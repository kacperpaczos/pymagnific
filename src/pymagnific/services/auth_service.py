"""Auth service - device login and status."""

from __future__ import annotations

from typing import Any

from mcp.shared.auth import OAuthToken

from pymagnific.clients.auth import device_login, mcp_auth
from pymagnific.clients.auth.token_storage import FileTokenStorage
from pymagnific.core.config import Settings, get_settings


class AuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._storage = FileTokenStorage(settings=self._settings)

    @property
    def token_path(self):
        return self._settings.oauth_token_path()

    async def login(self, *, open_browser: bool = True) -> OAuthToken:
        return await device_login.login(
            open_browser=open_browser,
            settings=self._settings,
            storage=self._storage,
        )

    async def status(self) -> dict[str, Any]:
        return await mcp_auth.auth_status(settings=self._settings, storage=self._storage)
