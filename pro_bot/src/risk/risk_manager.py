from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SymbolRules:
    min_qty: float
    min_notional: float
    qty_step: float
    price_step: float


class RiskManager:
    def __init__(
        self,
        risk_per_trade: float,
        max_daily_loss: float,
        losing_streak_cooldown_trades: int = 3,
        cooldown_minutes: int = 30,
    ) -> None:
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.losing_streak_cooldown_trades = losing_streak_cooldown_trades
        self.cooldown_minutes = cooldown_minutes

        self.daily_realized_pnl: float = 0.0
        self.current_losing_streak: int = 0
        self.cooldown_active: bool = False

    def can_trade(self) -> bool:
        if self.cooldown_active:
            return False
        if self.daily_realized_pnl <= -abs(self.max_daily_loss):
            return False
        return True

    def register_trade_result(self, pnl: float) -> None:
        self.daily_realized_pnl += pnl
        if pnl < 0:
            self.current_losing_streak += 1
            if self.current_losing_streak >= self.losing_streak_cooldown_trades:
                self.cooldown_active = True
        else:
            self.current_losing_streak = 0

    def size_position(self, balance_usdt: float, entry_price: float, sl_price: float, rules: SymbolRules) -> float:
        if entry_price <= 0 or sl_price <= 0:
            return 0.0
        risk_amount = balance_usdt * self.risk_per_trade
        sl_distance = abs(entry_price - sl_price)
        if sl_distance <= 0:
            return 0.0
        raw_qty = risk_amount / sl_distance
        # round down to step
        stepped_qty = math.floor(raw_qty / rules.qty_step) * rules.qty_step
        if stepped_qty < rules.min_qty:
            return 0.0
        if stepped_qty * entry_price < rules.min_notional:
            # raise to min notional if possible
            stepped_qty = math.ceil(rules.min_notional / entry_price / rules.qty_step) * rules.qty_step
        return max(0.0, stepped_qty)

    def validate_spread_and_depth(self, spread_bps: float, min_spread_bps: float, depth_usdt: float, min_depth_usdt: float) -> bool:
        if spread_bps > min_spread_bps:
            return False
        if depth_usdt < min_depth_usdt:
            return False
        return True