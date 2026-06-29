"""pymagnific exception hierarchy."""

from __future__ import annotations

from typing import Any


class PymagnificError(Exception):
    """Base error for pymagnific."""


class ConfigError(PymagnificError):
    """Missing or invalid configuration."""


class MagnificRestError(PymagnificError):
    def __init__(self, status: int, body: Any, *, retry_after: float | None = None):
        self.status = status
        self.body = body
        self.retry_after = retry_after
        super().__init__(f"HTTP {status}: {body}")


class MagnificRateLimitExceeded(PymagnificError):
    """Daily or hard client-side rate limit exceeded."""


class MagnificMcpError(PymagnificError):
    """MCP tool call failed."""


class AuthError(PymagnificError):
    """OAuth / authentication error."""


class AssetsError(PymagnificError):
    """Space asset export/import error."""
