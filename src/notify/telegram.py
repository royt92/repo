from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

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

    async def send_startup(self, mode: str, bybit_env: str, risk: float, max_dd: float) -> None:
        await self.send(
            f"🚀 Bot started\nMode: <b>{mode}</b>\nEnv: <b>{bybit_env}</b>\nRisk/Trade: <b>{risk:.4f}</b>\nMaxDailyLoss: <b>{max_dd:.4f}</b>"
        )

    async def send_candidates(self, symbols_with_notes: list[tuple[str, str]]) -> None:
        lines = ["📊 Top candidates:"]
        for sym, note in symbols_with_notes:
            lines.append(f"• <b>{sym}</b> — {note}")
        await self.send("\n".join(lines))

    async def send_error(self, where: str, err: str) -> None:
        await self.send(f"❗️ Error at <b>{where}</b>: <code>{err}</code>")

    async def send_trade(self, symbol: str, side: str, qty: float, price: float, reason: str) -> None:
        await self.send(f"🟢 Trade {side} {symbol} qty={qty:.6f} @ {price:.6f}\nReason: {reason}")

    async def send_exit(self, symbol: str, qty: float, price: float, pnl: float) -> None:
        emoji = "✅" if pnl >= 0 else "🔻"
        await self.send(f"{emoji} Exit {symbol} qty={qty:.6f} @ {price:.6f} PnL={pnl:.2f} USDT")

    async def send_daily_summary(self, pnl_total: float, num_trades: int) -> None:
        emoji = "📈" if pnl_total >= 0 else "📉"
        await self.send(f"{emoji} Daily PnL: {pnl_total:.2f} USDT, trades: {num_trades}")