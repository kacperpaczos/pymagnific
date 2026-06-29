"""REST client tests (async httpx)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pymagnific.clients.magnific_rest import MagnificRestClient
from pymagnific.core.exceptions import MagnificRestError


@pytest.fixture
def client():
    return MagnificRestClient(key="test-key")


@pytest.mark.asyncio
async def test_list_apps(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"data":[]}'
    mock_resp.json.return_value = {"data": []}
    mock_resp.headers = {}

    mock_http = AsyncMock()
    mock_http.request.return_value = mock_resp
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_http):
        result = await client.list_apps()
        assert result == {"data": []}
        mock_http.request.assert_called_once()


@pytest.mark.asyncio
async def test_probe_success(client):
    with patch.object(client, "list_apps", return_value={"data": [{"id": "x"}]}):
        result = await client.probe()
        assert result["api_key_valid"] is True
        assert result["apps"]["data"][0]["id"] == "x"


@pytest.mark.asyncio
async def test_run_app_error(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"message": "forbidden"}
    mock_resp.headers = {}

    mock_http = AsyncMock()
    mock_http.request.return_value = mock_resp
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_http):
        with pytest.raises(MagnificRestError) as exc:
            await client.run_app("app1", {"k": "v"})
        assert exc.value.status == 403
