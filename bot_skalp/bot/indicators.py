from __future__ import annotations

from typing import List, Tuple

import numpy as np


def ema(values: List[float], period: int) -> List[float]:
    if period <= 1:
        return values
    arr = np.array(values, dtype=float)
    ema_values = []
    k = 2 / (period + 1)
    prev = arr[0]
    for v in arr:
        prev = v * k + prev * (1 - k)
        ema_values.append(prev)
    return ema_values


def rsi(values: List[float], period: int = 14) -> List[float]:
    arr = np.array(values, dtype=float)
    deltas = np.diff(arr)
    seed = deltas[: period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi_series = [100 - 100 / (1 + rs)]
    up_val = up
    down_val = down
    for delta in deltas[period:]:
        up_val = (up_val * (period - 1) + max(delta, 0)) / period
        down_val = (down_val * (period - 1) + max(-delta, 0)) / period
        rs = up_val / down_val if down_val != 0 else 0
        rsi_series.append(100 - 100 / (1 + rs))
    # pad to same length
    padding = [50.0] * (len(values) - len(rsi_series))
    return padding + rsi_series


def atr_like(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    trs = []
    prev_close = closes[0]
    for h, l, c in zip(highs, lows, closes):
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    return ema(trs, period)


def realized_volatility(closes: List[float], period: int = 30) -> float:
    arr = np.array(closes[-period:], dtype=float)
    returns = np.diff(arr) / arr[:-1]
    return float(np.std(returns))