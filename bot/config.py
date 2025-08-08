import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


def _parse_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_list_of_floats(value: str, default: List[float]) -> List[float]:
    if not value:
        return default
    parts = [p.strip() for p in value.split(",") if p.strip()]
    result: List[float] = []
    for p in parts:
        try:
            result.append(float(p))
        except ValueError:
            continue
    return result or default


@dataclass
class Settings:
    env: str
    dry_run: bool
    bybit_api_key: str
    bybit_api_secret: str
    bybit_subaccount: str
    use_testnet: bool
    http_proxy: str
    https_proxy: str
    telegram_bot_token: str
    telegram_chat_id: str
    quote_asset: str
    base_budget_usd: float
    max_concurrent_positions: int
    risk_per_trade_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    dca_levels: int
    dca_step_pcts: List[float]
    timeframe: str
    screen_top_n: int
    loop_sleep_seconds: int


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        env=os.getenv("ENV", "dev"),
        dry_run=_parse_bool(os.getenv("DRY_RUN", "true"), True),
        bybit_api_key=os.getenv("BYBIT_API_KEY", ""),
        bybit_api_secret=os.getenv("BYBIT_API_SECRET", ""),
        bybit_subaccount=os.getenv("BYBIT_SUBACCOUNT", ""),
        use_testnet=_parse_bool(os.getenv("USE_TESTNET", "false"), False),
        http_proxy=os.getenv("HTTP_PROXY", ""),
        https_proxy=os.getenv("HTTPS_PROXY", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        quote_asset=os.getenv("QUOTE_ASSET", "USDT").upper(),
        base_budget_usd=_parse_float(os.getenv("BASE_BUDGET_USD", "1000"), 1000.0),
        max_concurrent_positions=_parse_int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"), 3),
        risk_per_trade_pct=_parse_float(os.getenv("RISK_PER_TRADE_PCT", "1.0"), 1.0),
        take_profit_pct=_parse_float(os.getenv("TAKE_PROFIT_PCT", "0.6"), 0.6),
        stop_loss_pct=_parse_float(os.getenv("STOP_LOSS_PCT", "2.0"), 2.0),
        dca_levels=_parse_int(os.getenv("DCA_LEVELS", "2"), 2),
        dca_step_pcts=_parse_list_of_floats(os.getenv("DCA_STEP_PCTS", "1.5,3.5"), [1.5, 3.5]),
        timeframe=os.getenv("TIMEFRAME", "1m"),
        screen_top_n=_parse_int(os.getenv("SCREEN_TOP_N", "20"), 20),
        loop_sleep_seconds=_parse_int(os.getenv("LOOP_SLEEP_SECONDS", "30"), 30),
    )