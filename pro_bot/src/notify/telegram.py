from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

import aiohttp

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: Optional[str], chat_id: Optional[str]) -> None:
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}" if token else None

    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, text: str) -> None:
        if not self.enabled():
            return
        assert self.base_url
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning("Telegram send failed", extra={"component": "notifier", "status": resp.status, "body": body})
        except Exception as e:
            logger.exception("Telegram send exception", extra={"component": "notifier"})

    async def send_startup(self, mode: str, bybit_env: str, risk: float, max_dd: float, balance: float = 0, max_positions: int = 0) -> None:
        mode_emoji = "📄" if mode == "paper" else "💰"
        env_emoji = "⚠️" if bybit_env == "testnet" else "🔴"
        session = self._get_trading_session()
        market = self._get_market_status()
        
        startup_msg = f"""🤖 <b>ТОРГОВЫЙ БОТ ЗАПУЩЕН</b>

{mode_emoji} <b>Режим:</b> <b>{mode.upper()}</b>
{env_emoji} <b>Среда:</b> <b>{bybit_env.upper()}</b>
💰 <b>Стартовый баланс:</b> <b>${balance:,.2f} USDT</b>

🛡️ <b>НАСТРОЙКИ РИСКА</b>
🎯 Риск на сделку: <b>{risk:.1%}</b> (${balance * risk:.2f})
🚫 Макс. дневные потери: <b>{max_dd:.1%}</b> (${balance * max_dd:.2f})
📊 Максимум позиций: <b>{max_positions if max_positions else '—'}</b>

{session['emoji']} <b>ТЕКУЩАЯ СЕССИЯ</b>
🌍 Сессия: <b>{session['name']}</b>
📈 Активность: <b>{session['activity']}</b>
{market['status']} Рынок: <b>{market['desc']}</b>

📊 <b>НАСТРОЙКИ СКРИНЕРА</b>
🔍 RVOL: <b>≥2.0x</b> (строгий отбор)
📊 Спред: <b>≤5bp</b> (высокая ликвидность)
💰 Глубина: <b>≥$100K</b>
⏱️ Сканирование: <b>каждые 10 мин</b>

⏰ <b>Время запуска:</b> <code>{self._get_current_time()}</code>

{"🟢 Готов к боевой торговле!" if mode == "live" else "🟡 Виртуальная торговля"}
📱 <b>Детальные отчеты каждые 10 минут</b>"""
        
        await self.send(startup_msg)

    async def send_candidates(self, symbols_with_notes: list[tuple[str, str]]) -> None:
        if not symbols_with_notes:
            await self.send("⚪ Кандидаты не найдены")
            return
            
        lines = ["📊 <b>ТОП КАНДИДАТЫ ДЛЯ ТОРГОВЛИ</b>\n"]
        for i, (sym, note) in enumerate(symbols_with_notes[:10], 1):
            lines.append(f"{i}. <b>{sym}</b>\n   💡 {note}\n")
        
        lines.append(f"\n🔍 Найдено кандидатов: <b>{len(symbols_with_notes)}</b>")
        lines.append(f"⏰ Сканирование: <code>{self._get_current_time()}</code>")
        
        await self.send("\n".join(lines))

    async def send_error(self, where: str, err: str) -> None:
        await self.send(f"❗️ Error at <b>{where}</b>: <code>{err}</code>")

    async def send_trade(self, symbol: str, side: str, qty: float, price: float, reason: str) -> None:
        side_emoji = "🟢" if side.upper() == "BUY" else "🔴"
        trade_msg = f"""{side_emoji} <b>НОВАЯ СДЕЛКА</b>

📊 Символ: <b>{symbol}</b>
📈 Направление: <b>{side.upper()}</b>
💰 Количество: <b>{qty:.6f}</b>
💵 Цена: <b>{price:.6f}</b>
🎯 Причина: <code>{reason}</code>

⏰ Время: <code>{self._get_current_time()}</code>"""
        await self.send(trade_msg)

    async def send_exit(self, symbol: str, qty: float, price: float, pnl: float) -> None:
        pnl_emoji = "✅" if pnl >= 0 else "❌"
        pnl_sign = "+" if pnl >= 0 else ""
        
        exit_msg = f"""{pnl_emoji} <b>ЗАКРЫТИЕ ПОЗИЦИИ</b>

📊 Символ: <b>{symbol}</b>
💰 Количество: <b>{qty:.6f}</b>
💵 Цена выхода: <b>{price:.6f}</b>

💸 PnL: <b>{pnl_sign}{pnl:.2f} USDT</b>
📊 Доходность: <b>{pnl_sign}{(pnl/abs(pnl)*100 if pnl != 0 else 0):.2f}%</b>

⏰ Время: <code>{self._get_current_time()}</code>"""
        
        await self.send(exit_msg)

    async def send_daily_summary(self, pnl_total: float, num_trades: int, win_rate: float = 0.0, volume: float = 0.0) -> None:
        pnl_emoji = "📈" if pnl_total >= 0 else "📉"
        pnl_sign = "+" if pnl_total >= 0 else ""
        
        summary_msg = f"""{pnl_emoji} <b>ДНЕВНОЙ ОТЧЕТ</b>

💰 Общий PnL: <b>{pnl_sign}{pnl_total:.2f} USDT</b>
📊 Количество сделок: <b>{num_trades}</b>
🎯 Винрейт: <b>{win_rate:.1%}</b>
📈 Объем торгов: <b>{volume:.2f} USDT</b>

⏰ Дата: <code>{self._get_current_time()}</code>"""
        
        await self.send(summary_msg)
        
    async def send_position_update(self, symbol: str, side: str, size: float, unrealized_pnl: float, entry_price: float, current_price: float) -> None:
        pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
        pnl_sign = "+" if unrealized_pnl >= 0 else ""
        
        position_msg = f"""{pnl_emoji} <b>ОБНОВЛЕНИЕ ПОЗИЦИИ</b>

📊 Символ: <b>{symbol}</b>
📈 Направление: <b>{side.upper()}</b>
💰 Размер: <b>{size:.6f}</b>
💵 Цена входа: <b>{entry_price:.6f}</b>
💵 Текущая цена: <b>{current_price:.6f}</b>

💸 Нереализованный PnL: <b>{pnl_sign}{unrealized_pnl:.2f} USDT</b>

⏰ Время: <code>{self._get_current_time()}</code>"""
        
        await self.send(position_msg)
        
    async def send_risk_warning(self, message: str, current_loss: float, max_loss: float) -> None:
        warning_msg = f"""⚠️ <b>ПРЕДУПРЕЖДЕНИЕ О РИСКАХ</b>

🚨 {message}

📉 Текущие потери: <b>{current_loss:.2f} USDT</b>
🛡️ Максимальные потери: <b>{max_loss:.2f} USDT</b>
📊 Использовано: <b>{(current_loss/max_loss*100):.1f}%</b>

⏰ Время: <code>{self._get_current_time()}</code>"""
        
        await self.send(warning_msg)
        
    def _get_current_time(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    def _get_trading_session(self) -> Dict[str, Any]:
        """Определяет текущую торговую сессию"""
        now = datetime.now()
        hour = now.hour
        
        # Определение сессий по московскому времени
        if 9 <= hour < 17:
            session = "🌏 Азиатская"
            emoji = "🌅"
            activity = "Низкая"
        elif 17 <= hour < 21:
            session = "🇪🇺 Европейская" 
            emoji = "🔥"
            activity = "Высокая"
        elif 21 <= hour < 24 or 0 <= hour < 6:
            session = "🇺🇸 Американская"
            emoji = "⚡"
            activity = "Высокая"
        else:
            session = "🌙 Межсессионная"
            emoji = "💤"
            activity = "Очень низкая"
            
        return {
            "name": session,
            "emoji": emoji, 
            "activity": activity,
            "time": now.strftime("%H:%M")
        }
        
    def _get_market_status(self) -> Dict[str, str]:
        """Определяет статус рынка"""
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=Понедельник, 6=Воскресенье
        
        # Криптовалютный рынок работает 24/7
        if weekday < 5:  # Будни
            if 9 <= hour < 21:
                return {"status": "🟢 Активен", "desc": "Основные сессии"}
            else:
                return {"status": "🟡 Спокойно", "desc": "Низкая активность"}
        elif weekday == 5:  # Суббота
            return {"status": "🟠 Выходной", "desc": "Традиционные рынки закрыты"}
        else:  # Воскресенье
            return {"status": "🔴 Тихо", "desc": "Минимальная активность"}
            
    async def send_periodic_report(self, balance: float, daily_pnl: float, positions_count: int, 
                                 scan_results: Dict[str, Any], market_analysis: Dict[str, Any]) -> None:
        """Отправляет периодический отчет каждые 10 минут"""
        session = self._get_trading_session()
        market = self._get_market_status()
        
        # Эмодзи для PnL
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
        pnl_sign = "+" if daily_pnl >= 0 else ""
        
        # Процент дневного PnL
        pnl_percent = (daily_pnl / balance * 100) if balance > 0 else 0
        
        # Статус торговли
        trading_status = "🟢 Активен" if positions_count > 0 else "🔍 Поиск сигналов"
        
        report = f"""📊 <b>ПЕРИОДИЧЕСКИЙ ОТЧЕТ</b>

{session['emoji']} <b>Торговая сессия:</b> {session['name']}
📍 <b>Активность рынка:</b> {session['activity']}
{market['status']} <b>Статус рынка:</b> {market['desc']}

💰 <b>ФИНАНСЫ</b>
💵 Баланс: <b>${balance:,.2f} USDT</b>
{pnl_emoji} Дневной PnL: <b>{pnl_sign}${daily_pnl:.2f}</b> ({pnl_sign}{pnl_percent:.2f}%)
📊 Активных позиций: <b>{positions_count}</b>
🎯 Статус: <b>{trading_status}</b>

🔍 <b>СКАНИРОВАНИЕ РЫНКА</b>
📈 Проанализировано: <b>{scan_results.get('total_symbols', 0)}</b> символов
⭐ Найдено кандидатов: <b>{scan_results.get('candidates', 0)}</b>
⚠️ Ошибок подключения: <b>{scan_results.get('errors', 0)}</b>
🎯 Лучший кандидат: <b>{scan_results.get('best_symbol', 'Нет')}</b>

📊 <b>АНАЛИЗ РЫНКА</b>
📈 BTC тренд: <b>{market_analysis.get('btc_trend', 'Неизвестно')}</b>
⚡ Волатильность: <b>{market_analysis.get('volatility', 'Средняя')}</b>
🌊 Объемы: <b>{market_analysis.get('volume_status', 'Нормальные')}</b>

🛡️ <b>РИСК-МЕНЕДЖМЕНТ</b>
🎯 Риск на сделку: <b>0.1%</b> ($<b>{balance * 0.001:.2f}</b>)
🚫 Макс. дневные потери: <b>1%</b> ($<b>{balance * 0.01:.2f}</b>)
📊 Использовано лимита: <b>{abs(daily_pnl) / (balance * 0.01) * 100:.1f}%</b>

⏰ <b>Время:</b> <code>{self._get_current_time()}</code>
🔄 <b>Следующий отчет:</b> через 10 минут"""
        
        await self.send(report)
        
    async def send_market_opportunity(self, symbol: str, analysis: Dict[str, Any]) -> None:
        """Уведомление о рыночной возможности"""
        session = self._get_trading_session()
        
        opportunity_msg = f"""🎯 <b>РЫНОЧНАЯ ВОЗМОЖНОСТЬ</b>

{session['emoji']} <b>Сессия:</b> {session['name']} ({session['time']})

📊 <b>Символ:</b> <b>{symbol}</b>
💰 <b>Цена:</b> <b>${analysis.get('price', 0):.6f}</b>
📈 <b>Тренд:</b> <b>{analysis.get('trend', 'Анализ...')}</b>
⚡ <b>RVOL:</b> <b>{analysis.get('rvol', 0):.2f}x</b>
🎯 <b>Score:</b> <b>{analysis.get('score', 0):.3f}</b>

📊 <b>ТЕХНИЧЕСКИЙ АНАЛИЗ</b>
📈 EMA20: <b>${analysis.get('ema20', 0):.6f}</b>
📊 EMA50: <b>${analysis.get('ema50', 0):.6f}</b>
📉 EMA200: <b>${analysis.get('ema200', 0):.6f}</b>
⚡ ATR: <b>{analysis.get('atr_percent', 0):.2f}%</b>
🔄 ADX: <b>{analysis.get('adx', 0):.1f}</b>

💹 <b>ЛИКВИДНОСТЬ</b>
📊 Спред: <b>{analysis.get('spread', 0):.1f} bp</b>
🌊 Глубина: <b>${analysis.get('depth', 0):,.0f}</b>
📈 Bid/Ask баланс: <b>{analysis.get('imbalance', 0):.1%}</b>

⏰ <b>Время:</b> <code>{self._get_current_time()}</code>
🔍 <b>Статус:</b> Мониторинг продолжается..."""
        
        await self.send(opportunity_msg)
        
    async def send_balance_update(self, balance: float, available: float, reserved: float, 
                                daily_pnl: float, total_pnl: float) -> None:
        """Детальное обновление баланса"""
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
        total_emoji = "🚀" if total_pnl >= 0 else "📉"
        pnl_sign = "+" if daily_pnl >= 0 else ""
        total_sign = "+" if total_pnl >= 0 else ""
        
        balance_msg = f"""💰 <b>ОБНОВЛЕНИЕ БАЛАНСА</b>

💵 <b>Общий баланс:</b> <b>${balance:,.2f} USDT</b>
✅ <b>Доступно:</b> <b>${available:,.2f} USDT</b>
🔒 <b>В позициях:</b> <b>${reserved:,.2f} USDT</b>

{pnl_emoji} <b>Дневной PnL:</b> <b>{pnl_sign}${daily_pnl:.2f}</b> ({pnl_sign}{daily_pnl/balance*100:.2f}%)
{total_emoji} <b>Общий PnL:</b> <b>{total_sign}${total_pnl:.2f}</b> ({total_sign}{total_pnl/balance*100:.2f}%)

🛡️ <b>РИСКИ</b>
🎯 <b>Риск на сделку:</b> <b>${balance * 0.001:.2f}</b> (0.1%)
🚫 <b>Макс. дневные потери:</b> <b>${balance * 0.01:.2f}</b> (1%)
📊 <b>Использовано лимита:</b> <b>{abs(daily_pnl) / (balance * 0.01) * 100:.1f}%</b>

⏰ <b>Время:</b> <code>{self._get_current_time()}</code>"""
        
        await self.send(balance_msg)