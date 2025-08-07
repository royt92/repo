#!/usr/bin/env python3
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

import numpy as np
import pandas as pd
import yaml
from tabulate import tabulate

try:
    import ccxt
except Exception as exc:
    print("Failed to import ccxt. Please install requirements: pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    from ta.trend import EMAIndicator
    from ta.momentum import RSIIndicator
    from ta.volatility import AverageTrueRange
except Exception as exc:
    print("Failed to import ta. Please install requirements: pip install -r requirements.txt", file=sys.stderr)
    raise


def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_exchange(name: str, enable_rate_limit: bool = True):
    name = (name or "binance").lower()
    if not hasattr(ccxt, name):
        raise ValueError(f"Unsupported exchange: {name}")
    klass = getattr(ccxt, name)
    exchange = klass({
        "enableRateLimit": enable_rate_limit,
        "options": {"defaultType": "spot"},
    })
    return exchange


def fetch_ohlcv_df(exchange, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not raw:
        raise RuntimeError(f"No OHLCV returned for {symbol} {timeframe}")
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    df = pd.DataFrame(raw, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    ema200 = EMAIndicator(close=close, window=200, fillna=False).ema_indicator()
    ema20 = EMAIndicator(close=close, window=20, fillna=False).ema_indicator()
    rsi2 = RSIIndicator(close=close, window=2, fillna=False).rsi()
    atr14 = AverageTrueRange(high=high, low=low, close=close, window=14, fillna=False).average_true_range()

    out = df.copy()
    out["ema200"] = ema200
    out["ema20"] = ema20
    out["rsi2"] = rsi2
    out["atr14"] = atr14
    out["roll_high20"] = df["high"].rolling(20, min_periods=20).max()
    out["roll_low20"] = df["low"].rolling(20, min_periods=20).min()
    return out


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trend_up"] = out["close"] > out["ema200"]

    # Pullback: RSI(2) < 5 and price near/below EMA20 within uptrend
    out["pullback_signal"] = (
        (out["trend_up"]) &
        (out["rsi2"] < 5) &
        (out["close"] <= out["ema20"] * 1.01)
    )

    # Breakout: close breaks 20-bar high within uptrend
    out["breakout_signal"] = (
        (out["trend_up"]) &
        (out["close"] > out["roll_high20"].shift(1))
    )
    return out


def position_sizing(entry: float, stop: float, equity: float, risk_pct: float) -> Dict[str, float]:
    if entry <= 0 or stop <= 0 or entry <= stop:
        return {"risk_amount": 0.0, "qty_base": 0.0, "position_value": 0.0}
    risk_amount = equity * (risk_pct / 100.0)
    risk_per_unit = entry - stop
    qty_base = risk_amount / risk_per_unit
    position_value = qty_base * entry
    return {
        "risk_amount": float(risk_amount),
        "qty_base": float(qty_base),
        "position_value": float(position_value),
    }


def format_timestamp(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def run_screener(args: argparse.Namespace) -> None:
    cfg = load_config(args.config) if args.config else {}

    exchange_name = args.exchange or cfg.get("exchange", "binance")
    timeframe = args.timeframe or cfg.get("timeframe", "15m")
    lookback = int(args.lookback or cfg.get("lookback_bars", 600))

    symbols_cli = []
    if args.symbols:
        symbols_cli = [s.strip() for s in args.symbols.split(",") if s.strip()]
    symbols_cfg = cfg.get("symbols", [])
    symbols: List[str] = symbols_cli or symbols_cfg
    if not symbols:
        raise SystemExit("No symbols provided. Use --symbols or config.yaml")

    equity = float(args.equity or cfg.get("risk", {}).get("equity", 10000))
    risk_pct = float(args.risk_pct or cfg.get("risk", {}).get("risk_pct", 0.75))
    atr_mult = float(args.atr_mult or cfg.get("risk", {}).get("atr_mult", 1.0))

    strategies_cfg = cfg.get("strategies", ["pullback", "breakout"])
    selected = args.strategy
    strategy_names = [selected] if selected in ("pullback", "breakout") else strategies_cfg

    os.makedirs("/workspace/output", exist_ok=True)

    ex = build_exchange(exchange_name)

    rows = []
    now = datetime.now(timezone.utc)

    for symbol in symbols:
        try:
            df = fetch_ohlcv_df(ex, symbol, timeframe, limit=lookback)
            df = compute_indicators(df)
            df = generate_signals(df)
            last = df.iloc[-1]

            entry_pullback = float(last["close"]) if bool(last["pullback_signal"]) else np.nan
            stop_pullback = float(last["close"] - atr_mult * last["atr14"]) if bool(last["pullback_signal"]) else np.nan
            size_pullback = position_sizing(entry_pullback, stop_pullback, equity, risk_pct) if bool(last["pullback_signal"]) else {"qty_base": np.nan, "position_value": np.nan}

            entry_breakout = float(last["close"]) if bool(last["breakout_signal"]) else np.nan
            stop_breakout = float(last["close"] - 1.5 * last["atr14"]) if bool(last["breakout_signal"]) else np.nan
            size_breakout = position_sizing(entry_breakout, stop_breakout, equity, risk_pct) if bool(last["breakout_signal"]) else {"qty_base": np.nan, "position_value": np.nan}

            row = {
                "timestamp": format_timestamp(now),
                "symbol": symbol,
                "timeframe": timeframe,
                "price": float(last["close"]),
                "ema200": float(last["ema200"]) if pd.notna(last["ema200"]) else np.nan,
                "ema20": float(last["ema20"]) if pd.notna(last["ema20"]) else np.nan,
                "atr14": float(last["atr14"]) if pd.notna(last["atr14"]) else np.nan,
                "rsi2": float(last["rsi2"]) if pd.notna(last["rsi2"]) else np.nan,
                "trend_up": bool(last.get("trend_up", False)),
                "pullback_signal": bool(last.get("pullback_signal", False)) if "pullback" in strategy_names else False,
                "pullback_entry": entry_pullback if "pullback" in strategy_names else np.nan,
                "pullback_stop": stop_pullback if "pullback" in strategy_names else np.nan,
                "pullback_qty": float(size_pullback.get("qty_base", np.nan)) if "pullback" in strategy_names else np.nan,
                "breakout_signal": bool(last.get("breakout_signal", False)) if "breakout" in strategy_names else False,
                "breakout_entry": entry_breakout if "breakout" in strategy_names else np.nan,
                "breakout_stop": stop_breakout if "breakout" in strategy_names else np.nan,
                "breakout_qty": float(size_breakout.get("qty_base", np.nan)) if "breakout" in strategy_names else np.nan,
            }
            rows.append(row)
        except Exception as exc:
            print(f"Error processing {symbol}: {exc}", file=sys.stderr)
            continue

    if not rows:
        print("No data/signals to display.")
        return

    out_df = pd.DataFrame(rows)
    csv_path = f"/workspace/output/screener_signals_{int(time.time())}.csv"
    out_df.to_csv(csv_path, index=False)

    display_cols = [
        "timestamp", "symbol", "price", "trend_up", "rsi2", "atr14",
        "pullback_signal", "pullback_entry", "pullback_stop", "pullback_qty",
        "breakout_signal", "breakout_entry", "breakout_stop", "breakout_qty",
    ]
    print(tabulate(out_df[display_cols], headers="keys", tablefmt="psql", showindex=False))
    print(f"Saved: {csv_path}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Intraday crypto spot screener")
    p.add_argument("--config", type=str, default="/workspace/config/config.yaml", help="Path to YAML config")
    p.add_argument("--exchange", type=str, default=None, help="Exchange id (ccxt), e.g., binance")
    p.add_argument("--symbols", type=str, default=None, help="Comma separated symbols, e.g., BTC/USDT,ETH/USDT")
    p.add_argument("--timeframe", type=str, default=None, help="Timeframe, e.g., 15m, 1h")
    p.add_argument("--lookback", type=int, default=None, help="Bars to fetch (default from config)")
    p.add_argument("--equity", type=float, default=None, help="Account equity in quote currency (e.g., USDT)")
    p.add_argument("--risk-pct", dest="risk_pct", type=float, default=None, help="Risk per trade, percent of equity")
    p.add_argument("--atr-mult", dest="atr_mult", type=float, default=None, help="ATR multiple for stop sizing")
    p.add_argument("--strategy", type=str, default="both", choices=["pullback", "breakout", "both"], help="Which strategy signals to show")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    run_screener(args)