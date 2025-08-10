import json
import logging
import logging.handlers
import os
from typing import Optional

from pythonjsonlogger import jsonlogger


def _default_log_path() -> str:
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "bot.log")


class ExtraFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if not hasattr(record, "component"):
            record.component = "root"  # type: ignore[attr-defined]
        return True


def setup_logging(level: str = "INFO", log_file_path: Optional[str] = None) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate logs on reload
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(component)s %(message)s",
        json_default=_json_default,
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(numeric_level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(ExtraFilter())

    file_path = log_file_path or _default_log_path()
    rotating = logging.handlers.RotatingFileHandler(
        file_path, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    rotating.setLevel(numeric_level)
    rotating.setFormatter(formatter)
    rotating.addFilter(ExtraFilter())

    root.addHandler(stream_handler)
    root.addHandler(rotating)


def _json_default(obj):
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"