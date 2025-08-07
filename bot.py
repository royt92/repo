#!/usr/bin/env python3
import os
import sys
import time
import json
import math
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
import yaml
import requests
from dotenv import load_dotenv

try:
    import ccxt
    from ta.trend import EMAIndicator
    from ta.momentum import RSIIndicator
    from ta.volatility import AverageTrueRange
except Exception as exc:
    print("Missing dependencies. Install: pip install -r /workspace/requirements.txt", file=sys.stderr)
    raise

STATE_PATH = "/workspace/state/positions.json"


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def ensure_dirs():
    os.makedirs("/workspace/state", exist_ok=True)
    os.makedirs("/workspace/output", exist_ok=True)


def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_PATH):
        return {"positions": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"positions": {}}


def save_state(state: Dict[str, Any]) -> None:
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def build_exchange(name: str):
    klass = getattr(ccxt, name)
    api_key = os.getenv("BYBIT_API_KEY")
    secret = os.getenv("BYBIT_API_SECRET")
    if not api_key or not secret:
        print("WARNING: BYBIT_API_KEY / BYBIT_API_SECRET not set. Read-only mode.")
    exchange = klass({
        "enableRateLimit": True,
        "apiKey": api_key,
        "secret": secret,
        "options": {"defaultType": "spot"},
    })
    return exchange


def fetch_universe(ex, cfg: Dict[str, Any]) -> List[str]:
    ex.load_markets()
    quote = cfg.get("universe", {}).get("quote", "USDT")
    min_vol = float(cfg.get("universe", {}).get("min_quote_volume_usd", 500000))
    max_symbols = int(cfg.get("universe", {}).get("max_symbols", 30))

    # fetch tickers for volume filtering
    tickers = ex.fetch_tickers()
    candidates = []
    for symbol, m in ex.markets.items():
        if m.get("spot") and m.get("active") and m.get("quote") == quote:
            t = tickers.get(symbol, {})
            # Prefer quote volume if provided
            vol_quote = t.get("quoteVolume") or t.get("baseVolume") * t.get("last", 0)
            if vol_quote and vol_quote >= min_vol:
                candidates.append((symbol, vol_quote))
    # sort by volume desc and cap
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in candidates[:max_symbols]]


