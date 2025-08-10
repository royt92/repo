from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from src.utils.math import DepthStats


def klines_to_df(klines: List[List[str]]) -> pd.DataFrame:
    # Bybit returns [timestamp, open, high, low, close, volume, turnover]
    cols = ["ts", "open", "high", "low", "close", "volume", "turnover"]
    df = pd.DataFrame(klines, columns=cols)
    for c in cols:
        if c == "ts":
            # Robustly parse timestamps possibly in sec/ms/us/ns and large integer strings
            ts_num = pd.to_numeric(df[c], errors="coerce")
            # Normalize to milliseconds
            median = ts_num.median(skipna=True)
            if pd.isna(median):
                df[c] = pd.NaT
            else:
                if median < 1e12:  # seconds
                    ts_ms = (ts_num * 1000).astype("int64", errors="ignore")
                elif median >= 1e16:  # nanoseconds
                    ts_ms = (ts_num // 1_000_000).astype("int64", errors="ignore")
                elif median >= 1e15:  # microseconds
                    ts_ms = (ts_num // 1_000).astype("int64", errors="ignore")
                else:  # milliseconds already
                    ts_ms = ts_num.astype("int64", errors="ignore")
                df[c] = pd.to_datetime(ts_ms, unit="ms", utc=True)
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def compute_spread_bps(orderbook: Dict[str, Any]) -> float:
    bids = orderbook.get("b", [])
    asks = orderbook.get("a", [])
    if not bids or not asks:
        return 1e9
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid = (best_bid + best_ask) / 2
    if mid == 0:
        return 1e9
    return (best_ask - best_bid) / mid * 10000


def compute_depth(orderbook: Dict[str, Any], pct: float = 0.002) -> DepthStats:
    bids = orderbook.get("b", [])
    asks = orderbook.get("a", [])
    if not bids or not asks:
        return DepthStats(0.0, 0.0)
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    mid = (best_bid + best_ask) / 2
    bid_limit = mid * (1 - pct)
    ask_limit = mid * (1 + pct)
    bid_depth = 0.0
    ask_depth = 0.0
    for price, qty in bids:
        p = float(price)
        q = float(qty)
        if p < bid_limit:
            break
        bid_depth += p * q
    for price, qty in asks:
        p = float(price)
        q = float(qty)
        if p > ask_limit:
            break
        ask_depth += p * q
    return DepthStats(bid_depth, ask_depth)


def trades_to_tick_stats(trades: List[Dict[str, Any]]) -> Dict[str, float]:
    # Bybit recent trades have: execId, symbol, price, size, side, time
    buy_vol = 0.0
    sell_vol = 0.0
    for t in trades:
        size = float(t.get("size", 0))
        side = t.get("side", "")
        if side.lower().startswith("buy"):
            buy_vol += size
        elif side.lower().startswith("sell"):
            sell_vol += size
    total = buy_vol + sell_vol
    imbalance = (buy_vol - sell_vol) / total if total > 0 else 0.0
    freq = len(trades)
    return {"buy_vol": buy_vol, "sell_vol": sell_vol, "tick_imbalance": imbalance, "tick_freq": float(freq)}