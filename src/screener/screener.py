from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from src.data.market_data import klines_to_df, compute_spread_bps, compute_depth, trades_to_tick_stats
from src.exchange.bybit_client import BybitClient
from src.utils.math import ema, atr, adx, zscore, normalize_minmax

logger = logging.getLogger(__name__)


@dataclass
class ScreenedSymbol:
    symbol: str
    score: float
    notes: str


class Screener:
    def __init__(self, client: BybitClient, min_rvol: float, max_spread_bp: float, min_depth_usdt: float, timeframe: str = "1m") -> None:
        self.client = client
        self.min_rvol = min_rvol
        self.max_spread_bp = max_spread_bp
        self.min_depth_usdt = min_depth_usdt
        self.timeframe = timeframe

    async def fetch_candidates(self) -> List[ScreenedSymbol]:
        symbols_info = await self.client.fetch_symbols_spot()
        symbols = [s["symbol"] for s in symbols_info if s.get("quoteCoin") == "USDT"]
        # Ticker volumes
        tickers = await self.client.fetch_ticker_24h()
        vol24 = {t["symbol"]: float(t.get("turnover24h", 0)) for t in tickers}

        results: List[ScreenedSymbol] = []

        async def process_symbol(sym: str) -> None:
            try:
                ob = await self.client.fetch_orderbook(sym, depth=50)
                spread_bp = compute_spread_bps(ob)
                depth = compute_depth(ob, pct=0.002)
                if spread_bp > self.max_spread_bp:
                    return
                if depth.total < self.min_depth_usdt:
                    return
                kl = await self.client.fetch_klines(sym, interval=self.timeframe, limit=600)
                if len(kl) < 100:
                    return
                df = klines_to_df(kl)
                df["ret"] = np.log(df["close"]).diff()
                df["ema20"] = ema(df["close"], 20)
                df["ema50"] = ema(df["close"], 50)
                df["ema200"] = ema(df["close"], 200)
                df["atr14"] = atr(df["high"], df["low"], df["close"], 14)
                df["adx14"] = adx(df["high"], df["low"], df["close"], 14)

                # RVOL approximation: use turnover relative to rolling mean
                vol_series = df["turnover"].rolling(1440 // (1 if self.timeframe == "1m" else 5)).sum()
                rvol_now = (vol_series.iloc[-1] / vol_series.rolling(10).mean().iloc[-2]) if len(vol_series) > 11 else 0
                if rvol_now < self.min_rvol:
                    return

                # Volatility
                atrp = (df["atr14"].iloc[-1] / df["close"].iloc[-1]) if df["close"].iloc[-1] > 0 else 0

                # Trend/momentum
                trend_long = 1.0 if (df["ema20"].iloc[-1] > df["ema50"].iloc[-1] > df["ema200"].iloc[-1]) else 0.0
                ema_slope = (df["ema20"].iloc[-1] - df["ema20"].iloc[-5]) / (5 * df["ema20"].iloc[-5] if df["ema20"].iloc[-5] else 1)
                adx_now = df["adx14"].iloc[-1]

                # Tick stats
                trades = await self.client.fetch_trades(sym, limit=100)
                tstats = trades_to_tick_stats(trades)

                # Normalize and weighted score
                # Use rough normalization for spread, atrp, adx, slope, imbalance, depth
                spread_norm = max(0.0, 1.0 - (spread_bp / self.max_spread_bp))
                atr_norm = min(1.0, atrp / 0.01)  # favor <=1% ATR
                adx_norm = min(1.0, adx_now / 25.0)
                slope_norm = max(0.0, min(1.0, ema_slope * 200))  # scale slope
                imb_norm = (tstats["tick_imbalance"] + 1) / 2
                depth_norm = min(1.0, depth.total / (self.min_depth_usdt * 2))
                rvol_norm = min(1.0, rvol_now / (self.min_rvol * 1.5))

                score = (
                    0.20 * spread_norm
                    + 0.20 * depth_norm
                    + 0.20 * rvol_norm
                    + 0.15 * adx_norm
                    + 0.15 * slope_norm
                    + 0.10 * imb_norm
                )
                note = f"spread={spread_bp:.1f}bp depth={depth.total:.0f} rvol={rvol_now:.2f} adx={adx_now:.1f} slope={ema_slope:.4f} imb={tstats['tick_imbalance']:.2f}"
                results.append(ScreenedSymbol(sym, float(score), note))
            except Exception as e:
                logger.warning("screener_symbol_error", extra={"component": "screener", "symbol": sym, "error": str(e)})

        # Concurrency limited
        sem = asyncio.Semaphore(10)

        async def sem_task(sym: str):
            async with sem:
                await process_symbol(sym)

        await asyncio.gather(*(sem_task(s) for s in symbols))

        # Sort and take top 3
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:3]