"""统一日志格式。"""
from __future__ import annotations

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG if settings.env == "dev" and "--debug" in sys.argv else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    for noisy in ("httpx", "httpx2", "httpcore", "openai", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
