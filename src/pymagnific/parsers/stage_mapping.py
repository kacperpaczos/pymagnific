"""Central stage ? logical_key mapping for exec run."""

from __future__ import annotations

from typing import Any

STAGE_TO_LOGICAL_KEY: dict[str, str] = {
    "stage_material": "material_generator",
    "stage_color": "color_generator",
    "stage_photoshoot": "product_shot_generator",
    "stage_composite": "composite_generator",
    "stage_texture": "texture_generator",
    "stage_print_flat": "print_flat_generator",
}

STAGE_BOARD_PATTERNS: dict[str, tuple[str, tuple[str, ...]]] = {
    "stage_material": ("image-generator", ("material variation generator",)),
    "stage_color": ("image-generator", ("color variation generator",)),
    "stage_photoshoot": ("image-generator", ("product shot generator",)),
    "stage_composite": ("image-generator", ("composite generator",)),
    "stage_texture": ("image-generator", ("texture generator",)),
    "stage_print_flat": ("image-generator", ("print flat generator",)),
}


def stage_node_from_bound_nodes(nodes: dict[str, str], stage_id: str) -> str | None:
    key = STAGE_TO_LOGICAL_KEY.get(stage_id)
    if key:
        return nodes.get(key)
    return None


def find_stage_node_on_board(board: dict[str, Any], stage_id: str) -> str | None:
    spec = STAGE_BOARD_PATTERNS.get(stage_id)
    if not spec:
        return None
    want_type, name_parts = spec
    for node in board.get("nodes", []):
        if str(node.get("type", "")).lower() != want_type:
            continue
        name = str(node.get("name", "")).lower()
        if all(part in name for part in name_parts):
            node_id = node.get("id")
            if node_id:
                return str(node_id)
    return None
