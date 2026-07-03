"""Tests for workspace builder (sync init)."""

from __future__ import annotations

import json
from pathlib import Path

from pymagnific.parsers.workspace_builder import (
    build_ecommerce_instance_from_spec,
    build_ecommerce_workspace_from_spec,
    build_workspace_from_spec_files,
)
from pymagnific.schemas.workspace import WorkspaceManifest


def _load_spec(pkg_root: Path) -> dict:
    spec_path = pkg_root / "tests" / "fixtures" / "pipeline-spec.json"
    return json.loads(spec_path.read_text(encoding="utf-8"))


def test_build_workspace_from_spec():
    spec = {
        "meta": {"space_ref": "produkty-ecommerce", "space_id": "abc-123"},
        "prompts": {
            "color_variation_generator": {"prompt_template": "BASE COLOR"},
            "composite_prompt_generator": {"instructions": "BASE COMPOSITE"},
            "shared": {"negative_fragments": ["no blur"]},
        },
        "assets": {"products": {"77": {}, "79": {}}},
    }
    ws = build_ecommerce_workspace_from_spec(spec, space_id="abc-123", pkg_root=Path("/tmp"))
    assert ws.meta.space_ref == "produkty-ecommerce"
    assert ws.pipeline_ids == ["77", "79"]
    assert ws.template is not None
    assert ws.template.template_id == "ecommerce_raw"
    assert "../templates/ecommerce_raw/board.json" in ws.template.board_file
    assert "Colors list" in ws.shared_prompts.color_generator_base
    assert ws.shared_prompts.negative_fragments == ["no blur"]


def test_build_instance_77_has_colors_with_ids(pkg_root: Path):
    spec = _load_spec(pkg_root)
    ws = build_ecommerce_workspace_from_spec(spec, space_id="test-space", pkg_root=pkg_root)
    inst = build_ecommerce_instance_from_spec(spec, "77", ws, pkg_root=pkg_root)
    assert len(inst.prompts.colors) == 3
    assert all(c.id for c in inst.prompts.colors)
    assert "spiral" in inst.prompts.color_generator.product_addon.lower()
    assert inst.prompts.color_generator.full
    assert "f63c26f2" not in inst.prompts.color_generator.full
    assert "Colors list" in inst.prompts.color_generator.full
    assert len(inst.prompts.shot_ideas) == 3
    assert inst.assets.material == "assets/material.jpg"
    assert inst.magnific.panel_name.startswith("Pipeline #77")


def test_init_workspace_writes_files(tmp_path: Path, pkg_root: Path):
    spec = _load_spec(pkg_root)
    workspace_dir = tmp_path / "produkty_ecommerce"
    workspace_dir.mkdir()

    result = build_workspace_from_spec_files(workspace_dir, spec, pkg_root=pkg_root)
    assert Path(result["workspace_path"]).is_file()
    assert (workspace_dir / "pipelines" / "77" / "instance.json").is_file()
    assert (workspace_dir / "pipelines" / "79" / "instance.json").is_file()

    ws = WorkspaceManifest.model_validate_json(
        (workspace_dir / "workspace.json").read_text(encoding="utf-8")
    )
    assert "77" in ws.pipeline_ids
    for row in result["instances"]:
        if row["product_id"] == "77":
            assert row["colors"] == 3


def test_instance_77_prepare_queries_after_init(pkg_root: Path, tmp_path: Path):
    from pymagnific.parsers.pipeline_spawn import build_instance_prepare_queries
    from pymagnific.schemas.workspace import PipelineInstance

    spec = _load_spec(pkg_root)
    workspace_dir = tmp_path / "ws"
    build_workspace_from_spec_files(workspace_dir, spec, pkg_root=pkg_root)
    ws = WorkspaceManifest.model_validate_json(
        (workspace_dir / "workspace.json").read_text(encoding="utf-8")
    )
    inst = PipelineInstance.model_validate_json(
        (workspace_dir / "pipelines" / "77" / "instance.json").read_text(encoding="utf-8")
    )
    inst.magnific.nodes = {
        "colors_list": "uuid-colors",
        "shot_ideas": "uuid-shots",
        "color_generator": "uuid-color-gen",
        "material_prompt_generator": "uuid-mat-prompt",
        "shots_prompt_generator": "uuid-shots-prompt",
    }
    queries = build_instance_prepare_queries(inst, workspace=ws)
    assert len(queries) >= 4
    assert any("uuid-colors" in q for q in queries)
    assert any("uuid-shots" in q for q in queries)
    assert inst.prompts.color_generator.full
