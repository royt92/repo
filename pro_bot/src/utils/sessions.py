"""Утилиты для определения торговых сессий и времени"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any


def get_trading_session_info() -> Dict[str, Any]:
    """Получает детальную информацию о текущей торговой сессии"""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Понедельник, 6=Воскресенье
    
    # Определение сессий по московскому времени (UTC+3)
    sessions = {
        "asian": {
            "name": "🌏 Азиатская",
            "hours": (2, 11),  # 02:00-11:00 MSK (23:00-08:00 UTC предыдущего дня) 
            "emoji": "🌅",
            "activity": "Низкая",
            "description": "Токио, Сингапур, Гонконг",
            "major_pairs": ["USDJPY", "EURJPY", "GBPJPY"],
            "crypto_activity": "Умеренная"
        },
        "european": {
            "name": "🇪🇺 Европейская", 
            "hours": (9, 18),  # 09:00-18:00 MSK (06:00-15:00 UTC)
            "emoji": "🔥",
            "activity": "Высокая",
            "description": "Лондон, Франкфурт, Цюрих",
            "major_pairs": ["EURUSD", "GBPUSD", "EURGBP"],
            "crypto_activity": "Высокая"
        },
        "american": {
            "name": "🇺🇸 Американская",
            "hours": (16, 1),  # 16:00-01:00 MSK (13:00-22:00 UTC)
            "emoji": "⚡",
            "activity": "Очень высокая",
            "description": "Нью-Йорк, Чикаго",
            "major_pairs": ["EURUSD", "GBPUSD", "USDCAD"],
            "crypto_activity": "Очень высокая"
        },
        "overlap_euro_us": {
            "name": "🔥 Евро-Американский перехлест",
            "hours": (16, 18),  # 16:00-18:00 MSK
            "emoji": "💥", 
            "activity": "Экстремальная",
            "description": "Пик активности",
            "major_pairs": ["EURUSD", "GBPUSD"],
            "crypto_activity": "Экстремальная"
        }
    }
    
    # Определяем текущую сессию
    current_session = None
    
    # Проверяем перехлест Европа-США (самая активная сессия)
    if 16 <= hour < 18:
        current_session = sessions["overlap_euro_us"]
    # Американская сессия (включая переход через полночь)
    elif 16 <= hour <= 23 or 0 <= hour < 1:
        current_session = sessions["american"]
    # Европейская сессия  
    elif 9 <= hour < 16:
        current_session = sessions["european"]
    # Азиатская сессия
    elif 2 <= hour < 9:
        current_session = sessions["asian"]
    else:
        # Межсессионное время (01:00-02:00 MSK)
        current_session = {
            "name": "🌙 Межсессионная",
            "emoji": "💤",
            "activity": "Минимальная", 
            "description": "Перерыв между сессиями",
            "crypto_activity": "Низкая"
        }
    
    # Добавляем информацию о времени
    current_session["current_time"] = now.strftime("%H:%M")
    current_session["date"] = now.strftime("%Y-%m-%d")
    current_session["weekday"] = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][weekday]
    
    # Определяем статус рынка
    if weekday < 5:  # Будни
        if 9 <= hour < 21:
            market_status = "🟢 Активен"
            market_desc = "Основные торговые часы"
        else:
            market_status = "🟡 Спокойно" 
            market_desc = "Внерыночные часы"
    elif weekday == 5:  # Суббота
        market_status = "🟠 Выходной"
        market_desc = "Традиционные рынки закрыты"
    else:  # Воскресенье
        market_status = "🔴 Тихо"
        market_desc = "Минимальная активность"
    
    current_session["market_status"] = market_status
    current_session["market_description"] = market_desc
    
    return current_session


def get_next_session_info() -> Dict[str, Any]:
    """Получает информацию о следующей торговой сессии"""
    now = datetime.now()
    hour = now.hour
    
    next_sessions = []
    
    # Определяем следующие сессии
    if hour < 2:
        next_sessions.append(("🌅 Азиатская", "02:00", "через несколько часов"))
    elif hour < 9:
        next_sessions.append(("🇪🇺 Европейская", "09:00", f"через {9 - hour} ч"))
    elif hour < 16:
        next_sessions.append(("🇺🇸 Американская", "16:00", f"через {16 - hour} ч")) 
    else:
        # После 16:00 - следующая азиатская сессия завтра
        next_sessions.append(("🌅 Азиатская", "02:00", "завтра"))
    
    return {
        "next_sessions": next_sessions,
        "timezone": "MSK (UTC+3)"
    }


def get_crypto_market_analysis() -> Dict[str, Any]:
    """Анализ активности криптовалютного рынка"""
    session = get_trading_session_info()
    
    # Криптовалютный рынок работает 24/7, но есть пики активности
    crypto_analysis = {
        "is_24_7": True,
        "current_activity": session.get("crypto_activity", "Средняя"),
        "best_trading_hours": "16:00-01:00 MSK (Американская сессия)",
        "lowest_activity": "01:00-09:00 MSK (Ночные часы)",
        "weekend_note": "Выходные обычно менее волатильны"
    }
    
    # Добавляем рекомендации по времени торговли
    hour = datetime.now().hour
    if 16 <= hour <= 23 or 0 <= hour < 1:
        crypto_analysis["recommendation"] = "🔥 Отличное время для торговли"
        crypto_analysis["reason"] = "Пик активности - американская сессия"
    elif 9 <= hour < 16:
        crypto_analysis["recommendation"] = "✅ Хорошее время для торговли"
        crypto_analysis["reason"] = "Европейская сессия - высокая активность"
    elif 2 <= hour < 9:
        crypto_analysis["recommendation"] = "⚠️ Умеренная активность"
        crypto_analysis["reason"] = "Азиатская сессия - меньше волатильности"
    else:
        crypto_analysis["recommendation"] = "💤 Низкая активность"
        crypto_analysis["reason"] = "Межсессионное время"
    
    return crypto_analysis


def format_session_report() -> str:
    """Форматирует полный отчет о торговых сессиях для Telegram"""
    session = get_trading_session_info()
    next_info = get_next_session_info()
    crypto = get_crypto_market_analysis()
    
    report = f"""📊 **АНАЛИЗ ТОРГОВЫХ СЕССИЙ**

{session['emoji']} **Текущая сессия:** {session['name']}
🕐 **Время:** {session['current_time']} ({session['weekday']}, {session['date']})
📈 **Активность:** {session['activity']}
{session['market_status']} **Статус:** {session['market_description']}

🪙 **КРИПТОВАЛЮТНЫЙ РЫНОК**
🌐 Работает: 24/7 без перерывов
⚡ Текущая активность: {crypto['current_activity']}
{crypto['recommendation']} {crypto['reason']}

⏰ **РЕКОМЕНДАЦИИ ПО ВРЕМЕНИ**
🔥 Лучшее время: {crypto['best_trading_hours']}
💤 Низкая активность: {crypto['lowest_activity']}

📅 **СЛЕДУЮЩИЕ СЕССИИ**"""
    
    for session_name, time, duration in next_info['next_sessions'][:2]:
        report += f"\n{session_name}: {time} ({duration})"
    
    report += f"\n\n🌍 Часовой пояс: {next_info['timezone']}"
    
    return report



