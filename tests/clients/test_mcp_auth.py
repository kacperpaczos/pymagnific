"""mcp_auth status tests."""

import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from pymagnific.clients.auth.mcp_auth import auth_status
from pymagnific.clients.auth.token_storage import FileTokenStorage


@pytest.mark.asyncio
async def test_auth_status_logged_out(tmp_path):
    storage = FileTokenStorage(
        token_path=tmp_path / "oauth.json",
        client_path=tmp_path / "oauth_client.json",
    )
    status = await auth_status(storage=storage)
    assert status["logged_in"] is False
    assert status["client_registered"] is False


@pytest.mark.asyncio
async def test_auth_status_logged_in(tmp_path):
    storage = FileTokenStorage(
        token_path=tmp_path / "oauth.json",
        client_path=tmp_path / "oauth_client.json",
    )
    await storage.set_tokens(OAuthToken(access_token="abc", refresh_token="ref", expires_in=3600))
    await storage.set_client_info(
        OAuthClientInformationFull(
            client_id="client-1",
            redirect_uris=["http://127.0.0.1/callback"],
            grant_types=["refresh_token"],
        )
    )
    status = await auth_status(storage=storage)
    assert status["logged_in"] is True
    assert status["client_id"] == "client-1"
    assert status["has_refresh"] is True
