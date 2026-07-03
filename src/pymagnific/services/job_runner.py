"""Execute pipeline jobs against Magnific Spaces (v3 workspace)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pymagnific.core.exceptions import AssetsError
from pymagnific.core.logging import get_logger
from pymagnific.parsers.stage_mapping import find_stage_node_on_board, stage_node_from_bound_nodes
from pymagnific.schemas.workspace import PipelineJob
from pymagnific.services.assets_service import AssetsService
from pymagnific.services.spaces_service import SpacesService
from pymagnific.services.workspace_store import WorkspaceStore

log = get_logger("jobs")


class JobRunner:
    def __init__(
        self,
        store: WorkspaceStore,
        assets: AssetsService,
        spaces: SpacesService,
        *,
        fetch_board: Callable[[str], Awaitable[dict[str, Any]]],
    ) -> None:
        self._store = store
        self._assets = assets
        self._spaces = spaces
        self._fetch_board = fetch_board

    async def run_instance_job(
        self,
        space_ref: str,
        job_id: str,
        *,
        space_id: str | None = None,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        workspace = self._store.load_workspace(space_ref)
        job: PipelineJob | None = None
        instance = None

        if product_id:
            instance = self._store.load_instance(space_ref, str(product_id))
            job = next((j for j in instance.jobs if j.job_id == job_id), None)
        else:
            for inst in self._store.list_instances(space_ref):
                candidate = next((j for j in inst.jobs if j.job_id == job_id), None)
                if candidate:
                    job = candidate
                    instance = inst
                    break

        if not job or not instance:
            raise AssetsError(f"Job not found in workspace instances: {job_id!r}")

        resolved_space_id = space_id or workspace.meta.space_id
        if not resolved_space_id:
            resolved_space_id = await self._assets.resolve_space_id(workspace.meta.space_ref)

        log.info(
            "exec job %s product=#%s steps=%d space=%s",
            job_id,
            instance.product_id,
            len(job.steps),
            resolved_space_id,
        )

        results: list[dict[str, Any]] = []
        for step in job.steps:
            action = step.get("action", "spaces_run")
            if action != "spaces_run":
                results.append({"step": step, "status": "skipped", "reason": "unsupported action"})
                continue

            start_node = step.get("start_node")
            if not start_node or str(start_node).endswith("-new"):
                start_node = stage_node_from_bound_nodes(
                    instance.magnific.nodes, str(step.get("stage", ""))
                )
            if not start_node:
                board = await self._fetch_board(resolved_space_id)
                start_node = find_stage_node_on_board(board, str(step.get("stage", "")))

            if not start_node:
                results.append(
                    {
                        "step": step,
                        "status": "skipped",
                        "reason": "start node not found (provision + bind nodes first)",
                    }
                )
                log.warning(
                    "job %s step %s skipped: start node not found",
                    job_id,
                    step.get("stage"),
                )
                continue

            log.info(
                "job %s step %s spaces_run start_node=%s",
                job_id,
                step.get("stage"),
                start_node,
            )
            run_result = await self._spaces.run_space(resolved_space_id, str(start_node))
            log.info(
                "job %s step %s done status=%s",
                job_id,
                step.get("stage"),
                (run_result.get("run_status") or {}).get("status")
                if isinstance(run_result.get("run_status"), dict)
                else run_result.get("run_status"),
            )
            results.append(
                {
                    "step": step,
                    "status": "ok",
                    "start_node": start_node,
                    "product_id": instance.product_id,
                    "run": run_result,
                }
            )

        return {
            "job_id": job_id,
            "product_id": instance.product_id,
            "space_id": resolved_space_id,
            "results": results,
        }

    async def run_batch(
        self,
        space_ref: str,
        *,
        phase: str | None = None,
        job_ids: list[str] | None = None,
        parallel: int = 2,
        product_ids: list[str] | None = None,
        run_job_fn: Callable[..., Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        instances = self._store.list_instances(space_ref, product_ids=product_ids)
        jobs: list[PipelineJob] = []
        for inst in instances:
            jobs.extend(j for j in inst.jobs if j.enabled)
        if phase:
            jobs = [j for j in jobs if j.phase == phase]
        if job_ids:
            wanted = set(job_ids)
            jobs = [j for j in jobs if j.job_id in wanted]
        if not jobs:
            raise AssetsError("No matching jobs to run")

        async def run_one(job: PipelineJob) -> dict[str, Any]:
            try:
                result = await run_job_fn(
                    space_ref,
                    job.job_id,
                    product_id=job.product_id,
                )
                return {
                    "job_id": job.job_id,
                    "product_id": job.product_id,
                    "status": "ok",
                    "result": result,
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "job_id": job.job_id,
                    "product_id": job.product_id,
                    "status": "error",
                    "error": str(exc),
                }

        parallel = max(1, parallel)
        if parallel == 1 or len(jobs) == 1:
            outcomes = [await run_one(j) for j in jobs]
        else:
            sem = asyncio.Semaphore(parallel)

            async def limited(job: PipelineJob) -> dict[str, Any]:
                async with sem:
                    return await run_one(job)

            outcomes = list(await asyncio.gather(*[limited(j) for j in jobs]))

        workspace = self._store.load_workspace(space_ref)
        return {
            "space_ref": space_ref,
            "space_id": workspace.meta.space_id,
            "phase": phase,
            "parallel": parallel,
            "job_count": len(jobs),
            "results": outcomes,
        }
