"""FileTokenStorage tests."""

import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from pymagnific.clients.auth.token_storage import FileTokenStorage


@pytest.mark.asyncio
async def test_token_round_trip(tmp_path):
    token_path = tmp_path / "oauth.json"
    client_path = tmp_path / "oauth_client.json"
    storage = FileTokenStorage(token_path=token_path, client_path=client_path)

    tokens = OAuthToken(
        access_token="access-abc",
        refresh_token="refresh-xyz",
        expires_in=3600,
        scope="openid offline_access",
    )
    await storage.set_tokens(tokens)
    loaded = await storage.get_tokens()
    assert loaded is not None
    assert loaded.access_token == "access-abc"
    assert loaded.refresh_token == "refresh-xyz"
    assert token_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_client_info_round_trip(tmp_path):
    client_path = tmp_path / "oauth_client.json"
    storage = FileTokenStorage(
        token_path=tmp_path / "oauth.json",
        client_path=client_path,
    )

    info = OAuthClientInformationFull(
        client_id="dyn-client-1",
        grant_types=["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
        token_endpoint_auth_method="none",
        redirect_uris=["http://127.0.0.1/callback"],
        response_types=[],
        client_name="pymagnific-cli",
    )
    await storage.set_client_info(info)
    loaded = await storage.get_client_info()
    assert loaded is not None
    assert loaded.client_id == "dyn-client-1"
    assert "urn:ietf:params:oauth:grant-type:device_code" in (loaded.grant_types or [])
