"""Tests for logging setup."""

from __future__ import annotations

import logging

from pymagnific.core.logging import get_logger, session_log_path, setup_logging


def test_setup_logging_writes_to_log_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_logging(level=logging.DEBUG, log_dir=tmp_path / "logs", console=False, force=True)
    logger = get_logger("test")
    logger.info("hello from test")

    path = session_log_path()
    assert path is not None
    assert path.parent == tmp_path / "logs"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    assert "session log file" in content
    assert "hello from test" in content


def test_default_log_dir_is_cwd_logs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_logging(console=False, force=True)
    assert session_log_path() is not None
    assert session_log_path().parent == tmp_path / "logs"