def fetch_ohlcv_df(ex, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    raw = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    out = df.copy()
    out["ema200"] = EMAIndicator(close=close, window=200).ema_indicator()
    out["ema20"] = EMAIndicator(close=close, window=20).ema_indicator()
    out["rsi2"] = RSIIndicator(close=close, window=2).rsi()
    out["atr14"] = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
    out["roll_high20"] = out["high"].rolling(20, min_periods=20).max()
    return out


def send_telegram(cfg: Dict[str, Any], text: str) -> None:
    tg = cfg.get("telegram", {})
    if not tg.get("enabled", False):
        return
    token = os.getenv(tg.get("token_env", "TELEGRAM_BOT_TOKEN"))
    chat_id = os.getenv(tg.get("chat_id_env", "TELEGRAM_CHAT_ID"))
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass


def amount_from_budget(ex, market: Dict[str, Any], budget_quote: float, price: float) -> float:
    amount = budget_quote / price
    amount = ex.amount_to_precision(market["symbol"], amount)
    amount = float(amount)
    # Respect min amount/cost if known
    limits = market.get("limits", {})
    min_amount = (limits.get("amount") or {}).get("min")
    min_cost = (limits.get("cost") or {}).get("min")
    if min_amount and amount < min_amount:
        amount = min_amount
    if min_cost and amount * price < min_cost:
        amount = min_cost / price
    return float(ex.amount_to_precision(market["symbol"], amount))


def place_market_order(ex, symbol: str, side: str, amount: float) -> Optional[Dict[str, Any]]:
    try:
        order = ex.create_order(symbol, type="market", side=side, amount=amount)
        return order
    except Exception as exc:
        print(f"Order error {symbol} {side} {amount}: {exc}")
        return None


def run_bot(config_path: str):
    load_dotenv()
    ensure_dirs()
    cfg = load_config(config_path)

    exchange_id = cfg.get("exchange", "bybit")
    ex = build_exchange(exchange_id)

    symbols = cfg.get("symbols") or []
    if not symbols:
        print("Building universe from exchange...")
        symbols = fetch_universe(ex, cfg)
    print(f"Universe: {len(symbols)} symbols")

    tf = cfg.get("timeframe", "15m")
    lookback = int(cfg.get("lookback_bars", 400))

    trading = cfg.get("trading", {})
    per_order_usd = float(trading.get("per_order_usd", 5))
    max_budget_per_symbol = float(trading.get("max_budget_per_symbol", 25))
    max_open_positions = int(trading.get("max_open_positions", 8))
    dca_steps = list(trading.get("dca_atr_steps", [0.5, 1.0, 1.5]))
    trail_mult = float(trading.get("trail_atr_mult", 2.0))
    close_if_below_ema200 = bool(trading.get("close_if_below_ema200", True))
    poll_sec = int(trading.get("poll_interval_sec", 60))

    state = load_state()

    send_telegram(cfg, f"✅ Bot started at {utc_now_str()} with {len(symbols)} symbols on {exchange_id} {tf}")

    while True:
        try:
            ex.load_markets()
            open_positions = {s: p for s, p in state.get("positions", {}).items() if p.get("qty", 0) > 0}

            for symbol in symbols:
                market = ex.markets.get(symbol)
                if not market or not market.get("active"):
                    continue

                df = fetch_ohlcv_df(ex, symbol, tf, lookback)
                df = compute_indicators(df)
                last = df.iloc[-1]

                price = float(last["close"])  # approximate execution price
                atr = float(last["atr14"]) if not math.isnan(last["atr14"]) else None
                ema200 = float(last["ema200"]) if not math.isnan(last["ema200"]) else None
                trend_up = ema200 is not None and price > ema200

                pos = state.setdefault("positions", {}).setdefault(symbol, {
                    "qty": 0.0,
                    "avg_price": 0.0,
                    "budget_used": 0.0,
                    "ladders_filled": 0,
                    "highest_close": 0.0,
                })

                in_pos = pos["qty"] > 0

                # Entry signal: uptrend and either pullback or breakout
                pullback = trend_up and (float(last["rsi2"]) < 5) and (price <= float(last["ema20"]) * 1.01)
                breakout = trend_up and (price > float(df["high"].rolling(20, min_periods=20).max().shift(1).iloc[-1]))
                entry_signal = pullback or breakout

                # DCA ladder prices based on initial entry price and ATR
                if in_pos and atr is not None and pos["ladders_filled"] < len(dca_steps):
                    next_step = dca_steps[pos["ladders_filled"]]
                    dca_price = pos.get("first_entry_price", pos["avg_price"]) - next_step * atr
                else:
                    dca_price = None

                # Exits
                exit_signal = False
                if in_pos and atr is not None:
                    pos["highest_close"] = max(pos.get("highest_close", 0.0), price)
                    trail_stop = pos["highest_close"] - trail_mult * atr
                    if price <= trail_stop:
                        exit_signal = True
                if in_pos and close_if_below_ema200 and ema200 is not None and price < ema200:
                    exit_signal = True

                # Execute exits first
                if in_pos and exit_signal:
                    amount = float(ex.amount_to_precision(symbol, pos["qty"]))
                    if amount > 0:
                        order = place_market_order(ex, symbol, "sell", amount)
                        if order:
                            send_telegram(cfg, f"🔴 Exit {symbol}: sold {amount} at ~{price}")
                            pos.update({"qty": 0.0, "avg_price": 0.0, "budget_used": 0.0, "ladders_filled": 0, "highest_close": 0.0})
                            save_state(state)
                            continue

                # Entries / Adds
                if not in_pos and entry_signal:
                    # Risk: cap number of concurrent positions
                    if len(open_positions) >= max_open_positions:
                        continue
                    amount = amount_from_budget(ex, market, per_order_usd, price)
                    if amount <= 0:
                        continue
                    order = place_market_order(ex, symbol, "buy", amount)
                    if order:
                        cost = amount * price
                        pos["qty"] = pos["qty"] + amount
                        # weighted avg price
                        pos["avg_price"] = (pos["avg_price"] * (pos["qty"] - amount) + price * amount) / pos["qty"]
                        pos["budget_used"] += cost
                        pos["first_entry_price"] = price
                        pos["highest_close"] = price
                        pos["ladders_filled"] = 0
                        send_telegram(cfg, f"🟢 Entry {symbol}: bought {amount} at ~{price}, budget {pos['budget_used']:.2f}/{max_budget_per_symbol}")
                        save_state(state)
                        open_positions = {s: p for s, p in state.get("positions", {}).items() if p.get("qty", 0) > 0}
                        continue

                # DCA adds
                if in_pos and dca_price is not None and price <= dca_price and pos["budget_used"] + per_order_usd <= max_budget_per_symbol:
                    amount = amount_from_budget(ex, market, per_order_usd, price)
                    if amount > 0:
                        order = place_market_order(ex, symbol, "buy", amount)
                        if order:
                            cost = amount * price
                            prev_qty = pos["qty"]
                            pos["qty"] += amount
                            pos["avg_price"] = (pos["avg_price"] * prev_qty + price * amount) / pos["qty"]
                            pos["budget_used"] += cost
                            pos["ladders_filled"] += 1
                            send_telegram(cfg, f"➕ DCA {symbol}: bought {amount} at ~{price}, ladders {pos['ladders_filled']}/{len(dca_steps)}, budget {pos['budget_used']:.2f}/{max_budget_per_symbol}")
                            save_state(state)
                            continue

                # Optional heartbeat per symbol (sparse)
                # print(f"{symbol} price={price} in_pos={in_pos} entry={entry_signal} dca_price={dca_price}")

            # small sleep between full passes
            time.sleep(poll_sec)
        except KeyboardInterrupt:
            print("Stopping by user...")
            send_telegram(cfg, "⏹️ Bot stopped by user")
            break
        except Exception as exc:
            errmsg = f"Error: {exc}\n{traceback.format_exc()}"
            print(errmsg)
            send_telegram(cfg, f"⚠️ {errmsg[:3500]}")
            time.sleep(5)


if __name__ == "__main__":
    config_path = os.environ.get("BOT_CONFIG", "/workspace/config/config.yaml")
    run_bot(config_path)