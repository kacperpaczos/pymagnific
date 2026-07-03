"""Plan sync steps for progress totals and resume."""

from __future__ import annotations

from dataclasses import dataclass

from pymagnific.parsers.pipeline_spawn import build_instance_prepare_steps
from pymagnific.schemas.sync_state import SyncPhase
from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest


@dataclass(frozen=True)
class PlannedStep:
    phase: SyncPhase
    product_id: str | None
    step_id: str


def plan_provision_steps(instances: list[PipelineInstance], *, include_bind: bool) -> list[PlannedStep]:
    steps: list[PlannedStep] = []
    for inst in instances:
        steps.append(PlannedStep("provision", inst.product_id, "provision"))
        if include_bind:
            steps.append(PlannedStep("bind", inst.product_id, "bind_nodes"))
    return steps


def plan_deploy_steps(
    instances: list[PipelineInstance],
    workspace: WorkspaceManifest,
) -> list[PlannedStep]:
    do3d = workspace.uses_do3d_textures_template()
    steps: list[PlannedStep] = []
    for inst in instances:
        pid = inst.product_id
        steps.append(PlannedStep("deploy", pid, "upload:product"))
        if not do3d:
            steps.append(PlannedStep("deploy", pid, "upload:material"))
        steps.append(PlannedStep("deploy", pid, "repair"))
        for prep in build_instance_prepare_steps(inst, workspace=workspace):
            steps.append(PlannedStep("deploy", pid, prep.step_id))
    return steps


def plan_full_steps(
    instances: list[PipelineInstance],
    workspace: WorkspaceManifest,
) -> list[PlannedStep]:
    return plan_provision_steps(instances, include_bind=True) + plan_deploy_steps(
        instances, workspace
    )
