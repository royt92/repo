from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import ccxt


@dataclass
class MarketInfo:
    symbol: str
    base: str
    quote: str
    taker: float
    maker: float
    precision_price: int
    precision_amount: int
    min_cost: float


class BybitClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        subaccount: str = "",
        enable_rate_limit: bool = True,
        dry_run: bool = True,
    ) -> None:
        self.exchange = ccxt.bybit(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": enable_rate_limit,
                "options": {"defaultType": "spot"},
                **({"headers": {"X-BB-Sub-Account-Id": subaccount}} if subaccount else {}),
            }
        )
        self.dry_run = dry_run
        self._markets: Dict[str, MarketInfo] = {}

    def load_markets(self, reload: bool = False) -> Dict[str, MarketInfo]:
        if self._markets and not reload:
            return self._markets
        markets = self.exchange.load_markets(reload)
        result: Dict[str, MarketInfo] = {}
        for sym, m in markets.items():
            if m.get("type") != "spot":
                continue
            precision_price = m.get("precision", {}).get("price", 4)
            precision_amount = m.get("precision", {}).get("amount", 4)
            min_cost = 0.0
            limits = m.get("limits", {}) or {}
            cost = limits.get("cost") or {}
            min_cost = float(cost.get("min") or 0.0)
            result[sym] = MarketInfo(
                symbol=sym,
                base=m.get("base"),
                quote=m.get("quote"),
                taker=float(m.get("taker", 0.001)),
                maker=float(m.get("maker", 0.001)),
                precision_price=int(precision_price),
                precision_amount=int(precision_amount),
                min_cost=min_cost,
            )
        self._markets = result
        return result

    def fetch_tickers(self) -> Dict[str, dict]:
        return self.exchange.fetch_tickers()

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> List[List[float]]:
        # ohlcv: [timestamp, open, high, low, close, volume]
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_balance(self) -> dict:
        return self.exchange.fetch_balance()

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[dict] = None,
    ) -> dict:
        if self.dry_run:
            return {
                "id": f"dryrun-{int(time.time()*1000)}",
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "amount": amount,
                "price": price,
                "filled": 0.0,
                "status": "dry_run",
            }
        if order_type == "market":
            return self.exchange.create_market_order(symbol, side, amount, params or {})
        else:
            assert price is not None, "price required for limit orders"
            return self.exchange.create_limit_order(symbol, side, amount, price, params or {})

    def fetch_ticker(self, symbol: str) -> dict:
        return self.exchange.fetch_ticker(symbol)

    def market_price(self, symbol: str) -> float:
        t = self.fetch_ticker(symbol)
        return float(t.get("last") or t.get("close") or 0.0)

    def price_to_precision(self, symbol: str, price: float) -> float:
        return float(self.exchange.price_to_precision(symbol, price))

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        return float(self.exchange.amount_to_precision(symbol, amount))