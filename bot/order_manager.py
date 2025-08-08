from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from .exchange import BybitClient


@dataclass
class Position:
    symbol: str
    avg_price: float
    quantity: float
    invested_usd: float
    target_tp_pct: float
    stop_loss_pct: float
    dca_executed: int


class OrderManager:
    def __init__(self, client: BybitClient, state_path: str = "/workspace/state.json") -> None:
        self.client = client
        self.state_path = state_path
        self.positions: Dict[str, Position] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.state_path, "r") as f:
                raw = json.load(f)
            for sym, p in raw.get("positions", {}).items():
                self.positions[sym] = Position(**p)
        except Exception:
            self.positions = {}

    def _save(self) -> None:
        try:
            with open(self.state_path, "w") as f:
                json.dump({"positions": {s: asdict(p) for s, p in self.positions.items()}}, f, indent=2)
        except Exception:
            pass

    def open_position(
        self,
        symbol: str,
        usd_amount: float,
        take_profit_pct: float,
        stop_loss_pct: float,
    ) -> Optional[Position]:
        price = self.client.market_price(symbol)
        if price <= 0:
            return None
        qty = usd_amount / price
        qty = self.client.amount_to_precision(symbol, qty)
        if qty <= 0:
            return None
        self.client.create_order(symbol, "buy", "market", qty)
        pos = Position(
            symbol=symbol,
            avg_price=price,
            quantity=qty,
            invested_usd=usd_amount,
            target_tp_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            dca_executed=0,
        )
        self.positions[symbol] = pos
        self._save()
        return pos

    def maybe_take_profit(self, symbol: str) -> Optional[float]:
        pos = self.positions.get(symbol)
        if not pos:
            return None
        price = self.client.market_price(symbol)
        if price <= 0:
            return None
        gain_pct = (price - pos.avg_price) / pos.avg_price * 100.0
        if gain_pct >= pos.target_tp_pct:
            self.client.create_order(symbol, "sell", "market", pos.quantity)
            profit_usd = (price - pos.avg_price) * pos.quantity
            del self.positions[symbol]
            self._save()
            return profit_usd
        return None

    def maybe_stop_loss(self, symbol: str) -> bool:
        pos = self.positions.get(symbol)
        if not pos:
            return False
        price = self.client.market_price(symbol)
        if price <= 0:
            return False
        loss_pct = (pos.avg_price - price) / pos.avg_price * 100.0
        if loss_pct >= pos.stop_loss_pct:
            self.client.create_order(symbol, "sell", "market", pos.quantity)
            del self.positions[symbol]
            self._save()
            return True
        return False

    def maybe_execute_dca(self, symbol: str, dca_steps_down_pct: List[float], dca_allocations_usd: List[float]) -> Optional[float]:
        pos = self.positions.get(symbol)
        if not pos:
            return None
        step_index = pos.dca_executed
        if step_index >= len(dca_steps_down_pct) or step_index >= len(dca_allocations_usd):
            return None
        price = self.client.market_price(symbol)
        if price <= 0:
            return None
        drop_pct = (pos.avg_price - price) / pos.avg_price * 100.0
        target_drop = dca_steps_down_pct[step_index]
        if drop_pct >= target_drop:
            usd = dca_allocations_usd[step_index]
            add_qty = usd / price
            add_qty = self.client.amount_to_precision(symbol, add_qty)
            if add_qty <= 0:
                return None
            self.client.create_order(symbol, "buy", "market", add_qty)
            new_qty = pos.quantity + add_qty
            pos.avg_price = (pos.avg_price * pos.quantity + price * add_qty) / new_qty
            pos.quantity = new_qty
            pos.invested_usd += usd
            pos.dca_executed += 1
            self.positions[symbol] = pos
            self._save()
            return usd
        return None