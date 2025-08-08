from __future__ import annotations

import requests


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, dry_run: bool = True, force_send: bool = False) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.force_send = force_send
        self.dry_run = dry_run and not force_send
        self._base = f"https://api.telegram.org/bot{bot_token}" if bot_token else ""

    def send_message(self, text: str, disable_web_page_preview: bool = True) -> None:
        # Always mirror to console for visibility
        print(f"[TELEGRAM] {text}")
        if self.dry_run or not (self.bot_token and self.chat_id):
            return
        try:
            url = f"{self._base}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "disable_web_page_preview": disable_web_page_preview}
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[TELEGRAM-ERR] {e}")