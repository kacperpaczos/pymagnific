"""Device authorization flow tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pymagnific.clients.auth.device_login import login
from pymagnific.clients.auth.token_storage import FileTokenStorage


@pytest.mark.asyncio
async def test_device_login_success(tmp_path):
    token_path = tmp_path / "oauth.json"
    client_path = tmp_path / "oauth_client.json"
    storage = FileTokenStorage(token_path=token_path, client_path=client_path)

    register_resp = MagicMock()
    register_resp.status_code = 201
    register_resp.json.return_value = {
        "client_id": "dyn-device-123",
        "grant_types": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
        "token_endpoint_auth_method": "none",
    }

    device_resp = MagicMock()
    device_resp.status_code = 200
    device_resp.json.return_value = {
        "device_code": "device-code-xyz",
        "user_code": "ABCD-1234",
        "verification_uri": "https://auth.example/verify",
        "verification_uri_complete": "https://auth.example/verify?user_code=ABCD-1234",
        "expires_in": 600,
        "interval": 0,
    }

    pending_resp = MagicMock()
    pending_resp.status_code = 400
    pending_resp.json.return_value = {"error": "authorization_pending"}

    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=[register_resp, device_resp, pending_resp, token_resp])
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch("pymagnific.clients.auth.device_login.httpx.AsyncClient", return_value=mock_http):
        with patch("pymagnific.clients.auth.device_login.webbrowser.open"):
            with patch("pymagnific.clients.auth.device_login._sleep", new_callable=AsyncMock):
                tokens = await login(open_browser=False, storage=storage)

    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "new-refresh"
    saved = await storage.get_tokens()
    assert saved is not None
    assert saved.access_token == "new-access"
    client = await storage.get_client_info()
    assert client is not None
    assert client.client_id == "dyn-device-123"


@pytest.mark.asyncio
async def test_device_login_reuses_registered_client(tmp_path):
    client_path = tmp_path / "oauth_client.json"
    client_path.write_text(
        '{"client_id":"existing","grant_types":["urn:ietf:params:oauth:grant-type:device_code","refresh_token"],'
        '"token_endpoint_auth_method":"none","response_types":[],"redirect_uris":["http://127.0.0.1/callback"]}',
        encoding="utf-8",
    )
    storage = FileTokenStorage(token_path=tmp_path / "oauth.json", client_path=client_path)

    device_resp = MagicMock()
    device_resp.status_code = 200
    device_resp.json.return_value = {
        "device_code": "dc",
        "verification_uri_complete": "https://auth.example/verify",
        "expires_in": 60,
        "interval": 0,
    }

    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {
        "access_token": "tok",
        "token_type": "Bearer",
        "expires_in": 60,
    }

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=[device_resp, token_resp])
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch("pymagnific.clients.auth.device_login.httpx.AsyncClient", return_value=mock_http):
        with patch("pymagnific.clients.auth.device_login.webbrowser.open"):
            tokens = await login(open_browser=False, storage=storage)

    assert tokens.access_token == "tok"
    assert mock_http.post.await_count == 2
