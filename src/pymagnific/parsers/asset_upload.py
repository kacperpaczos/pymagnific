"""Shared asset upload + node bind helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pymagnific.services.assets_service import AssetsService
from pymagnific.services.spaces_service import SpacesService


async def push_image_and_bind(
    assets: AssetsService,
    spaces: SpacesService,
    *,
    space_id: str,
    space_ref: str,
    image_path: Path,
    node_id: str,
    node_label: str,
) -> dict[str, Any]:
    """Upload image and set creationIdentifier on a board node."""
    push = await assets.push_image(space_ref, image_path, space_id=space_id)
    creation_id = push.get("creationIdentifier")
    result: dict[str, Any] = {
        "path": str(image_path),
        "creation_id": creation_id,
        "status": "ok",
    }
    if creation_id and node_id:
        await spaces.edit_space(
            space_id,
            f"Set creationIdentifier on {node_label} node ({node_id}) to {creation_id}",
        )
    return result
