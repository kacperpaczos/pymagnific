"""Apps service - REST Apps/Flows orchestration."""

from __future__ import annotations

from typing import Any

from pymagnific.clients.magnific_rest import MagnificRestClient
from pymagnific.core.config import Settings, get_settings


class AppsService:
    def __init__(
        self,
        rest: MagnificRestClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._rest = rest or MagnificRestClient(settings=self._settings)

    def rate_limit_status(self) -> dict[str, Any]:
        return self._rest.rate_limit_status()

    async def probe(self) -> dict[str, Any]:
        result = await self._rest.probe()
        result["rate_limits"] = self._rest.rate_limit_status()
        return result

    async def list_apps(self, *, page: int = 1, per_page: int = 25) -> Any:
        return await self._rest.list_apps(page=page, per_page=per_page)

    async def get_app(self, app_id: str) -> Any:
        return await self._rest.get_app(app_id)

    async def run_app(
        self,
        app_id: str,
        inputs: dict[str, Any],
        *,
        webhook: str | None = None,
    ) -> dict[str, Any]:
        wh = webhook or self._settings.webhook_url
        return await self._rest.run_app(app_id, inputs, webhook=wh)

    async def poll_run(self, run_id: str) -> Any:
        return await self._rest.poll_run(run_id)
