"""Tests for do3d_textures_2d template and migration."""

from __future__ import annotations

import json
from pathlib import Path

from pymagnific.parsers.jobs_from_template import build_do3d_textures_jobs
from pymagnific.parsers.pipeline_spawn import (
    build_instance_prepare_steps,
    build_instance_provision_query,
)
from pymagnific.parsers.template_clone import build_do3d_textures_provision_query
from pymagnific.parsers.workspace_builder import build_workspace_from_spec_files
from pymagnific.schemas.workspace import (
    ImageGeneratorPrompt,
    MagnificInstanceBinding,
    PipelineInstance,
    PipelinePrompts,
    WorkspaceManifest,
    WorkspaceMeta,
    WorkspaceTemplate,
)


def _do3d_workspace() -> WorkspaceManifest:
    return WorkspaceManifest(
        meta=WorkspaceMeta(workspace_id="do3d", space_ref="do3d-textures-2d"),
        template=WorkspaceTemplate(template_id="do3d_textures_2d"),
    )


def test_do3d_provision_under_4000_chars():
    inst = PipelineInstance(
        pipeline_id="pipeline-738-teczki-a4-klasyczne-1",
        product_id="738-teczki-a4-klasyczne-1",
        name="Teczki A4 klasyczne 1",
        magnific=MagnificInstanceBinding(
            panel_name="Pipeline #738-teczki-a4-klasyczne-1 - Teczki A4"
        ),
    )
    query = build_do3d_textures_provision_query(inst)
    assert len(query) < 4000
    assert "Texture generator" in query
    assert "Print flat generator" in query
    assert "Extract 2D" in query


def test_do3d_jobs_two_stages():
    inst = PipelineInstance(
        pipeline_id="pipeline-x",
        product_id="x",
        name="Test",
    )
    jobs = build_do3d_textures_jobs(inst)
    assert len(jobs) == 1
    stages = [s["stage"] for s in jobs[0].steps]
    assert stages == ["stage_texture", "stage_print_flat"]


def test_do3d_prepare_sets_both_generators():
    inst = PipelineInstance(
        pipeline_id="pipeline-x",
        product_id="x",
        prompts=PipelinePrompts(
            texture_generator=ImageGeneratorPrompt(full="texture prompt"),
            print_flat_generator=ImageGeneratorPrompt(full="flat prompt"),
        ),
        magnific=MagnificInstanceBinding(
            nodes={
                "texture_generator": "tex-uuid",
                "print_flat_generator": "flat-uuid",
            }
        ),
    )
    steps = build_instance_prepare_steps(inst, workspace=_do3d_workspace())
    ids = {s.step_id for s in steps}
    assert "prepare:texture_generator" in ids
    assert "prepare:print_flat_generator" in ids


def test_build_instance_provision_uses_do3d_template():
    inst = PipelineInstance(
        pipeline_id="pipeline-x",
        product_id="x",
        magnific=MagnificInstanceBinding(panel_name="Pipeline #x - Test"),
    )
    q = build_instance_provision_query(inst, workspace=_do3d_workspace())
    assert "Extract 2D" in q
    assert "Color variation" not in q


def test_init_do3d_minimal_spec(tmp_path: Path, pkg_root: Path):
    spec = {
        "meta": {
            "space_ref": "do3d-textures-2d",
            "template": "do3d_textures_2d",
        },
        "generator": {"model": "imagen-nano-banana-2-flash"},
        "references": [
            {
                "id": "ref-1",
                "name": "Ref 1",
                "texture_prompt": "tex",
                "print_flat_prompt": "flat",
            }
        ],
    }
    project = tmp_path / "do3d_textures_2d"
    project.mkdir()
    src = project / "assets" / "inputs"
    src.mkdir(parents=True)
    (src / "ref-1.jpg").write_bytes(b"fake")
    spec["references"][0]["source_image"] = "assets/inputs/ref-1.jpg"

    result = build_workspace_from_spec_files(project, spec, pkg_root=pkg_root)
    assert result["pipeline_ids"] == ["ref-1"]
    ws = json.loads((project / "workspace.json").read_text())
    assert ws["template"]["template_id"] == "do3d_textures_2d"
    inst = json.loads((project / "pipelines" / "ref-1" / "instance.json").read_text())
    assert inst["prompts"]["texture_generator"]["full"] == "tex"
    assert (project / "pipelines" / "ref-1" / "assets" / "product.jpg").is_file()
