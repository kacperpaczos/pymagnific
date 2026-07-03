"""Magnific API response helpers."""

from __future__ import annotations

from typing import Any


def extract_space_id(created: Any) -> str | None:
    if isinstance(created, dict):
        space = created.get("space")
        if isinstance(space, dict):
            sid = space.get("id") or space.get("spaceId")
            if sid:
                return str(sid)
        return (
            created.get("spaceId")
            or created.get("space_id")
            or created.get("id")
        )
    return None


def extract_operation_id(edit_resp: Any) -> str | None:
    if isinstance(edit_resp, dict):
        return (
            edit_resp.get("operationId")
            or edit_resp.get("operation_id")
            or edit_resp.get("threadId")
            or edit_resp.get("thread_id")
        )
    return None


def node_creation_id(board: dict[str, Any], node_id: str | None) -> str | None:
    if not node_id:
        return None
    for item in board.get("nodeData", []):
        if str(item.get("elementId")) == str(node_id) and item.get("key") == "creationIdentifier":
            value = item.get("value")
            return str(value) if value else None
    return None


def node_type(board: dict[str, Any], node_id: str | None) -> str | None:
    if not node_id:
        return None
    for node in board.get("nodes", []):
        if str(node.get("id")) == str(node_id):
            return str(node.get("type", "")).lower() or None
    return None
