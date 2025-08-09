import asyncio
import types

import pytest

from src.screener.screener import Screener


class DummyClient:
    async def fetch_symbols_spot(self):
        return [
            {"symbol": "AAAUSDT", "quoteCoin": "USDT", "status": "Trading"},
            {"symbol": "BBBUSDT", "quoteCoin": "USDT", "status": "Trading"},
        ]

    async def fetch_ticker_24h(self):
        return [
            {"symbol": "AAAUSDT", "turnover24h": "1000000"},
            {"symbol": "BBBUSDT", "turnover24h": "2000000"},
        ]

    async def fetch_orderbook(self, symbol: str, depth: int = 50):
        return {"b": [["10", "100"]], "a": [["10.01", "100"]]}

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 600):
        # generate trivial ascending prices
        now = 1710000000000
        kl = []
        for i in range(200):
            ts = now + i * 60_000
            o = 10 + i * 0.01
            h = o + 0.02
            l = o - 0.02
            c = o + 0.005
            v = 100 + i
            t = v * c
            kl.append([str(ts), str(o), str(h), str(l), str(c), str(v), str(t)])
        return kl

    async def fetch_trades(self, symbol: str, limit: int = 100):
        return [{"size": "10", "side": "Buy"} for _ in range(50)] + [{"size": "5", "side": "Sell"} for _ in range(10)]


@pytest.mark.asyncio
async def test_screener_returns_top3():
    s = Screener(DummyClient(), min_rvol=0.1, max_spread_bp=20, min_depth_usdt=1000, timeframe="1m")
    res = await s.fetch_candidates()
    assert len(res) <= 3
    assert all(r.symbol.endswith("USDT") for r in res)