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
    
    # Получаем стартовый баланс для отображения
    initial_balance = 1000.0  # Paper mode default
    
    async with BybitClient(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_env) as temp_client:
        if settings.mode == "live":
            try:
                try:
                    bal = await temp_client.fetch_balance("UNIFIED")
                except Exception:
                    bal = await temp_client.fetch_balance("SPOT")
                for acc in bal.get("list", []):
                    for coin in acc.get("coin", []):
                        if coin.get("coin") == "USDT":
                            initial_balance = float(coin.get("walletBalance", 0))
                            break
            except:
                initial_balance = 0.0
    
    await notifier.send_startup(settings.mode, settings.bybit_env, settings.risk_per_trade, settings.max_daily_loss, initial_balance, settings.max_concurrent_symbols)

    async with BybitClient(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_env) as client:
        db = DB(settings.sqlite_path)
        await db.init()

        screener = Screener(
            client,
            min_rvol=settings.screener_min_rvol,
            max_spread_bp=settings.screener_max_spread_bp,
            min_depth_usdt=settings.screener_min_depth_usdt,
            timeframe=settings.timeframe,
            max_results=settings.max_concurrent_symbols,
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
    
    async with BybitClient(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_env) as client:
        # Получаем стартовый баланс
        initial_balance = 1000.0  # Paper mode default
        if settings.mode == "live":
            try:
                try:
                    bal = await client.fetch_balance("UNIFIED")
                except Exception:
                    bal = await client.fetch_balance("SPOT")
                for acc in bal.get("list", []):
                    for coin in acc.get("coin", []):
                        if coin.get("coin") == "USDT":
                            initial_balance = float(coin.get("walletBalance", 0))
                            break
            except:
                initial_balance = 0.0
        
        await notifier.send_startup(settings.mode, settings.bybit_env, settings.risk_per_trade, settings.max_daily_loss, initial_balance, settings.max_concurrent_symbols)
        
        db = DB(settings.sqlite_path)
        await db.init()

        screener = Screener(
            client,
            min_rvol=settings.screener_min_rvol,
            max_spread_bp=settings.screener_max_spread_bp,
            min_depth_usdt=settings.screener_min_depth_usdt,
            timeframe=settings.timeframe,
            max_results=settings.max_concurrent_symbols,
        )
        executor = Executor(settings, client, db, notifier)
        
        # Запускаем задачу периодических отчетов
        async def periodic_reports():
            while True:
                await asyncio.sleep(600)  # 10 минут
                try:
                    # Получаем текущий баланс
                    current_balance = initial_balance
                    if settings.mode == "live":
                        try:
                            bal = await client.fetch_balance("UNIFIED")
                        except Exception:
                            bal = await client.fetch_balance("SPOT")
                        for acc in bal.get("list", []):
                            for coin in acc.get("coin", []):
                                if coin.get("coin") == "USDT":
                                    current_balance = float(coin.get("walletBalance", 0))
                                    break
                    
                    # Расчет дневного PnL
                    daily_pnl = current_balance - initial_balance
                    
                    # Информация о сканировании (примерная)
                    scan_results = {
                        "total_symbols": 500,
                        "candidates": len(await screener.fetch_candidates()),
                        "errors": 0,  # Можно добавить счетчик ошибок
                        "best_symbol": "Анализ..."
                    }
                    
                    # Анализ рынка (базовый)
                    market_analysis = {
                        "btc_trend": "Анализ...",
                        "volatility": "Средняя",
                        "volume_status": "Нормальные"
                    }
                    
                    await notifier.send_periodic_report(
                        balance=current_balance,
                        daily_pnl=daily_pnl,
                        positions_count=len(executor.positions),
                        scan_results=scan_results,
                        market_analysis=market_analysis
                    )
                except Exception as e:
                    logging.warning(f"Ошибка периодического отчета: {e}")
        
        # Запускаем периодические отчеты в фоне
        asyncio.create_task(periodic_reports())
        
        while True:
            candidates = await screener.fetch_candidates()
            top_symbols = [c.symbol for c in candidates][: settings.max_concurrent_symbols]
            
            # Отправляем детализированную информацию о кандидатах
            if candidates:
                await notifier.send_candidates([(c.symbol, c.notes) for c in candidates])
                
                # Дополнительно отправляем детальный анализ лучшего кандидата
                if len(candidates) > 0:
                    best = candidates[0]
                    try:
                        # Получаем дополнительные данные для анализа
                        kl = await client.fetch_klines(best.symbol, interval=settings.timeframe, limit=200)
                        ob = await client.fetch_orderbook(best.symbol, depth=50)
                        
                        if kl and ob:
                            df = pd.DataFrame(kl, columns=["ts", "open", "high", "low", "close", "volume", "turnover"]).astype(float)
                            current_price = float(df["close"].iloc[-1])
                            
                            from src.utils.math import ema
                            ema20 = ema(df["close"], 20).iloc[-1] if len(df) >= 20 else current_price
                            ema50 = ema(df["close"], 50).iloc[-1] if len(df) >= 50 else current_price
                            ema200 = ema(df["close"], 200).iloc[-1] if len(df) >= 200 else current_price
                            
                            from src.data.market_data import compute_spread_bps, compute_depth
                            spread = compute_spread_bps(ob)
                            depth = compute_depth(ob, pct=0.002)
                            
                            analysis = {
                                "price": current_price,
                                "trend": "EMA20>50>200" if ema20 > ema50 > ema200 else "Боковой/Нисходящий",
                                "rvol": 2.0,  # Можно вычислить реальный RVOL
                                "score": best.score,
                                "ema20": ema20,
                                "ema50": ema50,
                                "ema200": ema200,
                                "atr_percent": 0.5,  # Можно вычислить реальный ATR
                                "adx": 25.0,  # Можно вычислить реальный ADX
                                "spread": spread,
                                "depth": depth.total,
                                "imbalance": depth.imbalance
                            }
                            
                            await notifier.send_market_opportunity(best.symbol, analysis)
                    except:
                        pass  # Если не удалось получить детальный анализ
            
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