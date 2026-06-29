"""Magnific MCP client - spaces_*, flows_*, account_balance."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from pymagnific.clients.auth.mcp_auth import create_oauth_provider
from pymagnific.core.config import Settings, get_settings
from pymagnific.core.exceptions import MagnificMcpError


def _extract_content(result: Any) -> Any:
    if result is None:
        return None
    content = getattr(result, "content", None)
    if not content:
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result
    parts: list[Any] = []
    for block in content:
        if hasattr(block, "text"):
            text = block.text
            try:
                parts.append(json.loads(text))
            except (json.JSONDecodeError, TypeError):
                parts.append(text)
        elif hasattr(block, "model_dump"):
            parts.append(block.model_dump())
        else:
            parts.append(block)
    if len(parts) == 1:
        return parts[0]
    return parts


class MagnificMcpClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        auth = create_oauth_provider(settings=self._settings)
        async with streamablehttp_client(self._settings.mcp_url, auth=auth) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        async with self.session() as session:
            result = await session.call_tool(name, arguments or {})
            if getattr(result, "isError", False):
                raise MagnificMcpError(f"MCP {name} error: {_extract_content(result)}")
            return _extract_content(result)

    async def spaces_list(self, **kwargs: Any) -> Any:
        return await self.call_tool("spaces_list", kwargs)

    async def spaces_create(self, name: str, description: str | None = None) -> Any:
        args: dict[str, Any] = {"name": name}
        if description:
            args["description"] = description
        return await self.call_tool("spaces_create", args)

    async def spaces_edit(self, space_id: str, query: str, **kwargs: Any) -> Any:
        args: dict[str, Any] = {"spaceId": space_id, "query": query, **kwargs}
        return await self.call_tool("spaces_edit", args)

    async def spaces_edit_status(self, **kwargs: Any) -> Any:
        return await self.call_tool("spaces_edit_status", kwargs)

    async def spaces_state(self, space_id: str, **kwargs: Any) -> Any:
        return await self.call_tool("spaces_state", {"spaceId": space_id, **kwargs})

    async def spaces_get_nodes(self, space_id: str, node_ids: list[str], **kwargs: Any) -> Any:
        return await self.call_tool(
            "spaces_get_nodes",
            {"spaceId": space_id, "nodeIds": node_ids, **kwargs},
        )

    async def spaces_run(
        self,
        space_id: str,
        start_node_id: str,
        *,
        mode: str = "connected",
    ) -> Any:
        return await self.call_tool(
            "spaces_run",
            {"spaceId": space_id, "startNodeId": start_node_id, "mode": mode},
        )

    async def spaces_run_status(
        self, workflow_run_identifier: str, *, timeout_seconds: int = 25
    ) -> Any:
        return await self.call_tool(
            "spaces_run_status",
            {"workflowRunIdentifier": workflow_run_identifier, "timeoutSeconds": timeout_seconds},
        )

    async def simulate_spaces(
        self, space_id: str, start_node_id: str, *, mode: str = "connected"
    ) -> Any:
        return await self.call_tool(
            "simulate_spaces",
            {"spaceId": space_id, "startNodeId": start_node_id, "mode": mode},
        )

    async def spaces_add_creations(
        self,
        space_id: str,
        creation_identifiers: list[str],
        *,
        page_id: str | None = None,
    ) -> Any:
        args: dict[str, Any] = {
            "spaceId": space_id,
            "creationIdentifiers": creation_identifiers,
        }
        if page_id:
            args["pageId"] = page_id
        return await self.call_tool("spaces_add_creations", args)

    async def creations_get(self, creation_identifier: str) -> Any:
        return await self.call_tool("creations_get", {"creationIdentifier": creation_identifier})

    async def creations_request_upload(self, mime_type: str) -> Any:
        return await self.call_tool("creations_request_upload", {"mimeType": mime_type})

    async def creations_finalize_upload(self, path: str) -> Any:
        return await self.call_tool("creations_finalize_upload", {"path": path})

    async def account_balance(self) -> Any:
        return await self.call_tool("account_balance", {})
