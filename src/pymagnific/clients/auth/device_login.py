"""OAuth 2.0 Device Authorization Grant (RFC 8628) for Magnific MCP CLI login."""

from __future__ import annotations

import time
import webbrowser

import httpx
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from pymagnific.clients.auth.token_storage import FileTokenStorage
from pymagnific.core.config import (
    OAUTH_AUTH_SERVER,
    OAUTH_REGISTRATION_ENDPOINT,
    Settings,
    get_settings,
)

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_PLACEHOLDER_REDIRECT = "http://127.0.0.1/callback"


def _device_authorization_endpoint() -> str:
    return f"{OAUTH_AUTH_SERVER}/protocol/openid-connect/auth/device"


def _token_endpoint() -> str:
    return f"{OAUTH_AUTH_SERVER}/protocol/openid-connect/token"


async def _register_device_client(
    storage: FileTokenStorage,
    settings: Settings,
) -> OAuthClientInformationFull:
    existing = await storage.get_client_info()
    if existing and existing.client_id:
        grant_types = existing.grant_types or []
        if DEVICE_GRANT in grant_types:
            return existing

    payload = {
        "client_name": "pymagnific-cli",
        "grant_types": [DEVICE_GRANT, "refresh_token"],
        "response_types": [],
        "token_endpoint_auth_method": "none",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            OAUTH_REGISTRATION_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Client registration failed: {resp.status_code} {resp.text}")

    data = resp.json()
    info = OAuthClientInformationFull(
        client_id=data["client_id"],
        client_secret=data.get("client_secret"),
        grant_types=data.get("grant_types", payload["grant_types"]),
        token_endpoint_auth_method=data.get("token_endpoint_auth_method", "none"),
        redirect_uris=data.get("redirect_uris") or [_PLACEHOLDER_REDIRECT],
        response_types=data.get("response_types", []),
        scope=settings.oauth_scopes,
        client_name="pymagnific-cli",
    )
    await storage.set_client_info(info)
    return info


async def login(
    *,
    open_browser: bool = True,
    settings: Settings | None = None,
    storage: FileTokenStorage | None = None,
) -> OAuthToken:
    """Run device authorization flow and persist tokens."""
    cfg = settings or get_settings()
    store = storage or FileTokenStorage(settings=cfg)
    client_info = await _register_device_client(store, cfg)
    if not client_info.client_id:
        raise RuntimeError("Client registration did not return client_id")

    async with httpx.AsyncClient(timeout=30) as http:
        device_resp = await http.post(
            _device_authorization_endpoint(),
            data={
                "client_id": client_info.client_id,
                "scope": cfg.oauth_scopes,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if device_resp.status_code >= 400:
            raise RuntimeError(
                f"Device authorization failed: {device_resp.status_code} {device_resp.text}"
            )

        device_data = device_resp.json()
        device_code = device_data["device_code"]
        user_code = device_data.get("user_code", "")
        verification_uri = device_data.get("verification_uri_complete") or device_data.get(
            "verification_uri", ""
        )
        interval = int(device_data.get("interval", 5))
        expires_in = int(device_data.get("expires_in", cfg.oauth_device_timeout))
        deadline = time.monotonic() + min(expires_in, cfg.oauth_device_timeout)

        print("Open this URL in your browser and sign in to Magnific:")
        if verification_uri and user_code and "user_code" not in verification_uri:
            print(f"{verification_uri}")
            print(f"Enter code: {user_code}")
        else:
            print(verification_uri or _device_authorization_endpoint())

        if open_browser and verification_uri:
            webbrowser.open(verification_uri)

        while time.monotonic() < deadline:
            token_resp = await http.post(
                _token_endpoint(),
                data={
                    "grant_type": DEVICE_GRANT,
                    "device_code": device_code,
                    "client_id": client_info.client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_resp.status_code == 200:
                tokens = OAuthToken.model_validate(token_resp.json())
                await store.set_tokens(tokens)
                return tokens

            try:
                error_body = token_resp.json()
                error = error_body.get("error", "")
            except Exception:
                error = token_resp.text

            if error == "authorization_pending":
                await _sleep(interval)
                continue
            if error == "slow_down":
                interval += 5
                await _sleep(interval)
                continue
            if error == "access_denied":
                raise RuntimeError("Authorization denied by user")
            if error == "expired_token":
                raise RuntimeError("Device code expired - run auth login again")

            raise RuntimeError(f"Token poll failed: {token_resp.status_code} {error}")

    raise RuntimeError(f"Device authorization timed out after {cfg.oauth_device_timeout}s")


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
