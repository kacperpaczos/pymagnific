"""Filesystem paths for Magnific projects and workspaces."""

from __future__ import annotations

import re
from pathlib import Path

from pymagnific.core.config import Settings, get_settings


def slugify_ref(space_ref: str) -> str:
    cleaned = re.sub(r"[^\w\s-]+", "", space_ref.strip().lower())
    cleaned = re.sub(r"[\s-]+", "_", cleaned)
    return cleaned or "space"


def product_ids_from_pipeline_ids(pipeline_ids: list[str] | None) -> list[str] | None:
    if not pipeline_ids:
        return None
    out: list[str] = []
    for pid in pipeline_ids:
        if pid.startswith("pipeline-"):
            out.append(pid.removeprefix("pipeline-"))
        else:
            out.append(pid)
    return out


class ProjectPaths:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def projects_dir(self) -> Path:
        self._settings.projects_dir.mkdir(parents=True, exist_ok=True)
        return self._settings.projects_dir

    def project_path(self, space_ref: str) -> Path:
        return self.projects_dir() / slugify_ref(space_ref)

    def workspace_file(self, space_ref: str) -> Path:
        return self.project_path(space_ref) / "workspace.json"

    def instance_dir(self, space_ref: str, product_id: str) -> Path:
        return self.project_path(space_ref) / "pipelines" / product_id

    def instance_file(self, space_ref: str, product_id: str) -> Path:
        return self.instance_dir(space_ref, product_id) / "instance.json"

    def sync_state_file(self, space_ref: str) -> Path:
        return self.project_path(space_ref) / ".sync" / "state.json"
