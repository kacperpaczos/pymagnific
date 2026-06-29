"""Magnific REST API rate limiting and automatic warnings."""

from __future__ import annotations

import json
import sys
import time
import warnings
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Any

from pymagnific.core.config import get_settings
from pymagnific.core.exceptions import MagnificRateLimitExceeded

RPM_LIMIT = 50
BURST_LIMIT = 50
BURST_WINDOW_S = 5.0
AVG_RPS_LIMIT = 10.0
AVG_WINDOW_S = 120.0
WARNING_RATIO = 0.8

RPD_LIMITS: dict[str, int] = {
    "/v1/ai/image-to-prompt": 1000,
    "/v1/ai/improve-prompt": 1000,
    "/v1/analytics/": 100,
}

for _prefix in ("/v1/ai/powered-search", "/v1/resources"):
    RPD_LIMITS.setdefault(_prefix, 1000)


@dataclass
class RateLimitSnapshot:
    rpm_used: int
    rpm_limit: int
    burst_used: int
    burst_limit: int
    avg_rps: float
    avg_rps_limit: float
    warnings: list[str] = field(default_factory=list)


class MagnificRateLimitWarning(UserWarning):
    """Approaching Magnific API rate limits."""


class MagnificRateLimiter:
    """Thread-safe client-side limiter for Magnific REST API."""

    def __init__(
        self,
        *,
        rpm_limit: int = RPM_LIMIT,
        burst_limit: int = BURST_LIMIT,
        burst_window_s: float = BURST_WINDOW_S,
        avg_rps_limit: float = AVG_RPS_LIMIT,
        avg_window_s: float = AVG_WINDOW_S,
        warning_ratio: float = WARNING_RATIO,
        rpd_limits: dict[str, int] | None = None,
        usage_path: Path | None = None,
    ) -> None:
        self.rpm_limit = rpm_limit
        self.burst_limit = burst_limit
        self.burst_window_s = burst_window_s
        self.avg_rps_limit = avg_rps_limit
        self.avg_window_s = avg_window_s
        self.warning_ratio = warning_ratio
        self.rpd_limits = rpd_limits or dict(RPD_LIMITS)
        self._usage_path = usage_path or get_settings().rate_usage_path()

        self._lock = Lock()
        self._minute: deque[float] = deque()
        self._burst: deque[float] = deque()
        self._avg: deque[float] = deque()
        self._warned: set[str] = set()

    def _prune(self, window: deque[float], horizon_s: float, now: float) -> None:
        cutoff = now - horizon_s
        while window and window[0] < cutoff:
            window.popleft()

    def _load_rpd(self) -> dict[str, Any]:
        if not self._usage_path.is_file():
            return {"date": date.today().isoformat(), "endpoints": {}}
        try:
            data = json.loads(self._usage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"date": date.today().isoformat(), "endpoints": {}}
        if data.get("date") != date.today().isoformat():
            return {"date": date.today().isoformat(), "endpoints": {}}
        return data

    def _save_rpd(self, data: dict[str, Any]) -> None:
        self._usage_path.parent.mkdir(parents=True, exist_ok=True)
        self._usage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._usage_path.chmod(0o600)

    def _rpd_key(self, path: str) -> str | None:
        for prefix, limit in self.rpd_limits.items():
            if path.startswith(prefix):
                return prefix
        return None

    def _emit_warning(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        warnings.warn(message, MagnificRateLimitWarning, stacklevel=4)
        print(f"[pymagnific rate-limit] {message}", file=sys.stderr)

    def snapshot(self) -> RateLimitSnapshot:
        now = time.monotonic()
        with self._lock:
            self._prune(self._minute, 60.0, now)
            self._prune(self._burst, self.burst_window_s, now)
            self._prune(self._avg, self.avg_window_s, now)
            avg_rps = len(self._avg) / self.avg_window_s if self._avg else 0.0
            warns = list(self._collect_warnings(now, avg_rps, check_only=True))
        return RateLimitSnapshot(
            rpm_used=len(self._minute),
            rpm_limit=self.rpm_limit,
            burst_used=len(self._burst),
            burst_limit=self.burst_limit,
            avg_rps=round(avg_rps, 2),
            avg_rps_limit=self.avg_rps_limit,
            warnings=warns,
        )

    def _collect_warnings(
        self, now: float, avg_rps: float, *, check_only: bool = False
    ) -> list[str]:
        msgs: list[str] = []
        rpm_used = len(self._minute)
        burst_used = len(self._burst)

        if rpm_used >= self.rpm_limit * self.warning_ratio:
            msgs.append(
                f"RPM {rpm_used}/{self.rpm_limit} (Magnific limit: 50 requests/minute per API key)"
            )
        if burst_used >= self.burst_limit * self.warning_ratio:
            msgs.append(
                f"Burst {burst_used}/{self.burst_limit} in {self.burst_window_s:.0f}s "
                f"(Magnific limit: 50 req / 5s per IP)"
            )
        if avg_rps >= self.avg_rps_limit * self.warning_ratio:
            msgs.append(
                f"Avg {avg_rps:.1f}/{self.avg_rps_limit:.0f} req/s over "
                f"{self.avg_window_s:.0f}s (Magnific limit: 10 req/s per IP)"
            )

        rpd = self._load_rpd()
        for prefix, limit in self.rpd_limits.items():
            used = int(rpd.get("endpoints", {}).get(prefix, 0))
            if used >= limit * self.warning_ratio:
                msgs.append(f"Daily {prefix}: {used}/{limit} RPD")

        if not check_only:
            for msg in msgs:
                self._emit_warning(f"warn-{hash(msg)}", msg)
        return msgs

    def acquire(self, path: str = "") -> None:
        while True:
            wait_s = 0.0
            with self._lock:
                now = time.monotonic()
                self._prune(self._minute, 60.0, now)
                self._prune(self._burst, self.burst_window_s, now)
                self._prune(self._avg, self.avg_window_s, now)

                avg_rps = len(self._avg) / self.avg_window_s if self._avg else 0.0
                self._collect_warnings(now, avg_rps)

                if len(self._minute) >= self.rpm_limit:
                    wait_s = max(wait_s, 60.0 - (now - self._minute[0]) + 0.05)
                if len(self._burst) >= self.burst_limit:
                    wait_s = max(wait_s, self.burst_window_s - (now - self._burst[0]) + 0.05)
                max_avg_count = int(self.avg_rps_limit * self.avg_window_s)
                if len(self._avg) >= max_avg_count:
                    wait_s = max(wait_s, self._avg[0] + self.avg_window_s - now + 0.05)

                rpd_key = self._rpd_key(path)
                if rpd_key:
                    rpd = self._load_rpd()
                    used = int(rpd.get("endpoints", {}).get(rpd_key, 0))
                    limit = self.rpd_limits[rpd_key]
                    if used >= limit:
                        raise MagnificRateLimitExceeded(
                            f"Daily limit reached for {rpd_key}: {used}/{limit} RPD. "
                            "Resets at midnight UTC."
                        )

                if wait_s <= 0:
                    stamp = time.monotonic()
                    self._minute.append(stamp)
                    self._burst.append(stamp)
                    self._avg.append(stamp)
                    if rpd_key:
                        rpd = self._load_rpd()
                        endpoints = rpd.setdefault("endpoints", {})
                        endpoints[rpd_key] = int(endpoints.get(rpd_key, 0)) + 1
                        self._save_rpd(rpd)
                    return

            time.sleep(min(wait_s, 2.0))

    def note_rate_limited_response(self, retry_after_s: float | None = None) -> float:
        wait = retry_after_s if retry_after_s and retry_after_s > 0 else 60.0
        self._emit_warning(
            "http-429",
            f"Magnific API returned 429 Too Many Requests. Waiting {wait:.0f}s before retry.",
        )
        return wait

    def reset_warnings(self) -> None:
        self._warned.clear()


_default_limiter: MagnificRateLimiter | None = None


def get_rate_limiter() -> MagnificRateLimiter:
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = MagnificRateLimiter()
    return _default_limiter


def parse_retry_after(header_value: str | None) -> float | None:
    if not header_value:
        return None
    try:
        return float(header_value.strip())
    except ValueError:
        return None
