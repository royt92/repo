from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_unix_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def from_unix_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def minutes_ago(minutes: int) -> datetime:
    return utc_now() - timedelta(minutes=minutes)


def hours_ago(hours: int) -> datetime:
    return utc_now() - timedelta(hours=hours)