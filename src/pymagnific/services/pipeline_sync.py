"""Pipeline sync: provision, deploy, upload, prepare in one Magnific Space."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymagnific.core.config import get_settings
from pymagnific.core.exceptions import AssetsError
from pymagnific.parsers.asset_upload import push_image_and_bind
from pymagnific.parsers.board_toon import parse_board_json
from pymagnific.parsers.instance_board import bind_nodes_from_board
from pymagnific.parsers.pipeline_prompts import apply_prompts_to_instance
from pymagnific.parsers.pipeline_spawn import (
    PrepareStep,
    build_instance_asset_repair_query,
    build_instance_prepare_steps,
    build_instance_provision_query,
)
from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest
from pymagnific.services.api_helpers import extract_operation_id, node_creation_id, node_type
from pymagnific.services.assets_service import AssetsService
from pymagnific.services.spaces_service import SpacesService
from pymagnific.services.sync_checkpoint import SyncCheckpoint
from pymagnific.services.sync_planner import (
    plan_deploy_steps,
    plan_full_steps,
    plan_provision_steps,
)
from pymagnific.services.sync_progress import NullSyncProgress, SyncContext
from pymagnific.services.sync_runner import run_sync_step
from pymagnific.services.workspace_store import WorkspaceStore
from pymagnific.templates.registry import required_asset_slots
from pymagnific.templates.validate import record_asset_binding


class PipelineSync:
    def __init__(
        self,
        store: WorkspaceStore,
        assets: AssetsService,
        spaces: SpacesService,
    ) -> None:
        self._store = store
        self._assets = assets
        self._spaces = spaces

    def _checkpoint(self, space_ref: str) -> SyncCheckpoint:
        return SyncCheckpoint(self._store.paths.sync_state_file(space_ref))

    def _init_ctx(
        self,
        space_ref: str,
        ctx: SyncContext | None,
        *,
        total_steps: int,
        space_id: str | None,
    ) -> SyncContext | None:
        if ctx is None:
            return None
        if ctx.run_state is not None:
            return ctx
        checkpoint = ctx.checkpoint or self._checkpoint(space_ref)
        progress = ctx.progress or NullSyncProgress()
        run_state = checkpoint.start_run(
            space_ref,
            space_id=space_id,
            total_steps=total_steps,
            resume=ctx.resume,
        )
        progress.on_run_start(run_state)
        ctx.checkpoint = checkpoint
        ctx.run_state = run_state
        ctx.progress = progress
        return ctx

    async def _fetch_board(self, space_id: str) -> dict[str, Any]:
        state = await self._spaces.get_state(space_id)
        if isinstance(state, dict):
            return state
        if isinstance(state, str):
            return parse_board_json(state)
        return {}

    async def _wait_edit(
        self,
        op_id: str,
        *,
        timeout: float,
        ctx: SyncContext | None,
    ) -> Any:
        deadline = time.monotonic() + timeout
        poll_n = 0
        last: Any = None
        while time.monotonic() < deadline:
            poll_n += 1
            if ctx and ctx.progress:
                ctx.progress.on_wait(op_id, poll_n)
            last = await self._spaces._mcp.spaces_edit_status(
                operationId=op_id,
                timeoutSeconds=25,
            )
            from pymagnific.services.spaces_service import _is_terminal_edit_status

            if _is_terminal_edit_status(last):
                return last
            hint = 5
            if isinstance(last, dict):
                hint = int(last.get("poll_after_seconds", hint))
            import asyncio

            await asyncio.sleep(hint)
        raise TimeoutError(f"spaces_edit_status timeout after {timeout}s (last: {last})")

    async def _edit_and_wait(
        self,
        space_id: str,
        query: str,
        *,
        timeout: float,
        ctx: SyncContext | None,
    ) -> tuple[Any, Any]:
        edit_resp = await self._spaces.edit_space(space_id, query)
        op_id = extract_operation_id(edit_resp)
        status = None
        if op_id:
            status = await self._wait_edit(str(op_id), timeout=timeout, ctx=ctx)
        return edit_resp, status

    async def _bind_one(
        self,
        space_ref: str,
        workspace: Any,
        instance: PipelineInstance,
        space_id: str,
        board: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        if board is None:
            board = await self._fetch_board(space_id)
        nodes = bind_nodes_from_board(instance, board)
        instance.magnific.nodes = nodes
        instance.magnific.space_id = space_id
        apply_prompts_to_instance(instance, workspace, nodes=nodes)
        self._store.save_instance(space_ref, instance)
        return nodes

    async def provision_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        edit_timeout: float = 600.0,
        ctx: SyncContext | None = None,
        bind_after: bool | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        space_id = workspace.meta.space_id
        if not space_id:
            space_id = await self._assets.resolve_space_id(workspace.meta.space_ref)
            workspace.meta.space_id = space_id
            self._store.save_workspace(space_ref, workspace)

        if bind_after is None:
            bind_after = ctx is None

        if apply and ctx is not None:
            ctx = self._init_ctx(
                space_ref,
                ctx,
                total_steps=len(plan_provision_steps(instances, include_bind=bind_after)),
                space_id=space_id,
            )

        results: list[dict[str, Any]] = []
        for instance in instances:
            query = build_instance_provision_query(instance, workspace=workspace)
            if not apply:
                results.append(
                    {
                        "product_id": instance.product_id,
                        "status": "dry_run",
                        "edit_query": query,
                    }
                )
                continue

            async def _provision() -> dict[str, Any]:
                _edit_resp, status = await self._edit_and_wait(
                    space_id, query, timeout=edit_timeout, ctx=ctx
                )
                return {"edit_status": status}

            prov_detail = await run_sync_step(
                ctx,
                phase="provision",
                product_id=instance.product_id,
                step_id="provision",
                fn=_provision,
            )
            prov_skipped = prov_detail is None and ctx and ctx.resume
            nodes: dict[str, str] = instance.magnific.nodes
            if bind_after:

                async def _bind_inline() -> dict[str, Any]:
                    board = await self._fetch_board(space_id)
                    n = await self._bind_one(
                        space_ref, workspace, instance, space_id, board=board
                    )
                    instance.magnific.provisioned_at = datetime.now(UTC).isoformat()
                    self._store.save_instance(space_ref, instance)
                    return {"nodes_bound": len(n)}

                if ctx:
                    bind_detail = await run_sync_step(
                        ctx,
                        phase="bind",
                        product_id=instance.product_id,
                        step_id="bind_nodes",
                        fn=_bind_inline,
                    )
                    if bind_detail:
                        nodes = instance.magnific.nodes
                else:
                    board = await self._fetch_board(space_id)
                    nodes = await self._bind_one(
                        space_ref, workspace, instance, space_id, board=board
                    )
                    instance.magnific.provisioned_at = datetime.now(UTC).isoformat()
                    self._store.save_instance(space_ref, instance)
            elif apply:

                async def _bind() -> dict[str, Any]:
                    board = await self._fetch_board(space_id)
                    n = await self._bind_one(
                        space_ref, workspace, instance, space_id, board=board
                    )
                    instance.magnific.provisioned_at = datetime.now(UTC).isoformat()
                    self._store.save_instance(space_ref, instance)
                    return {"nodes_bound": len(n)}

                bind_detail = await run_sync_step(
                    ctx,
                    phase="bind",
                    product_id=instance.product_id,
                    step_id="bind_nodes",
                    fn=_bind,
                )
                if bind_detail:
                    nodes = instance.magnific.nodes

            results.append(
                {
                    "product_id": instance.product_id,
                    "panel_name": instance.magnific.panel_name,
                    "status": "skipped" if prov_skipped and not nodes else "provisioned",
                    "nodes_bound": len(nodes),
                    "provision": prov_detail,
                    "reason": "resume" if prov_skipped else None,
                }
            )

        if ctx and ctx.active and ctx.checkpoint and ctx.run_state:
            if bind_after:
                ctx.checkpoint.mark_completed(ctx.run_state)

        asset_readiness = self._asset_readiness_summary(space_ref, workspace, instances)

        return {
            "dry_run": not apply,
            "space_id": space_id,
            "checkpoint": str(self._store.paths.sync_state_file(space_ref))
            if ctx and ctx.active
            else None,
            "note": "provision adds pipeline panels to shared Space. No run. Upload assets via deploy.",
            "asset_readiness": asset_readiness,
            "results": results,
        }

    def _asset_readiness_summary(
        self,
        space_ref: str,
        workspace: WorkspaceManifest,
        instances: list[PipelineInstance],
    ) -> dict[str, Any]:
        from pymagnific.templates.registry import required_asset_slots

        template_id = workspace.template.template_id if workspace.template else ""
        slots = required_asset_slots(get_settings().pkg_root, template_id)
        required = [s for s in slots if s.required]
        missing = 0
        ready = 0
        for instance in instances:
            inst_dir = self._store.paths.instance_dir(space_ref, instance.product_id)
            has_all = True
            for slot in required:
                rel = getattr(instance.assets, slot.slot, "")
                if not rel or not (inst_dir / rel).is_file():
                    has_all = False
                    break
            if has_all:
                ready += 1
            else:
                missing += 1
        warning = None
        if missing:
            warning = (
                f"{missing}/{len(instances)} instance(s) missing required local product asset; "
                "provision does not upload — run sync deploy --apply after adding assets."
            )
        return {
            "instances": len(instances),
            "assets_ready": ready,
            "assets_missing": missing,
            "warning": warning,
        }

    async def bind_instances_from_remote(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        ctx: SyncContext | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        space_id = workspace.meta.space_id or await self._assets.resolve_space_id(
            workspace.meta.space_ref
        )
        instances = self._store.list_instances(space_ref, product_ids=product_ids)

        if ctx is not None:
            ctx = self._init_ctx(
                space_ref,
                ctx,
                total_steps=len(instances),
                space_id=space_id,
            )

        board = await self._fetch_board(space_id)
        results: list[dict[str, Any]] = []
        for instance in instances:

            async def _bind(inst: PipelineInstance = instance) -> dict[str, Any]:
                nodes = await self._bind_one(
                    space_ref, workspace, inst, space_id, board=board
                )
                return {"nodes_bound": len(nodes), "nodes": nodes}

            detail = await run_sync_step(
                ctx,
                phase="bind",
                product_id=instance.product_id,
                step_id="bind_nodes",
                fn=_bind,
            )
            if detail is None and ctx and ctx.resume:
                results.append(
                    {
                        "product_id": instance.product_id,
                        "nodes_bound": len(instance.magnific.nodes),
                        "status": "skipped",
                    }
                )
            else:
                results.append(
                    {
                        "product_id": instance.product_id,
                        "nodes_bound": detail.get("nodes_bound", 0) if detail else 0,
                        "nodes": instance.magnific.nodes,
                    }
                )

        if ctx and ctx.active and ctx.checkpoint and ctx.run_state:
            ctx.checkpoint.mark_completed(ctx.run_state)

        return {
            "space_id": space_id,
            "checkpoint": str(self._store.paths.sync_state_file(space_ref))
            if ctx and ctx.active
            else None,
            "results": results,
        }

    async def upload_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        ctx: SyncContext | None = None,
        upload_result_accum: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        space_id = workspace.meta.space_id or await self._assets.resolve_space_id(
            workspace.meta.space_ref
        )
        template_id = workspace.template.template_id if workspace.template else "ecommerce_raw"
        settings = get_settings()
        asset_slots = {
            s.slot: s for s in required_asset_slots(settings.pkg_root, template_id)
        }
        results: list[dict[str, Any]] = upload_result_accum.get("results", []) if upload_result_accum else []
        upload_errors = 0

        for instance in instances:
            inst_dir = self._store.paths.instance_dir(space_ref, instance.product_id)
            if not apply:
                missing = []
                for slot_name, slot in asset_slots.items():
                    if not slot.required:
                        continue
                    rel = getattr(instance.assets, slot_name, "")
                    if rel and not (inst_dir / rel).is_file():
                        missing.append(slot_name)
                results.append(
                    {
                        "product_id": instance.product_id,
                        "space_id": space_id,
                        "status": "dry_run",
                        "would_upload": {
                            "product": str(inst_dir / instance.assets.product),
                            "material": str(inst_dir / instance.assets.material),
                        },
                        "missing_required_assets": missing,
                    }
                )
                continue

            uploads: list[dict[str, Any]] = []
            product_path = inst_dir / instance.assets.product
            product_slot = asset_slots.get("product")
            if product_slot and product_slot.required and not product_path.is_file():
                upload_errors += 1
                results.append(
                    {
                        "product_id": instance.product_id,
                        "space_id": space_id,
                        "status": "error",
                        "error": f"required asset missing: {product_path}",
                        "uploads": [],
                    }
                )
                continue
            if product_path.is_file():

                async def _up_product() -> dict[str, Any]:
                    push = await push_image_and_bind(
                        self._assets,
                        self._spaces,
                        space_id=space_id,
                        space_ref=instance.product_id,
                        image_path=product_path,
                        node_id=str(instance.magnific.nodes.get("product") or ""),
                        node_label=f"Product (Pipeline #{instance.product_id})",
                    )
                    return {"kind": "product", **push}

                try:
                    r = await run_sync_step(
                        ctx,
                        phase="deploy",
                        product_id=instance.product_id,
                        step_id="upload:product",
                        fn=_up_product,
                    )
                    if r:
                        uploads.append(r)
                        cid = r.get("creation_id") or r.get("creationIdentifier")
                        if cid:
                            digest = hashlib.sha256(product_path.read_bytes()).hexdigest()
                            record_asset_binding(
                                instance, "product", sha256=digest, creation_id=str(cid)
                            )
                            self._store.save_instance(space_ref, instance)
                    elif ctx and ctx.resume:
                        uploads.append({"kind": "product", "status": "skipped"})
                except Exception as exc:  # noqa: BLE001
                    upload_errors += 1
                    uploads.append({"kind": "product", "status": "error", "error": str(exc)})

            material_path = inst_dir / instance.assets.material
            if material_path.is_file():

                async def _up_material() -> dict[str, Any]:
                    push = await push_image_and_bind(
                        self._assets,
                        self._spaces,
                        space_id=space_id,
                        space_ref=instance.product_id,
                        image_path=material_path,
                        node_id=str(instance.magnific.nodes.get("material_reference") or ""),
                        node_label=f"Material reference (Pipeline #{instance.product_id})",
                    )
                    return {"kind": "material", **push}

                try:
                    r = await run_sync_step(
                        ctx,
                        phase="deploy",
                        product_id=instance.product_id,
                        step_id="upload:material",
                        fn=_up_material,
                    )
                    if r:
                        uploads.append(r)
                    elif ctx and ctx.resume:
                        uploads.append({"kind": "material", "status": "skipped"})
                except Exception as exc:  # noqa: BLE001
                    uploads.append({"kind": "material", "status": "error", "error": str(exc)})

            status = "uploaded"
            if any(u.get("status") == "error" for u in uploads):
                status = "error"
                upload_errors += 1
            results.append(
                {
                    "product_id": instance.product_id,
                    "space_id": space_id,
                    "status": status,
                    "uploads": uploads,
                }
            )

        if apply and upload_errors:
            raise AssetsError(
                f"upload failed for {upload_errors} pipeline(s); fix missing assets or retry"
            )

        out = {
            "dry_run": not apply,
            "space_id": space_id,
            "pipeline_count": len(instances),
            "note": "upload pushes images to shared Space nodes from magnific.nodes.",
            "results": results,
        }
        if upload_result_accum is not None:
            upload_result_accum.update(out)
        return out

    async def prepare_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        background_creation_ids: dict[str, str] | None = None,
        edit_timeout: float = 300.0,
        ctx: SyncContext | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        space_id = workspace.meta.space_id or await self._assets.resolve_space_id(
            workspace.meta.space_ref
        )
        results: list[dict[str, Any]] = []

        for instance in instances:
            planned_steps: list[PrepareStep] = list(
                build_instance_prepare_steps(instance, workspace=workspace)
            )

            if not instance.magnific.nodes and apply:
                raise RuntimeError(
                    "bind nodes first: pymagnific project sync bind-nodes --apply"
                )

            if not apply:
                results.append(
                    {
                        "product_id": instance.product_id,
                        "space_id": space_id,
                        "status": "dry_run",
                        "edit_queries": [s.query for s in planned_steps],
                        "step_ids": [s.step_id for s in planned_steps],
                    }
                )
                continue

            edit_results: list[dict[str, Any]] = []
            for prep in planned_steps:

                async def _prep(step: PrepareStep = prep) -> dict[str, Any]:
                    _edit_resp, status = await self._edit_and_wait(
                        space_id, step.query, timeout=edit_timeout, ctx=ctx
                    )
                    return {
                        "step_id": step.step_id,
                        "operation_id": extract_operation_id(_edit_resp),
                        "status": status,
                    }

                try:
                    r = await run_sync_step(
                        ctx,
                        phase="deploy",
                        product_id=instance.product_id,
                        step_id=prep.step_id,
                        fn=_prep,
                    )
                    if r:
                        edit_results.append(r)
                    elif ctx and ctx.resume:
                        edit_results.append({"step_id": prep.step_id, "status": "skipped"})
                except Exception as exc:  # noqa: BLE001
                    edit_results.append({"step_id": prep.step_id, "status": "error", "error": str(exc)})
                    raise

            results.append(
                {
                    "product_id": instance.product_id,
                    "space_id": space_id,
                    "panel_name": instance.magnific.panel_name,
                    "status": "prepared",
                    "web_url": f"https://www.magnific.com/app/spaces/{space_id}",
                    "edits": edit_results,
                }
            )

        return {
            "dry_run": not apply,
            "space_id": space_id,
            "note": "prepare sets lists, prompts, and background pool. Does not run pipeline.",
            "results": results,
        }

    async def repair_instance_asset_nodes(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        upload_result: dict[str, Any] | None = None,
        edit_timeout: float = 300.0,
        ctx: SyncContext | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        space_id = workspace.meta.space_id or await self._assets.resolve_space_id(
            workspace.meta.space_ref
        )
        upload_by_product: dict[str, dict[str, str]] = {}
        for row in (upload_result or {}).get("results", []):
            pid = str(row.get("product_id", ""))
            uploads = upload_by_product.setdefault(pid, {})
            for u in row.get("uploads", []):
                if u.get("status") not in ("ok", "skipped"):
                    continue
                cid = u.get("creation_id")
                if not cid:
                    continue
                if u.get("kind") == "product":
                    uploads["product"] = str(cid)
                elif u.get("kind") == "material":
                    uploads["material"] = str(cid)
                elif u.get("kind") == "background" and "background" not in uploads:
                    uploads["background"] = str(cid)

        ecommerce_raw = workspace.uses_ecommerce_raw_template()
        do3d = workspace.uses_do3d_textures_template()
        board = await self._fetch_board(space_id)
        results: list[dict[str, Any]] = []

        for instance in instances:
            pid = instance.product_id
            uploads = upload_by_product.get(pid, {})
            product_cid = uploads.get("product") or node_creation_id(
                board, instance.magnific.nodes.get("product", "")
            )
            material_cid = uploads.get("material") or node_creation_id(
                board, instance.magnific.nodes.get("material_reference", "")
            )
            bg_cid = uploads.get("background") or node_creation_id(
                board, instance.magnific.nodes.get("background_pool", "")
            )
            product_type = node_type(board, instance.magnific.nodes.get("product", ""))
            material_type = node_type(board, instance.magnific.nodes.get("material_reference", ""))
            bg_type = node_type(board, instance.magnific.nodes.get("background_pool", ""))

            if ecommerce_raw:
                needs_repair = (
                    product_type == "image-generator" or material_type == "image-generator"
                )
            elif do3d:
                needs_repair = product_type == "image-generator"
            else:
                needs_repair = product_type == "image-generator" or bg_type == "image-generator"

            if not needs_repair:

                async def _skip() -> dict[str, Any]:
                    return {"status": "ok", "note": "asset nodes already creation type"}

                r = await run_sync_step(
                    ctx,
                    phase="deploy",
                    product_id=pid,
                    step_id="repair",
                    fn=_skip,
                )
                results.append({"product_id": pid, **(r or {"status": "skipped"})})
                continue

            query = build_instance_asset_repair_query(
                instance,
                product_creation_id=product_cid,
                material_creation_id=material_cid,
                background_creation_id=bg_cid,
                ecommerce_raw=ecommerce_raw,
                do3d_textures=do3d,
            )
            if not query:
                results.append({"product_id": pid, "status": "skipped", "reason": "no creation ids"})
                continue

            async def _repair() -> dict[str, Any]:
                _edit_resp, status = await self._edit_and_wait(
                    space_id, query, timeout=edit_timeout, ctx=ctx
                )
                new_board = await self._fetch_board(space_id)
                nodes = await self._bind_one(
                    space_ref, workspace, instance, space_id, board=new_board
                )
                return {
                    "status": "repaired",
                    "product_type_was": product_type,
                    "nodes_rebound": len(nodes),
                    "edit_status": status,
                }

            try:
                detail = await run_sync_step(
                    ctx,
                    phase="deploy",
                    product_id=pid,
                    step_id="repair",
                    fn=_repair,
                )
                results.append({"product_id": pid, **(detail or {"status": "skipped"})})
            except Exception as exc:  # noqa: BLE001
                results.append({"product_id": pid, "status": "error", "error": str(exc)})
                raise

        return {"space_id": space_id, "results": results}

    async def deploy_instances(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        edit_timeout: float = 300.0,
        ctx: SyncContext | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        space_id = workspace.meta.space_id

        if not apply:
            upload_result = await self.upload_instances(
                space_ref, product_ids=product_ids, apply=False
            )
            prepare_result = await self.prepare_instances(
                space_ref, product_ids=product_ids, apply=False
            )
            return {
                "dry_run": True,
                "upload": upload_result,
                "prepare": prepare_result,
            }

        if ctx is not None:
            ctx = self._init_ctx(
                space_ref,
                ctx,
                total_steps=len(plan_deploy_steps(instances, workspace)),
                space_id=space_id,
            )

        upload_result = await self.upload_instances(
            space_ref,
            product_ids=product_ids,
            apply=True,
            ctx=ctx,
        )
        repair_result = await self.repair_instance_asset_nodes(
            space_ref,
            product_ids=product_ids,
            upload_result=upload_result,
            edit_timeout=edit_timeout,
            ctx=ctx,
        )
        bg_map: dict[str, str] = {}
        for row in upload_result.get("results", []):
            pid = str(row.get("product_id") or "")
            for u in row.get("uploads", []):
                if u.get("kind") == "background" and u.get("creation_id"):
                    bg_map[pid] = str(u["creation_id"])
                    break

        prepare_result = await self.prepare_instances(
            space_ref,
            product_ids=product_ids,
            apply=True,
            background_creation_ids=bg_map,
            edit_timeout=edit_timeout,
            ctx=ctx,
        )

        if ctx and ctx.active and ctx.checkpoint and ctx.run_state:
            ctx.checkpoint.mark_completed(ctx.run_state)

        return {
            "dry_run": False,
            "note": "deploy = upload + repair + prepare. Open web_url in Magnific to review. No run.",
            "checkpoint": str(self._store.paths.sync_state_file(space_ref))
            if ctx and ctx.active
            else None,
            "upload": upload_result,
            "repair": repair_result,
            "prepare": prepare_result,
        }

    async def sync_full(
        self,
        space_ref: str,
        *,
        product_ids: list[str] | None = None,
        apply: bool = False,
        edit_timeout: float = 600.0,
        ctx: SyncContext | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        space_id = workspace.meta.space_id

        if not apply:
            return {
                "dry_run": True,
                "provision": await self.provision_instances(
                    space_ref, product_ids=product_ids, apply=False, bind_after=False
                ),
                "deploy": await self.deploy_instances(
                    space_ref, product_ids=product_ids, apply=False
                ),
            }

        if ctx is not None:
            ctx = self._init_ctx(
                space_ref,
                ctx,
                total_steps=len(plan_full_steps(instances, workspace)),
                space_id=space_id,
            )

        provision_result = await self.provision_instances(
            space_ref,
            product_ids=product_ids,
            apply=True,
            edit_timeout=edit_timeout,
            ctx=ctx,
            bind_after=False,
        )
        deploy_result = await self.deploy_instances(
            space_ref,
            product_ids=product_ids,
            apply=True,
            edit_timeout=edit_timeout,
            ctx=ctx,
        )

        if ctx and ctx.active and ctx.checkpoint and ctx.run_state:
            ctx.checkpoint.mark_completed(ctx.run_state)

        return {
            "dry_run": False,
            "checkpoint": str(self._store.paths.sync_state_file(space_ref))
            if ctx and ctx.active
            else None,
            "provision": provision_result,
            "deploy": deploy_result,
        }

    async def _upload_instance_assets(
        self,
        space_id: str,
        instance: PipelineInstance,
        inst_dir: Path,
        *,
        ecommerce_raw: bool = False,
    ) -> list[dict[str, Any]]:
        uploads: list[dict[str, Any]] = []
        nodes = instance.magnific.nodes
        marker = f"Pipeline #{instance.product_id}"

        product_path = inst_dir / instance.assets.product
        if product_path.is_file():
            try:
                product_node = nodes.get("product")
                push = await push_image_and_bind(
                    self._assets,
                    self._spaces,
                    space_id=space_id,
                    space_ref=instance.product_id,
                    image_path=product_path,
                    node_id=str(product_node or ""),
                    node_label=f"Product ({marker})",
                )
                uploads.append({"kind": "product", **push})
            except Exception as exc:  # noqa: BLE001
                uploads.append({"kind": "product", "status": "error", "error": str(exc)})

        material_path = inst_dir / instance.assets.material
        if material_path.is_file():
            try:
                material_node = nodes.get("material_reference")
                push = await push_image_and_bind(
                    self._assets,
                    self._spaces,
                    space_id=space_id,
                    space_ref=instance.product_id,
                    image_path=material_path,
                    node_id=str(material_node or ""),
                    node_label=f"Material reference ({marker})",
                )
                uploads.append({"kind": "material", **push})
            except Exception as exc:  # noqa: BLE001
                uploads.append({"kind": "material", "status": "error", "error": str(exc)})

        if not ecommerce_raw:
            for bg in instance.assets.backgrounds[:5]:
                bg_path = inst_dir / bg.file
                if not bg_path.is_file():
                    continue
                try:
                    push = await self._assets.push_image(
                        instance.product_id, bg_path, space_id=space_id
                    )
                    uploads.append(
                        {
                            "kind": "background",
                            "file": bg.file,
                            "creation_id": push.get("creationIdentifier"),
                            "status": "ok",
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    uploads.append(
                        {"kind": "background", "file": bg.file, "status": "error", "error": str(exc)}
                    )
        return uploads

    def sync_status(self, space_ref: str) -> dict[str, Any]:
        checkpoint = self._checkpoint(space_ref)
        state = checkpoint.load()
        if not state:
            return {
                "space_ref": space_ref,
                "status": "no_checkpoint",
                "checkpoint_path": str(checkpoint.path),
            }
        done, total = state.progress_fraction()
        return {
            "space_ref": space_ref,
            "checkpoint_path": str(checkpoint.path),
            "run_id": state.run_id,
            "status": state.status,
            "progress": f"{done}/{total}",
            "current": state.current.model_dump() if state.current else None,
            "failed": state.failed.model_dump() if state.failed else None,
            "last_completed": state.completed[-1].model_dump() if state.completed else None,
        }
