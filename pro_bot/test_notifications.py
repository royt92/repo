#!/usr/bin/env python3
"""Тест новых уведомлений Telegram"""

import asyncio
from src.notify.telegram import TelegramNotifier
from src.settings import get_settings

async def test_all_notifications():
    """Тестирует все виды уведомлений"""
    settings = get_settings()
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    
    print("🧪 Тестируем новые уведомления...")
    
    # 1. Стартовое уведомление
    print("📤 Отправляем стартовое уведомление...")
    await notifier.send_startup("live", "live", 0.001, 0.01, 5000.0)
    await asyncio.sleep(2)
    
    # 2. Периодический отчет
    print("📤 Отправляем периодический отчет...")
    scan_results = {
        "total_symbols": 500,
        "candidates": 3,
        "errors": 15,
        "best_symbol": "BTCUSDT"
    }
    
    market_analysis = {
        "btc_trend": "📈 Восходящий (EMA20>50>200)",
        "volatility": "Средняя (0.8%)",
        "volume_status": "Выше среднего (+15%)"
    }
    
    await notifier.send_periodic_report(
        balance=5125.50,
        daily_pnl=125.50,
        positions_count=1,
        scan_results=scan_results,
        market_analysis=market_analysis
    )
    await asyncio.sleep(2)
    
    # 3. Рыночная возможность
    print("📤 Отправляем анализ рыночной возможности...")
    analysis = {
        "price": 45234.56,
        "trend": "📈 EMA20>50>200 (Восходящий)",
        "rvol": 2.3,
        "score": 0.847,
        "ema20": 45180.23,
        "ema50": 44950.12,
        "ema200": 44200.88,
        "atr_percent": 0.75,
        "adx": 28.5,
        "spread": 3.2,
        "depth": 125000,
        "imbalance": 0.085
    }
    
    await notifier.send_market_opportunity("BTCUSDT", analysis)
    await asyncio.sleep(2)
    
    # 4. Обновление баланса
    print("📤 Отправляем обновление баланса...")
    await notifier.send_balance_update(
        balance=5125.50,
        available=4800.30,
        reserved=325.20,
        daily_pnl=125.50,
        total_pnl=425.50
    )
    await asyncio.sleep(2)
    
    # 5. Торговая операция
    print("📤 Отправляем уведомление о сделке...")
    await notifier.send_trade("BTCUSDT", "BUY", 0.001, 45234.56, "EMA20 пуллбэк + OB дисбаланс 8.5%")
    await asyncio.sleep(2)
    
    # 6. Закрытие позиции
    print("📤 Отправляем уведомление о закрытии...")
    await notifier.send_exit("BTCUSDT", 0.001, 45487.23, 2.52)
    await asyncio.sleep(2)
    
    # 7. Предупреждение о рисках
    print("📤 Отправляем предупреждение о рисках...")
    await notifier.send_risk_warning("Приближение к дневному лимиту потерь", -45.20, 50.00)
    
    print("✅ Все уведомления отправлены!")

if __name__ == "__main__":
    asyncio.run(test_all_notifications())



