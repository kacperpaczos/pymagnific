"""Pydantic models for Space board exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SpaceCreation(BaseModel):
    node_id: str
    name: str
    creation_identifier: str


class PulledAsset(BaseModel):
    node_id: str
    name: str
    creation_identifier: str
    local_path: Path
    url: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpaceExport(BaseModel):
    base_dir: Path
    board_toon: Path
    board_json: Path
    manifest: Path
    assets: list[PulledAsset]
    counts: dict[str, int]

    model_config = {"arbitrary_types_allowed": True}


class BoardSummary(BaseModel):
    space_id: str | None = None
    elements_count: int | None = None
    connections_count: int | None = None
    panels: list[dict[str, Any]] = Field(default_factory=list)
    creations: list[dict[str, Any]] = Field(default_factory=list)
    creation_count: int = 0
    node_count: int = 0
    connection_count: int = 0
    export_dir: str | None = None
    resolved_space_id: str | None = None
