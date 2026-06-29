"""File-backed OAuth token storage for MCP SDK."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from pymagnific.core.config import Settings, get_settings


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    path.chmod(0o600)


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class FileTokenStorage:
    """Implements mcp.client.auth.TokenStorage protocol."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        token_path: Path | None = None,
        client_path: Path | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._token_path = token_path or cfg.oauth_token_path()
        self._client_path = client_path or cfg.oauth_client_path()

    async def get_tokens(self) -> OAuthToken | None:
        data = _load_json(self._token_path)
        if data is None:
            return None
        return OAuthToken.model_validate(data)

    async def set_tokens(self, tokens: OAuthToken) -> None:
        _save_json(self._token_path, tokens.model_dump(mode="json", exclude_none=True))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        data = _load_json(self._client_path)
        if data is None:
            return None
        return OAuthClientInformationFull.model_validate(data)

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        _save_json(
            self._client_path,
            client_info.model_dump(mode="json", exclude_none=True),
        )
