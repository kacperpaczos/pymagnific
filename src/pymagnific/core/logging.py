"""Structured logging setup for pymagnific."""

from __future__ import annotations

import logging
import sys


def setup_logging(*, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("pymagnific")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "pymagnific")
