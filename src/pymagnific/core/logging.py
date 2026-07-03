"""Structured logging setup for pymagnific."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

_configured = False
_session_log_path: Path | None = None

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def session_log_path() -> Path | None:
    """Path to the log file for the current CLI session, if configured."""
    return _session_log_path


def default_log_dir() -> Path:
    """Default log directory: ./logs relative to current working directory."""
    return Path.cwd() / "logs"


def setup_logging(
    *,
    level: int = logging.INFO,
    log_dir: Path | None = None,
    console: bool = True,
    force: bool = False,
) -> logging.Logger:
    """Configure pymagnific logger with file (+ optional stderr) handlers."""
    global _configured, _session_log_path

    logger = logging.getLogger("pymagnific")
    if _configured and not force:
        return logger

    if force:
        logger.handlers.clear()

    target_dir = (log_dir or default_log_dir()).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    _session_log_path = target_dir / f"pymagnific-{stamp}.log"

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = logging.FileHandler(_session_log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(level)
        logger.addHandler(stream_handler)

    logger.setLevel(level)
    logger.propagate = False
    _configured = True
    logger.info("session log file: %s", _session_log_path)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the pymagnific namespace."""
    if name is None or name == "pymagnific":
        return logging.getLogger("pymagnific")
    if name.startswith("pymagnific."):
        return logging.getLogger(name)
    return logging.getLogger(f"pymagnific.{name}")
