"""Workspace and pipeline instance persistence."""

from __future__ import annotations

import json
from pathlib import Path

from pymagnific.core.exceptions import AssetsError
from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest
from pymagnific.services.project_paths import ProjectPaths


class WorkspaceStore:
    def __init__(self, paths: ProjectPaths | None = None) -> None:
        self._paths = paths or ProjectPaths()

    def has_workspace(self, space_ref: str) -> bool:
        return self._paths.workspace_file(space_ref).is_file()

    def load_workspace(self, space_ref: str) -> WorkspaceManifest:
        path = self._paths.workspace_file(space_ref)
        if not path.is_file():
            raise AssetsError(
                f"Workspace not found: {path}. Run: pymagnific project sync init {space_ref}"
            )
        return WorkspaceManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def save_workspace(self, space_ref: str, workspace: WorkspaceManifest) -> Path:
        path = self._paths.workspace_file(space_ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(workspace.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def load_instance(self, space_ref: str, product_id: str) -> PipelineInstance:
        path = self._paths.instance_file(space_ref, product_id)
        if not path.is_file():
            raise AssetsError(f"Pipeline instance not found: {path}")
        return PipelineInstance.model_validate_json(path.read_text(encoding="utf-8"))

    def save_instance(self, space_ref: str, instance: PipelineInstance) -> Path:
        path = self._paths.instance_file(space_ref, instance.product_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(instance.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def list_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
    ) -> list[PipelineInstance]:
        workspace = self.load_workspace(space_ref)
        ids = product_ids or workspace.pipeline_ids
        instances: list[PipelineInstance] = []
        for pid in ids:
            if self._paths.instance_file(space_ref, pid).is_file():
                instances.append(self.load_instance(space_ref, pid))
        return [i for i in instances if i.enabled]

    @property
    def paths(self) -> ProjectPaths:
        return self._paths
