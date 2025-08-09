from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List

import pandas as pd

from src.exchange.bybit_client import BybitClient
from src.notify.telegram import TelegramNotifier
from src.screener.screener import Screener
from src.settings import get_settings
from src.storage.db import DB
from src.utils.logging import setup_logging
from src.execution.executor import Executor


async def run_once() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    await notifier.send_startup(settings.mode, settings.bybit_env, settings.risk_per_trade, settings.max_daily_loss)

    async with BybitClient(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_env) as client:
        db = DB(settings.sqlite_path)
        await db.init()

        screener = Screener(
            client,
            min_rvol=settings.screener_min_rvol,
            max_spread_bp=settings.screener_max_spread_bp,
            min_depth_usdt=settings.screener_min_depth_usdt,
            timeframe=settings.timeframe,
        )
        candidates = await screener.fetch_candidates()
        top_symbols = [c.symbol for c in candidates][: settings.max_concurrent_symbols]
        await notifier.send_candidates([(c.symbol, c.notes) for c in candidates])

        executor = Executor(settings, client, db, notifier)
        if not top_symbols:
            return
        await executor.run_symbols(top_symbols)


async def run_daemon() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    await notifier.send_startup(settings.mode, settings.bybit_env, settings.risk_per_trade, settings.max_daily_loss)

    async with BybitClient(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_env) as client:
        db = DB(settings.sqlite_path)
        await db.init()

        screener = Screener(
            client,
            min_rvol=settings.screener_min_rvol,
            max_spread_bp=settings.screener_max_spread_bp,
            min_depth_usdt=settings.screener_min_depth_usdt,
            timeframe=settings.timeframe,
        )
        executor = Executor(settings, client, db, notifier)
        while True:
            candidates = await screener.fetch_candidates()
            top_symbols = [c.symbol for c in candidates][: settings.max_concurrent_symbols]
            await notifier.send_candidates([(c.symbol, c.notes) for c in candidates])
            if top_symbols:
                await executor.run_loop(top_symbols, settings.rescan_minutes)
            else:
                await asyncio.sleep(settings.rescan_minutes * 60)


def backtest(symbol: str, days: int) -> None:
    # Simplified backtest: uses klines and strategy rules without market impact
    settings = get_settings()
    setup_logging(settings.log_level)

    async def _run():
        async with BybitClient(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_env) as client:
            kl = await client.fetch_klines(symbol, interval=settings.timeframe, limit=days * (1440 // (1 if settings.timeframe == "1m" else 5)))
            df = pd.DataFrame()
            if kl:
                df = pd.DataFrame(kl, columns=["ts", "open", "high", "low", "close", "volume", "turnover"]).astype(float)
            # Placeholder: compute naive metrics
            returns = pd.Series([0.0])
            print({"trades": 0, "win_rate": 0.0, "pf": 0.0, "expectancy": 0.0})

    asyncio.run(_run())


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit Spot Scalper Bot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("once")
    sub.add_parser("daemon")

    bt = sub.add_parser("backtest")
    bt.add_argument("--symbol", required=True)
    bt.add_argument("--days", type=int, default=30)

    args = parser.parse_args()

    if args.cmd == "once":
        asyncio.run(run_once())
    elif args.cmd == "daemon":
        asyncio.run(run_daemon())
    elif args.cmd == "backtest":
        backtest(args.symbol, args.days)


if __name__ == "__main__":
    main()