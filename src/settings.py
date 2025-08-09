from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    bybit_api_key: Optional[str] = Field(default=None, alias="BYBIT_API_KEY")
    bybit_api_secret: Optional[str] = Field(default=None, alias="BYBIT_API_SECRET")
    bybit_env: Literal["live", "testnet"] = Field(default="live", alias="BYBIT_ENV")

    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")

    mode: Literal["paper", "live"] = Field(default="paper", alias="MODE")

    risk_per_trade: float = Field(default=0.003, alias="RISK_PER_TRADE")
    max_daily_loss: float = Field(default=0.02, alias="MAX_DAILY_LOSS")
    max_concurrent_symbols: int = Field(default=3, alias="MAX_CONCURRENT_SYMBOLS")

    screener_min_rvol: float = Field(default=1.5, alias="SCREENER_MIN_RVOL")
    screener_max_spread_bp: float = Field(default=8.0, alias="SCREENER_MAX_SPREAD_BP")
    screener_min_depth_usdt: float = Field(default=50_000.0, alias="SCREENER_MIN_DEPTH_USDT")
    rescan_minutes: int = Field(default=15, alias="RESCAN_MINUTES")
    timeframe: Literal["1m", "5m"] = Field(default="1m", alias="TIMEFRAME")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Order controls
    post_only: bool = True
    order_timeout_sec: int = 15
    max_slippage_bps: float = 10.0

    # DB path
    sqlite_path: str = "./bot_state.sqlite3"

    def is_live(self) -> bool:
        return self.mode == "live"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]