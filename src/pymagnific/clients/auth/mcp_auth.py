"""MCP OAuth provider factory and auth status."""

from __future__ import annotations

import time
from typing import Any

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata, OAuthToken
from mcp.shared.auth_utils import calculate_token_expiry

from pymagnific.clients.auth.token_storage import FileTokenStorage
from pymagnific.core.config import Settings, get_settings

_PLACEHOLDER_REDIRECT = "http://127.0.0.1/callback"


def create_oauth_provider(
    *,
    settings: Settings | None = None,
    storage: FileTokenStorage | None = None,
) -> OAuthClientProvider:
    cfg = settings or get_settings()
    return OAuthClientProvider(
        server_url=cfg.mcp_url,
        client_metadata=OAuthClientMetadata(
            redirect_uris=[_PLACEHOLDER_REDIRECT],
            scope=cfg.oauth_scopes,
            grant_types=[
                "authorization_code",
                "refresh_token",
                "urn:ietf:params:oauth:grant-type:device_code",
            ],
            client_name="pymagnific-cli",
        ),
        storage=storage or FileTokenStorage(settings=cfg),
        redirect_handler=None,
        callback_handler=None,
    )


def _token_expired(tokens: OAuthToken | None) -> bool | None:
    if tokens is None:
        return None
    if tokens.expires_in is None:
        return False
    expiry = calculate_token_expiry(tokens.expires_in)
    if expiry is None:
        return False
    return time.time() > expiry


async def auth_status(
    *,
    settings: Settings | None = None,
    storage: FileTokenStorage | None = None,
) -> dict[str, Any]:
    cfg = settings or get_settings()
    store = storage or FileTokenStorage(settings=cfg)
    tokens = await store.get_tokens()
    client = await store.get_client_info()
    expired = _token_expired(tokens)

    if tokens is None:
        return {
            "logged_in": False,
            "client_registered": client is not None,
            "client_id": client.client_id if client else None,
            "token_path": str(cfg.oauth_token_path()),
            "client_path": str(cfg.oauth_client_path()),
        }

    return {
        "logged_in": True,
        "client_registered": client is not None,
        "client_id": client.client_id if client else None,
        "token_path": str(cfg.oauth_token_path()),
        "client_path": str(cfg.oauth_client_path()),
        "expired": expired,
        "has_refresh": bool(tokens.refresh_token),
        "grant_types": client.grant_types if client else None,
    }
