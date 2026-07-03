"""Tests for pipeline prompt templates."""

from __future__ import annotations

from pymagnific.parsers.workspace_builder import (
    build_ecommerce_instance_from_spec,
    build_ecommerce_workspace_from_spec,
)
from pymagnific.parsers.pipeline_prompts import (
    build_color_generator_prompt,
    build_composite_instructions,
    color_product_addon,
)
from pymagnific.schemas.workspace import PipelineInstance, PipelinePrompts


def test_color_prompt_no_parent_uuid():
    inst = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        name="Katalogi",
        prompts=PipelinePrompts(),
    )
    prompt = build_color_generator_prompt(inst)
    assert "f63c26f2" not in prompt
    assert "the Colors list" in prompt
    assert "spiral" in color_product_addon("77").lower()


def test_color_prompt_uses_bound_node_uuid():
    inst = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        name="Katalogi",
        prompts=PipelinePrompts(),
    )
    nodes = {"colors_list": "new-uuid-123"}
    prompt = build_color_generator_prompt(inst, nodes=nodes)
    assert "@[new-uuid-123:Colors list]" in prompt
    assert "f63c26f2" not in prompt


def test_init_instance_prompts_differ_by_product(pkg_root):
    import json

    spec = json.loads((pkg_root / "tests" / "fixtures" / "pipeline-spec.json").read_text())
    ws = build_ecommerce_workspace_from_spec(spec, pkg_root=pkg_root)
    inst77 = build_ecommerce_instance_from_spec(spec, "77", ws, pkg_root=pkg_root)
    inst79 = build_ecommerce_instance_from_spec(spec, "79", ws, pkg_root=pkg_root)
    assert inst77.prompts.color_generator.full != inst79.prompts.color_generator.full
    assert "spiral" in inst77.prompts.color_generator.full.lower()
    assert "door hanger" in inst79.prompts.color_generator.full.lower()
    assert "f63c26f2" not in inst77.prompts.color_generator.full
    assert "placement-hints-list-new" not in inst79.prompts.composite_prompt_generator.instructions


def test_composite_instructions_natural_placement_ref():
    inst = PipelineInstance(
        pipeline_id="pipeline-79",
        product_id="79",
        name="Zawieszki",
        prompts=PipelinePrompts(),
    )
    text = build_composite_instructions(inst)
    assert "Placement hints list" in text
    assert "placement-hints-list-new" not in text
