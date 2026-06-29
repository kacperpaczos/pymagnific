"""Rate limiter tests."""

import time
from datetime import date

import pytest

from pymagnific.clients.rate_limit import (
    MagnificRateLimiter,
    MagnificRateLimitExceeded,
    parse_retry_after,
)


def test_parse_retry_after():
    assert parse_retry_after("30") == 30.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("invalid") is None


def test_rpm_throttle(tmp_path):
    limiter = MagnificRateLimiter(
        rpm_limit=3,
        burst_limit=100,
        avg_rps_limit=1000,
        usage_path=tmp_path / "usage.json",
    )
    for _ in range(3):
        limiter.acquire("/v1/ai/apps")
    start = time.monotonic()
    limiter.acquire("/v1/ai/apps")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.04


def test_daily_limit_blocks(tmp_path):
    usage = tmp_path / "usage.json"
    usage.write_text(
        f'{{"date": "{date.today().isoformat()}", "endpoints": {{"/v1/ai/improve-prompt": 1000}}}}',
        encoding="utf-8",
    )
    limiter = MagnificRateLimiter(usage_path=usage)
    with pytest.raises(MagnificRateLimitExceeded):
        limiter.acquire("/v1/ai/improve-prompt/foo")


def test_warning_near_limit():
    limiter = MagnificRateLimiter(rpm_limit=10, burst_limit=100, avg_rps_limit=1000)
    for _ in range(8):
        limiter.acquire("/v1/ai/apps")
    snap = limiter.snapshot()
    assert snap.rpm_used == 8
    assert any("RPM" in w for w in snap.warnings)
