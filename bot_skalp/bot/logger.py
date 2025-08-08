import logging
import sys


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("bot")
    if logger.handlers:
        # already configured
        logger.setLevel(level)
        return logger
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger