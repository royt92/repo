from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .indicators import ema, rsi


@dataclass
class Signal:
    side: Optional[str]  # "buy" or "sell" or None
    reason: str


def generate_signal(closes: List[float]) -> Signal:
    if len(closes) < 50:
        return Signal(side=None, reason="insufficient_data")
    ema_fast = ema(closes, 9)
    ema_slow = ema(closes, 21)
    r = rsi(closes, 14)
    # Cross detection
    cross_up = ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1]
    cross_down = ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1]
    rsi_last = r[-1]
    if cross_up and rsi_last > 45:
        return Signal(side="buy", reason=f"ema_cross_up_rsi_{rsi_last:.1f}")
    if cross_down and rsi_last < 55:
        return Signal(side="sell", reason=f"ema_cross_down_rsi_{rsi_last:.1f}")
    return Signal(side=None, reason="no_setup")