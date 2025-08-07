#!/usr/bin/env python3
import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:
    import ccxt
    from ta.trend import EMAIndicator
    from ta.momentum import RSIIndicator
    from ta.volatility import AverageTrueRange
except Exception as exc:
    print("Missing dependencies. Install: pip install -r requirements.txt", file=sys.stderr)
    raise


@dataclass
class StrategyParams:
    strategy: str  # 'pullback' or 'breakout'
    risk_pct: float = 0.75
    atr_mult_stop: float = 1.0
    atr_mult_trail: float = 2.0
    breakout_lookback: int = 20
    take_profit_r_multiple: float = 2.0


def build_exchange(name: str):
    name = (name or "binance").lower()
    if not hasattr(ccxt, name):
        raise ValueError(f"Unsupported exchange: {name}")
    klass = getattr(ccxt, name)
    return klass({"enableRateLimit": True, "options": {"defaultType": "spot"}})


def fetch_ohlcv_df(exchange, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    df = pd.DataFrame(raw, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


def with_indicators(df: pd.DataFrame) -> pd.DataFrame:
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


def generate_entries(df: pd.DataFrame, params: StrategyParams) -> pd.Series:
    trend_up = df["close"] > df["ema200"]
    if params.strategy == "pullback":
        entries = trend_up & (df["rsi2"] < 5) & (df["close"] <= df["ema20"] * 1.01)
    else:  # breakout
        entries = trend_up & (df["close"] > df["roll_high20"].shift(1))
    # enter on next bar open
    return entries.shift(1).fillna(False)


def run_backtest(df: pd.DataFrame, params: StrategyParams, equity: float, fee_bps_per_side: float = 10.0) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    entries = generate_entries(df, params)

    opens = df["open"].astype(float)
    atr = df["atr14"].astype(float)

    in_trade = False
    entry_price = 0.0
    stop_price = 0.0
    highest_close_since_entry = 0.0

    r_list = []
    trade_records = []

    for ts, row in df.iterrows():
        o = float(row["open"]) if not np.isnan(row["open"]) else None
        c = float(row["close"]) if not np.isnan(row["close"]) else None
        a = float(row["atr14"]) if not np.isnan(row["atr14"]) else None

        if not in_trade and entries.loc[ts]:
            # enter
            entry_price = o
            if params.strategy == "pullback":
                stop_price = entry_price - params.atr_mult_stop * a
            else:
                stop_price = entry_price - 1.5 * a
            risk_per_unit = entry_price - stop_price
            highest_close_since_entry = c
            in_trade = True
            r_list.append(np.nan)
            continue

        if in_trade:
            # update trailing
            highest_close_since_entry = max(highest_close_since_entry, c)
            trail_stop = highest_close_since_entry - params.atr_mult_trail * a
            active_stop = max(stop_price, trail_stop)

            r_multiple = (c - entry_price) / (entry_price - stop_price)
            take_profit_hit = r_multiple >= params.take_profit_r_multiple

            stop_hit = row["low"] <= active_stop

            if stop_hit:
                exit_price = active_stop
            elif take_profit_hit:
                exit_price = c
            else:
                # no exit
                r_list.append(np.nan)
                continue

            r = (exit_price - entry_price) / (entry_price - stop_price)
            r_list.append(r)
            trade_records.append({
                "timestamp": ts,
                "entry": entry_price,
                "exit": exit_price,
                "stop": stop_price,
                "atr": a,
                "r": r,
            })
            in_trade = False
            entry_price = 0.0
            stop_price = 0.0
            highest_close_since_entry = 0.0
        else:
            r_list.append(np.nan)

    pnl_r = pd.Series(r_list, index=df.index, name="r")

    # Apply fees: two sides per trade, approximate by subtracting fee in R units at exits
    fee_per_side = fee_bps_per_side / 10000.0
    # Approximate R fee impact: 2*fee * entry_price / (entry_price - stop_price)
    # We'll subtract a flat 0.04 R per trade for simplicity (depends on stop distance). Conservative.
    realized_trades = pnl_r.dropna()
    realized_trades_after_fees = realized_trades - 0.04

    equity_curve_r = realized_trades_after_fees.cumsum()

    stats = {
        "trades": int(realized_trades_after_fees.shape[0]),
        "win_rate": float((realized_trades_after_fees > 0).mean()) if realized_trades_after_fees.shape[0] else 0.0,
        "avg_r": float(realized_trades_after_fees.mean()) if realized_trades_after_fees.shape[0] else 0.0,
        "total_r": float(realized_trades_after_fees.sum()) if realized_trades_after_fees.shape[0] else 0.0,
        "max_dd_r": float((equity_curve_r - equity_curve_r.cummax()).min()) if realized_trades_after_fees.shape[0] else 0.0,
    }

    result_df = pd.DataFrame({
        "open": df["open"],
        "close": df["close"],
        "r": pnl_r,
        "equity_r": equity_curve_r.reindex(df.index).ffill().fillna(0.0),
    })

    return result_df, stats


def main(argv: List[str]) -> None:
    ap = argparse.ArgumentParser(description="Simple intraday backtest for spot crypto strategies")
    ap.add_argument("--exchange", type=str, default="binance")
    ap.add_argument("--symbol", type=str, default="BTC/USDT")
    ap.add_argument("--timeframe", type=str, default="15m")
    ap.add_argument("--lookback", type=int, default=1000)
    ap.add_argument("--strategy", type=str, choices=["pullback", "breakout"], default="pullback")
    ap.add_argument("--equity", type=float, default=10000)
    args = ap.parse_args(argv)

    ex = build_exchange(args.exchange)
    df = fetch_ohlcv_df(ex, args.symbol, args.timeframe, args.lookback)
    df = with_indicators(df)

    params = StrategyParams(strategy=args.strategy)
    result_df, stats = run_backtest(df, params, args.equity)

    print(f"Symbol: {args.symbol}  Timeframe: {args.timeframe}  Bars: {len(result_df)}")
    print("Stats:")
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    out_path = f"/workspace/output/backtest_{args.symbol.replace('/', '-')}_{args.timeframe}_{args.strategy}.csv"
    os.makedirs("/workspace/output", exist_ok=True)
    result_df.to_csv(out_path)
    print(f"Saved equity and R series: {out_path}")


if __name__ == "__main__":
    main(sys.argv[1:])