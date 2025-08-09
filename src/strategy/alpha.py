from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.utils.math import ema, atr


@dataclass
class Signal:
    side: str  # "Buy" or "Sell"
    entry_price: float
    sl_price: float
    tp_price: float
    reason: str


class AlphaStrategy:
    def __init__(self, timeframe: str = "1m") -> None:
        self.timeframe = timeframe

    def generate(self, df: pd.DataFrame, orderbook: dict, tick_stats: dict) -> Optional[Signal]:
        if len(df) < 80:
            return None
        close = df["close"]
        ema20 = ema(close, 20)
        ema50 = ema(close, 50)
        ema200 = ema(close, 200)
        atr14 = atr(df["high"], df["low"], df["close"], 14)

        last_close = float(close.iloc[-1])
        last_ema20 = float(ema20.iloc[-1])
        last_ema50 = float(ema50.iloc[-1])
        last_ema200 = float(ema200.iloc[-1])
        last_atr = float(atr14.iloc[-1])

        # Trend filter: long only
        if not (last_ema20 > last_ema50 > last_ema200):
            return None

        # Pullback condition: price near ema20 within 0.1-0.2 ATR
        distance = abs(last_close - last_ema20)
        if last_atr <= 0 or distance > 0.25 * last_atr:
            return None

        # Orderbook imbalance
        bids = orderbook.get("b", [])
        asks = orderbook.get("a", [])
        if not bids or not asks:
            return None
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2
        # Sum top-10 levels
        bid_vol = sum(float(p) * float(q) for p, q in bids[:10])
        ask_vol = sum(float(p) * float(q) for p, q in asks[:10])
        if bid_vol + ask_vol == 0:
            return None
        ob_imb = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        if ob_imb < 0.05:
            return None

        # Tick volume spike confirmation
        tick_imb = float(tick_stats.get("tick_imbalance", 0.0))
        tick_freq = float(tick_stats.get("tick_freq", 0.0))
        if tick_imb < 0.05 or tick_freq < 10:
            return None

        # Compute SL/TP based on ATR
        sl_distance = max(0.15 / 100 * last_close, 0.5 * last_atr)
        tp_distance = max(0.25 / 100 * last_close, 0.8 * last_atr)
        sl_price = last_close - sl_distance
        tp_price = last_close + tp_distance

        return Signal(
            side="Buy",
            entry_price=last_close,
            sl_price=sl_price,
            tp_price=tp_price,
            reason=f"trend ema20>50>200 pullback {distance:.5f} ob_imb {ob_imb:.2f} tick_spike {tick_freq:.0f}"
        )