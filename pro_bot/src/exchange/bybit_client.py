from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from src.settings import get_settings

logger = logging.getLogger(__name__)


class BybitClient:
    def __init__(self, api_key: Optional[str], api_secret: Optional[str], env: str = "live") -> None:
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.env = env
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_rest = "https://api.bybit.com" if env == "live" else "https://api-testnet.bybit.com"
        self.base_ws_public = "wss://stream.bybit.com/v5/public/spot" if env == "live" else "wss://stream-testnet.bybit.com/v5/public/spot"
        self.base_ws_private = "wss://stream.bybit.com/v5/private" if env == "live" else "wss://stream-testnet.bybit.com/v5/private"

    async def __aenter__(self) -> "BybitClient":
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self.session:
            await self.session.close()
            self.session = None

    # --- REST helpers ---
    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        payload = timestamp + self.api_key + recv_window + json.dumps(params, separators=(",", ":"))
        signature = hmac.new(self.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json",
        }

    @retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None, auth: bool = False) -> Any:
        assert self.session
        url = self.base_rest + path
        headers = self._sign(params or {}) if auth else None
        async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json(content_type=None)
            if r.status != 200 or data.get("retCode") not in (0, "0"):
                raise RuntimeError(f"GET {path} failed: {r.status} {data}")
            return data.get("result")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
    async def _post(self, path: str, body: Optional[Dict[str, Any]] = None, auth: bool = True) -> Any:
        assert self.session
        url = self.base_rest + path
        headers = self._sign(body or {}) if auth else {"Content-Type": "application/json"}
        async with self.session.post(url, data=json.dumps(body or {}), headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json(content_type=None)
            if r.status != 200 or data.get("retCode") not in (0, "0"):
                raise RuntimeError(f"POST {path} failed: {r.status} {data}")
            return data.get("result")

    # --- Public methods ---
    async def fetch_symbols_spot(self) -> List[Dict[str, Any]]:
        res = await self._get("/v5/market/instruments-info", {"category": "spot"})
        return [x for x in res.get("list", []) if x.get("quoteCoin") == "USDT" and x.get("status") == "Trading"]

    async def fetch_ticker_24h(self) -> List[Dict[str, Any]]:
        res = await self._get("/v5/market/tickers", {"category": "spot"})
        return res.get("list", [])

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> List[List[str]]:
        res = await self._get(
            "/v5/market/kline",
            {"category": "spot", "symbol": symbol, "interval": interval, "limit": limit},
        )
        return res.get("list", [])

    async def fetch_orderbook(self, symbol: str, depth: int = 50) -> Dict[str, Any]:
        res = await self._get(
            "/v5/market/orderbook",
            {"category": "spot", "symbol": symbol, "limit": depth},
        )
        return res

    async def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        res = await self._get(
            "/v5/market/recent-trade",
            {"category": "spot", "symbol": symbol, "limit": limit},
        )
        return res.get("list", [])

    # --- Private methods ---
    async def fetch_balance(self) -> Dict[str, Any]:
        res = await self._get("/v5/account/wallet-balance", {"accountType": "UNIFIED"}, auth=True)
        return res

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        price: Optional[str] = None,
        time_in_force: str = "PostOnly",
        reduce_only: bool = False,
        category: str = "spot",
        is_market: bool = False,
        order_link_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": order_type.capitalize(),
            "qty": qty,
            "timeInForce": time_in_force,
        }
        if price is not None:
            body["price"] = price
        if order_link_id:
            body["orderLinkId"] = order_link_id
        return await self._post("/v5/order/create", body, auth=True)

    async def cancel_order(self, symbol: str, order_id: Optional[str] = None, order_link_id: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"category": "spot", "symbol": symbol}
        if order_id:
            body["orderId"] = order_id
        if order_link_id:
            body["orderLinkId"] = order_link_id
        return await self._post("/v5/order/cancel", body, auth=True)

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        res = await self._get("/v5/order/realtime", params, auth=True)
        return res.get("list", [])

    # --- WebSocket ---
    async def ws_public(self, topics: List[str]):
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.base_ws_public, heartbeat=20) as ws:
                await ws.send_json({"op": "subscribe", "args": topics})
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        yield data
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break

    async def ws_private(self, topics: List[str]):
        if not (self.api_key and self.api_secret):
            raise RuntimeError("Private WS requires API credentials")
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.base_ws_private, heartbeat=20) as ws:
                timestamp = str(int(time.time() * 1000))
                param_str = "GET/realtime" + timestamp
                sign = hmac.new(self.api_secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()
                await ws.send_json({
                    "op": "auth",
                    "args": [self.api_key, timestamp, sign],
                })
                await ws.send_json({"op": "subscribe", "args": topics})
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        yield data
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break