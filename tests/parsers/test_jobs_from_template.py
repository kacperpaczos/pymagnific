"""Tests for ecommerce_raw job builder."""

from __future__ import annotations

from pymagnific.parsers.jobs_from_template import build_ecommerce_raw_jobs, jobs_for_instance
from pymagnific.schemas.workspace import (
    ColorEntry,
    PipelineInstance,
    PipelinePrompts,
    WorkspaceManifest,
    WorkspaceMeta,
    WorkspaceTemplate,
)


def test_ecommerce_jobs_no_composite():
    inst = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        prompts=PipelinePrompts(
            colors=[
                ColorEntry(id="77-navy", text="navy", pilot=True),
                ColorEntry(id="77-kraft", text="kraft", pilot=True),
            ],
            shot_ideas=["desk flat lay", "shelf shot"],
        ),
    )
    jobs = build_ecommerce_raw_jobs(inst)
    assert jobs
    for job in jobs:
        stages = [s.get("stage") for s in job.steps]
        assert "stage_composite" not in stages
        assert "stage_color" in stages
        assert "stage_photoshoot" in stages


def test_jobs_for_instance_uses_template_when_ecommerce_raw():
    ws = WorkspaceManifest(
        meta=WorkspaceMeta(workspace_id="ws", space_ref="ws"),
        template=WorkspaceTemplate(template_id="ecommerce_raw"),
    )
    inst = PipelineInstance(
        pipeline_id="pipeline-79",
        product_id="79",
        prompts=PipelinePrompts(
            colors=[ColorEntry(id="79-red", text="red", pilot=True)],
            shot_ideas=["hotel door"],
        ),
    )
    jobs = jobs_for_instance(inst, ws, spec_jobs=[{"job_id": "legacy", "product_id": "79", "steps": []}])
    assert len(jobs) == 1
    assert jobs[0].job_id.startswith("pilot-79")
