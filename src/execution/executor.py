from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from src.data.market_data import klines_to_df, compute_spread_bps, compute_depth, trades_to_tick_stats
from src.exchange.bybit_client import BybitClient
from src.notify.telegram import TelegramNotifier
from src.risk.risk_manager import RiskManager, SymbolRules
from src.settings import Settings
from src.storage.db import DB
from src.strategy.alpha import AlphaStrategy

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    qty: float
    avg_price: float
    sl_price: float
    tp_price: float


class Executor:
    def __init__(self, settings: Settings, client: BybitClient, db: DB, notifier: TelegramNotifier) -> None:
        self.settings = settings
        self.client = client
        self.db = db
        self.notifier = notifier

        self.strategy = AlphaStrategy(settings.timeframe)
        self.risk = RiskManager(settings.risk_per_trade, settings.max_daily_loss)

        self.positions: Dict[str, Position] = {}
        self.rules_cache: Dict[str, SymbolRules] = {}

    async def load_symbol_rules(self, symbol: str) -> SymbolRules:
        if symbol in self.rules_cache:
            return self.rules_cache[symbol]
        # Simplified: use instrument info for lot/step sizes
        infos = await self.client.fetch_symbols_spot()
        info = next(x for x in infos if x["symbol"] == symbol)
        min_qty = float(info.get("lotSizeFilter", {}).get("minOrderQty", 0.0))
        qty_step = float(info.get("lotSizeFilter", {}).get("qtyStep", 0.000001))
        price_step = float(info.get("priceFilter", {}).get("tickSize", 0.0000001))
        min_notional = float(info.get("lotSizeFilter", {}).get("minOrderAmt", 5.0))
        rules = SymbolRules(min_qty=min_qty, min_notional=min_notional, qty_step=qty_step, price_step=price_step)
        self.rules_cache[symbol] = rules
        return rules

    async def get_balance_usdt(self) -> float:
        if self.settings.mode == "paper":
            return 1000.0
        bal = await self.client.fetch_balance()
        # Unified account structure
        for acc in bal.get("list", []):
            for coin in acc.get("coin", []):
                if coin.get("coin") == "USDT":
                    return float(coin.get("walletBalance", 0))
        return 0.0

    async def handle_symbol(self, symbol: str) -> None:
        try:
            kl = await self.client.fetch_klines(symbol, interval=self.settings.timeframe, limit=300)
            df = klines_to_df(kl)
            ob = await self.client.fetch_orderbook(symbol, depth=50)
            trades = await self.client.fetch_trades(symbol, limit=100)
            tick_stats = trades_to_tick_stats(trades)

            signal = self.strategy.generate(df, ob, tick_stats)
            if not signal:
                return

            spread_bps = compute_spread_bps(ob)
            depth = compute_depth(ob, pct=0.002)
            rules = await self.load_symbol_rules(symbol)

            if not self.risk.validate_spread_and_depth(spread_bps, self.settings.screener_max_spread_bp, depth.total, self.settings.screener_min_depth_usdt):
                return

            balance = await self.get_balance_usdt()
            qty = self.risk.size_position(balance, signal.entry_price, signal.sl_price, rules)
            if qty <= 0:
                return

            if symbol in self.positions:
                return

            await self.notifier.send_trade(symbol, signal.side, qty, signal.entry_price, signal.reason)

            if self.settings.mode == "paper":
                # Simulate instant fill at best ask
                self.positions[symbol] = Position(symbol, qty, signal.entry_price, signal.sl_price, signal.tp_price)
                await self.db.insert_order(
                    client_order_id=str(uuid.uuid4()),
                    exchange_order_id="paper",
                    time=pd.Timestamp.utcnow(),
                    symbol=symbol,
                    side=signal.side,
                    type="Limit",
                    qty=qty,
                    price=signal.entry_price,
                    status="filled",
                    meta="{}",
                )
                return

            # Live: post-only then fallback
            order_link_id = str(uuid.uuid4())
            try:
                res = await self.client.place_order(
                    symbol=symbol,
                    side=signal.side,
                    order_type="Limit",
                    qty=f"{qty}",
                    price=f"{signal.entry_price}",
                    time_in_force="PostOnly" if self.settings.post_only else "GTC",
                    order_link_id=order_link_id,
                )
                await self.db.insert_order(
                    client_order_id=order_link_id,
                    exchange_order_id=res.get("orderId", ""),
                    time=pd.Timestamp.utcnow(),
                    symbol=symbol,
                    side=signal.side,
                    type="Limit",
                    qty=qty,
                    price=signal.entry_price,
                    status="new",
                    meta=json.dumps(res),
                )
            except Exception as e:
                # Fallback to IOC if post-only rejected
                res = await self.client.place_order(
                    symbol=symbol,
                    side=signal.side,
                    order_type="Market",
                    qty=f"{qty}",
                    time_in_force="IOC",
                    order_link_id=order_link_id,
                )
                await self.db.insert_order(
                    client_order_id=order_link_id,
                    exchange_order_id=res.get("orderId", ""),
                    time=pd.Timestamp.utcnow(),
                    symbol=symbol,
                    side=signal.side,
                    type="Market",
                    qty=qty,
                    price=signal.entry_price,
                    status="filled",
                    meta=json.dumps(res),
                )
                self.positions[symbol] = Position(symbol, qty, signal.entry_price, signal.sl_price, signal.tp_price)
        except Exception as e:
            logger.exception("handle_symbol_error", extra={"component": "executor", "symbol": symbol})

    async def manage_positions(self) -> None:
        # Simplified: poll prices and exit at SL/TP
        while True:
            await asyncio.sleep(2)
            for symbol, pos in list(self.positions.items()):
                ob = await self.client.fetch_orderbook(symbol, depth=1)
                bids = ob.get("b", [])
                asks = ob.get("a", [])
                if not bids or not asks:
                    continue
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                last_price = (best_bid + best_ask) / 2
                if last_price <= pos.sl_price or last_price >= pos.tp_price:
                    qty = pos.qty
                    pnl = (last_price - pos.avg_price) * qty
                    await self.notifier.send_exit(symbol, qty, last_price, pnl)
                    await self.db.insert_trade(
                        time=pd.Timestamp.utcnow(),
                        symbol=symbol,
                        side="Sell",
                        qty=qty,
                        price=last_price,
                        fee=0.0,
                        pnl=pnl,
                        strategy="alpha",
                    )
                    self.risk.register_trade_result(pnl)
                    del self.positions[symbol]

    async def run_symbols(self, symbols: List[str]) -> None:
        await asyncio.gather(*(self.handle_symbol(sym) for sym in symbols))

    async def run_loop(self, symbols: List[str], rescan_minutes: int) -> None:
        asyncio.create_task(self.manage_positions())
        while True:
            await self.run_symbols(symbols)
            await asyncio.sleep(rescan_minutes * 60)