"""Map pipeline instance nodes from Magnific board state."""

from __future__ import annotations

from typing import Any

from pymagnific.parsers.node_registry import (
    BIND_PATTERNS,
    IMAGE_GENERATOR_KEYS,
    LIST_KEYS,
    PROMPT_GENERATOR_KEYS,
    TYPE_OVERRIDES,
)
from pymagnific.schemas.workspace import PipelineInstance


def _pipeline_marker(instance: PipelineInstance) -> str:
    return f"pipeline #{instance.product_id}".lower()


def _node_belongs_to_instance(
    node: dict[str, Any],
    instance: PipelineInstance,
    panels_by_id: dict[str, str],
) -> bool:
    marker = _pipeline_marker(instance)
    group_id = node.get("groupId")
    if group_id:
        panel = str(panels_by_id.get(str(group_id), "")).lower()
        if marker in panel:
            return True
    return marker in str(node.get("name", "")).lower()


def _matches_type(logical_key: str, node_type: str) -> bool:
    allowed = TYPE_OVERRIDES.get(logical_key)
    if allowed:
        return node_type in allowed
    if logical_key in LIST_KEYS:
        return node_type == "list"
    if logical_key in PROMPT_GENERATOR_KEYS:
        return node_type == "prompt-generator"
    if logical_key in IMAGE_GENERATOR_KEYS:
        return node_type == "image-generator"
    return True


def bind_nodes_from_board(
    instance: PipelineInstance,
    board: dict[str, Any],
) -> dict[str, str]:
    """Find node UUIDs for this pipeline instance by product id suffix on panels/nodes."""
    panels_by_id: dict[str, str] = {}
    for node in board.get("nodes", []):
        if node.get("type") == "panel":
            panels_by_id[str(node["id"])] = str(node.get("name", ""))

    bound: dict[str, str] = {}
    for logical_key, name_parts in BIND_PATTERNS.items():
        for node in board.get("nodes", []):
            if node.get("type") == "panel":
                continue
            if not _node_belongs_to_instance(node, instance, panels_by_id):
                continue
            node_type = str(node.get("type", "")).lower()
            if not _matches_type(logical_key, node_type):
                continue
            name = str(node.get("name", "")).lower()
            if logical_key == "product":
                if "product" not in name or "label" in name or "shot" in name:
                    continue
                bound[logical_key] = str(node["id"])
                break
            if all(part in name for part in name_parts):
                bound[logical_key] = str(node["id"])
                break

    return bound
