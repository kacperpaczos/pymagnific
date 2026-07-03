"""Template registry: paths and required asset slots per template_id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

KNOWN_TEMPLATES = ("ecommerce_raw", "do3d_textures_2d")


class RequiredAssetSlot(BaseModel):
    slot: str
    logical_key: str
    required: bool = True
    formats: list[str] = Field(default_factory=lambda: ["jpg", "jpeg", "png"])


_DEFAULT_REQUIRED_ASSETS: dict[str, list[RequiredAssetSlot]] = {
    "ecommerce_raw": [
        RequiredAssetSlot(slot="product", logical_key="product", required=True),
        RequiredAssetSlot(slot="material", logical_key="material_reference", required=False),
    ],
    "do3d_textures_2d": [
        RequiredAssetSlot(slot="product", logical_key="product", required=True),
    ],
}


def templates_root(pkg_root: Path) -> Path:
    return pkg_root / "projects" / "templates"


def template_dir(pkg_root: Path, template_id: str) -> Path:
    path = templates_root(pkg_root) / template_id
    if not path.is_dir():
        raise FileNotFoundError(f"Template not found: {template_id} ({path})")
    return path


def template_board_path(pkg_root: Path, template_id: str) -> Path:
    return template_dir(pkg_root, template_id) / "board.json"


def template_project_path(pkg_root: Path, template_id: str) -> Path:
    return template_dir(pkg_root, template_id) / "project.json"


def list_templates(pkg_root: Path) -> list[str]:
    root = templates_root(pkg_root)
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "template.json").is_file()
    )


def load_template_meta(pkg_root: Path, template_id: str) -> dict[str, Any]:
    path = template_dir(pkg_root, template_id) / "template.json"
    return json.loads(path.read_text(encoding="utf-8"))


def required_asset_slots(pkg_root: Path, template_id: str) -> list[RequiredAssetSlot]:
    meta = load_template_meta(pkg_root, template_id)
    raw = meta.get("required_assets")
    if isinstance(raw, list) and raw:
        return [RequiredAssetSlot.model_validate(item) for item in raw]
    return list(_DEFAULT_REQUIRED_ASSETS.get(template_id, _DEFAULT_REQUIRED_ASSETS["ecommerce_raw"]))
