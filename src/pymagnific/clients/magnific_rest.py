"""Magnific REST API client (x-magnific-api-key) - async."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from pymagnific.clients.rate_limit import get_rate_limiter, parse_retry_after
from pymagnific.core.config import MAGNIFIC_API_BASE, Settings, get_settings
from pymagnific.core.exceptions import MagnificRestError


class MagnificRestClient:
    def __init__(
        self,
        key: str | None = None,
        *,
        settings: Settings | None = None,
        timeout: float | None = None,
        rate_limit: bool = True,
        max_retries: int = 2,
    ):
        self._settings = settings or get_settings()
        self._key = key or self._settings.require_api_key()
        self._timeout = timeout if timeout is not None else self._settings.rest_timeout
        self._rate_limit = rate_limit
        self._max_retries = max_retries
        self._limiter = get_rate_limiter()

    def rate_limit_status(self) -> dict[str, Any]:
        snap = self._limiter.snapshot()
        return {
            "rpm": f"{snap.rpm_used}/{snap.rpm_limit}",
            "burst_5s": f"{snap.burst_used}/{snap.burst_limit}",
            "avg_rps_2m": f"{snap.avg_rps}/{snap.avg_rps_limit}",
            "warnings": snap.warnings,
            "docs": "https://docs.magnific.com (50 RPM/key, 50/5s burst, 10 rps avg)",
        }

    def _headers(self) -> dict[str, str]:
        return {
            "x-magnific-api-key": self._key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        url = f"{MAGNIFIC_API_BASE}{path}"
        last_error: MagnificRestError | None = None

        for attempt in range(self._max_retries + 1):
            if self._rate_limit:
                self._limiter.acquire(path)

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(
                    method, url, headers=self._headers(), json=json, params=params
                )

            if resp.status_code == 429 and attempt < self._max_retries:
                retry_after = parse_retry_after(resp.headers.get("Retry-After"))
                wait = self._limiter.note_rate_limited_response(retry_after)
                await asyncio.sleep(wait)
                continue

            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                last_error = MagnificRestError(
                    resp.status_code,
                    body,
                    retry_after=parse_retry_after(resp.headers.get("Retry-After")),
                )
                raise last_error

            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()

        if last_error:
            raise last_error
        raise RuntimeError("Request failed after retries")

    async def probe(self) -> dict[str, Any]:
        result: dict[str, Any] = {"api_key_valid": False, "apps": None, "errors": []}
        try:
            apps = await self.list_apps()
            result["api_key_valid"] = True
            result["apps"] = apps
        except MagnificRestError as e:
            result["errors"].append(
                {"endpoint": "GET /v1/ai/apps", "status": e.status, "body": e.body}
            )
        return result

    async def list_apps(self, *, page: int = 1, per_page: int = 25) -> Any:
        return await self._request(
            "GET",
            "/v1/ai/apps",
            params={"page": page, "perPage": per_page},
        )

    async def get_app(self, app_id: str) -> Any:
        return await self._request("GET", f"/v1/ai/apps/{app_id}")

    async def run_app(
        self,
        app_id: str,
        inputs: dict[str, Any],
        *,
        webhook: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"inputs": inputs}
        if webhook:
            body["webhook"] = webhook
        return await self._request("POST", f"/v1/ai/apps/{app_id}/run", json=body)

    async def get_run(self, run_id: str) -> Any:
        return await self._request("GET", f"/v1/ai/apps/runs/{run_id}")

    async def poll_run(
        self,
        run_id: str,
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
    ) -> Any:
        if interval < 1.2 and self._rate_limit:
            import warnings

            warnings.warn(
                "poll interval < 1.2s may exceed Magnific 50 RPM limit with other calls",
                stacklevel=2,
            )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = await self.get_run(run_id)
            status = (data or {}).get("status", "").lower()
            if status in ("finished", "failed", "completed", "error"):
                return data
            await asyncio.sleep(interval)
        raise TimeoutError(f"Run {run_id} did not finish within {timeout}s")
