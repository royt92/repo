from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from .indicators import realized_volatility


@dataclass
class ScreenedSymbol:
    symbol: str
    score: float
    vol24h_usd: float
    rv: float


def screen_symbols(
    tickers: Dict[str, dict],
    quote_asset: str,
    ohlc_provider,
    timeframe: str,
    top_n: int = 20,
) -> List[ScreenedSymbol]:
    candidates: List[ScreenedSymbol] = []
    for sym, t in tickers.items():
        # Spot symbols like BTC/USDT
        if not sym.endswith(f"/{quote_asset}"):
            continue
        if "info" in t and t["info"].get("contractType"):
            # skip derivatives
            continue
        info = t.get("info", {}) or {}
        vol = float(
            t.get("quoteVolume")
            or t.get("baseVolume")
            or info.get("quoteVolume24h")
            or info.get("turnover24h")
            or info.get("qv")
            or 0.0
        )
        last = float(t.get("last") or t.get("close") or info.get("lastPrice") or info.get("lp") or 0.0)
        if last <= 0 or vol <= 100000:  # require some liquidity
            continue
        try:
            ohlcv = ohlc_provider(sym, timeframe, limit=120)
            closes = [c[4] for c in ohlcv]
            rv = realized_volatility(closes, period=60)
        except Exception:
            rv = 0.0
        score = vol * (1 + 1000 * rv)
        candidates.append(ScreenedSymbol(symbol=sym, score=score, vol24h_usd=vol, rv=rv))
    candidates.sort(key=lambda x: x.score, reverse=True)
    return candidates[:top_n]