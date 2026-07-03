"""Workspace pipeline service: provision, upload, prepare, deploy, run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pymagnific.core.config import Settings, get_settings
from pymagnific.core.exceptions import AssetsError
from pymagnific.parsers.board_toon import parse_board_json
from pymagnific.parsers.workspace_builder import build_workspace_from_spec_files
from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest
from pymagnific.services.assets_service import AssetsService
from pymagnific.services.job_runner import JobRunner
from pymagnific.services.pipeline_sync import PipelineSync
from pymagnific.services.project_paths import ProjectPaths, product_ids_from_pipeline_ids
from pymagnific.services.spaces_service import SpacesService
from pymagnific.services.sync_checkpoint import SyncCheckpoint
from pymagnific.services.sync_progress import CliSyncProgress, NullSyncProgress, SyncContext
from pymagnific.services.workspace_store import WorkspaceStore
from pymagnific.templates.audit import audit_workspace_remote
from pymagnific.templates.validate import checkpoint_has_upload, validate_workspace


class ProjectService:
    def __init__(
        self,
        assets: AssetsService | None = None,
        spaces: SpacesService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._assets = assets or AssetsService(settings=self._settings)
        self._spaces = spaces or SpacesService(settings=self._settings)
        self._paths = ProjectPaths(self._settings)
        self._store = WorkspaceStore(self._paths)
        self._sync = PipelineSync(self._store, self._assets, self._spaces)
        self._jobs = JobRunner(
            self._store,
            self._assets,
            self._spaces,
            fetch_board=self._fetch_board,
        )

    def projects_dir(self) -> Path:
        return self._paths.projects_dir()

    def project_path(self, space_ref: str) -> Path:
        return self._paths.project_path(space_ref)

    def workspace_file(self, space_ref: str) -> Path:
        return self._paths.workspace_file(space_ref)

    def instance_dir(self, space_ref: str, product_id: str) -> Path:
        return self._paths.instance_dir(space_ref, product_id)

    def instance_file(self, space_ref: str, product_id: str) -> Path:
        return self._paths.instance_file(space_ref, product_id)

    def has_workspace(self, space_ref: str) -> bool:
        return self._store.has_workspace(space_ref)

    def _require_workspace(self, space_ref: str) -> None:
        if not self.has_workspace(space_ref):
            raise AssetsError(
                f"No workspace.json for '{space_ref}'. "
                f"Run `pymagnific project sync init {space_ref} --spec pipeline-spec.json` first."
            )

    def load_workspace(self, space_ref: str) -> WorkspaceManifest:
        return self._store.load_workspace(space_ref)

    def save_workspace(self, space_ref: str, workspace: WorkspaceManifest) -> Path:
        return self._store.save_workspace(space_ref, workspace)

    def load_instance(self, space_ref: str, product_id: str) -> PipelineInstance:
        return self._store.load_instance(space_ref, product_id)

    def save_instance(self, space_ref: str, instance: PipelineInstance) -> Path:
        return self._store.save_instance(space_ref, instance)

    def list_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
    ) -> list[PipelineInstance]:
        return self._store.list_instances(space_ref, product_ids=product_ids)

    @staticmethod
    def product_ids_from_pipeline_ids(pipeline_ids: list[str] | None) -> list[str] | None:
        return product_ids_from_pipeline_ids(pipeline_ids)

    def init_workspace(
        self,
        space_ref: str,
        *,
        spec_path: Path | None = None,
    ) -> dict[str, Any]:
        spec_path = spec_path or (self.project_path(space_ref) / "pipeline-spec-draft.json")
        if not spec_path.is_file():
            raise AssetsError(f"Pipeline spec not found: {spec_path}")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        return build_workspace_from_spec_files(
            self.project_path(space_ref),
            spec,
            pkg_root=self._settings.pkg_root,
        )

    def validate_workspace_local(
        self,
        space_ref: str,
        *,
        pipeline_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return validate_workspace(
            self._settings.pkg_root,
            self.project_path(space_ref),
            pipeline_ids=self.product_ids_from_pipeline_ids(pipeline_ids),
        )

    def audit_workspace_remote(
        self,
        space_ref: str,
        *,
        pipeline_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return audit_workspace_remote(
            self.project_path(space_ref),
            pipeline_ids=self.product_ids_from_pipeline_ids(pipeline_ids),
            pkg_root=self._settings.pkg_root,
        )

    def sync_checkpoint(self, space_ref: str) -> SyncCheckpoint:
        return SyncCheckpoint(self._paths.sync_state_file(space_ref))

    def build_sync_context(
        self,
        space_ref: str,
        *,
        resume: bool = False,
        fresh: bool = False,
        quiet: bool = False,
    ) -> SyncContext:
        checkpoint = self.sync_checkpoint(space_ref)
        if fresh and checkpoint.exists():
            checkpoint.clear()
        progress = NullSyncProgress() if quiet else CliSyncProgress()
        return SyncContext(checkpoint=checkpoint, progress=progress, resume=resume)

    def sync_status(self, space_ref: str) -> dict[str, Any]:
        return self._sync.sync_status(space_ref)

    async def provision_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        edit_timeout: float = 600.0,
        resume: bool = False,
        fresh: bool = False,
        quiet: bool = False,
    ) -> dict[str, Any]:
        ctx = (
            self.build_sync_context(space_ref, resume=resume, fresh=fresh, quiet=quiet)
            if apply
            else None
        )
        return await self._sync.provision_instances(
            space_ref,
            product_ids=product_ids,
            apply=apply,
            edit_timeout=edit_timeout,
            ctx=ctx,
        )

    async def bind_instances_from_remote(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        resume: bool = False,
        fresh: bool = False,
        quiet: bool = False,
    ) -> dict[str, Any]:
        ctx = self.build_sync_context(space_ref, resume=resume, fresh=fresh, quiet=quiet)
        return await self._sync.bind_instances_from_remote(
            space_ref, product_ids=product_ids, ctx=ctx
        )

    async def sync_full(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        edit_timeout: float = 600.0,
        resume: bool = False,
        fresh: bool = False,
        quiet: bool = False,
    ) -> dict[str, Any]:
        ctx = (
            self.build_sync_context(space_ref, resume=resume, fresh=fresh, quiet=quiet)
            if apply
            else None
        )
        return await self._sync.sync_full(
            space_ref,
            product_ids=product_ids,
            apply=apply,
            edit_timeout=edit_timeout,
            ctx=ctx,
        )

    async def upload_pipelines(
        self,
        space_ref: str,
        *,
        pipeline_ids: list[str] | None = None,
        apply: bool = False,
    ) -> dict[str, Any]:
        self._require_workspace(space_ref)
        return await self.upload_instances(
            space_ref,
            product_ids=self.product_ids_from_pipeline_ids(pipeline_ids),
            apply=apply,
        )

    async def prepare_pipelines(
        self,
        space_ref: str,
        *,
        pipeline_ids: list[str] | None = None,
        apply: bool = False,
        background_creation_ids: dict[str, str] | None = None,
        edit_timeout: float = 300.0,
    ) -> dict[str, Any]:
        self._require_workspace(space_ref)
        return await self.prepare_instances(
            space_ref,
            product_ids=self.product_ids_from_pipeline_ids(pipeline_ids),
            apply=apply,
            background_creation_ids=background_creation_ids,
            edit_timeout=edit_timeout,
        )

    async def deploy_pipelines(
        self,
        space_ref: str,
        *,
        pipeline_ids: list[str] | None = None,
        apply: bool = False,
        resume: bool = False,
        fresh: bool = False,
        quiet: bool = False,
        edit_timeout: float = 300.0,
    ) -> dict[str, Any]:
        self._require_workspace(space_ref)
        product_ids = self.product_ids_from_pipeline_ids(pipeline_ids)
        ctx = (
            self.build_sync_context(space_ref, resume=resume, fresh=fresh, quiet=quiet)
            if apply
            else None
        )
        return await self._sync.deploy_instances(
            space_ref,
            product_ids=product_ids,
            apply=apply,
            edit_timeout=edit_timeout,
            ctx=ctx,
        )

    async def repair_instance_asset_nodes(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        upload_result: dict[str, Any] | None = None,
        edit_timeout: float = 300.0,
    ) -> dict[str, Any]:
        return await self._sync.repair_instance_asset_nodes(
            space_ref,
            product_ids=product_ids,
            upload_result=upload_result,
            edit_timeout=edit_timeout,
        )

    async def upload_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
    ) -> dict[str, Any]:
        return await self._sync.upload_instances(
            space_ref, product_ids=product_ids, apply=apply
        )

    async def prepare_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        background_creation_ids: dict[str, str] | None = None,
        edit_timeout: float = 300.0,
    ) -> dict[str, Any]:
        return await self._sync.prepare_instances(
            space_ref,
            product_ids=product_ids,
            apply=apply,
            background_creation_ids=background_creation_ids,
            edit_timeout=edit_timeout,
        )

    def _assert_exec_gates(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        skip_gates: bool = False,
    ) -> None:
        if skip_gates:
            return
        project_dir = self.project_path(space_ref)
        ids = product_ids or self.load_workspace(space_ref).pipeline_ids
        validation = validate_workspace(
            self._settings.pkg_root,
            project_dir,
            pipeline_ids=ids,
        )
        if not validation.get("ok"):
            fails = [
                c for c in validation.get("checks", []) if c.get("status") == "fail"
            ]
            detail = "; ".join(
                f"{c.get('scope')}/{c.get('check')}: {c.get('detail', '')}" for c in fails[:5]
            )
            raise AssetsError(
                "exec blocked: local validation failed — "
                + (detail or "see project validate")
                + ". Run `project validate` or fix assets."
            )
        missing_upload: list[str] = []
        for pid in ids:
            inst = self.load_instance(space_ref, pid)
            if inst.deploy_status in ("uploaded", "prepared", "ready"):
                continue
            if checkpoint_has_upload(project_dir, pid):
                continue
            missing_upload.append(pid)
        if missing_upload:
            raise AssetsError(
                "exec blocked: product upload not completed for pipeline(s): "
                + ", ".join(missing_upload)
                + ". Run `project sync deploy --apply` first or use --skip-gates."
            )

    async def run_batch(
        self,
        space_ref: str,
        *,
        phase: str | None = None,
        job_ids: list[str] | None = None,
        parallel: int = 2,
        product_ids: list[str] | None = None,
        skip_gates: bool = False,
    ) -> dict[str, Any]:
        self._require_workspace(space_ref)
        self._assert_exec_gates(space_ref, product_ids=product_ids, skip_gates=skip_gates)
        return await self._jobs.run_batch(
            space_ref,
            phase=phase,
            job_ids=job_ids,
            parallel=parallel,
            product_ids=product_ids,
            run_job_fn=self.run_job,
        )

    async def run_job(
        self,
        space_ref: str,
        job_id: str,
        *,
        space_id: str | None = None,
        product_id: str | None = None,
        skip_gates: bool = False,
    ) -> dict[str, Any]:
        self._require_workspace(space_ref)
        pids = [product_id] if product_id else None
        self._assert_exec_gates(space_ref, product_ids=pids, skip_gates=skip_gates)
        return await self._jobs.run_instance_job(
            space_ref,
            job_id,
            space_id=space_id,
            product_id=product_id,
        )

    async def _fetch_board(self, space_id: str) -> dict[str, Any]:
        state = await self._spaces.get_state(space_id)
        if isinstance(state, dict):
            return state
        if isinstance(state, str):
            return parse_board_json(state)
        return {}
