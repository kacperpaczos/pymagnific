"""Tests for pipeline spawn query builder (v3)."""

from __future__ import annotations

from pymagnific.parsers.pipeline_spawn import (
    PrepareStep,
    build_instance_prepare_queries,
    build_instance_prepare_steps,
    build_instance_provision_query,
    child_space_ref,
)
from pymagnific.schemas.workspace import (
    ColorEntry,
    ColorGeneratorPrompt,
    CompositePromptGenerator,
    MagnificInstanceBinding,
    PipelineInstance,
    PipelinePrompts,
    WorkspaceManifest,
    WorkspaceMeta,
    WorkspaceTemplate,
)


def test_child_space_ref():
    assert child_space_ref("produkty-ecommerce", "77") == "produkty-ecommerce-77"


def test_build_instance_provision_query_differs_77_vs_79():
  inst77 = PipelineInstance(
      pipeline_id="pipeline-77",
      product_id="77",
      name="Katalogi spiralowane",
      prompts=PipelinePrompts(
          color_generator=ColorGeneratorPrompt(
              full="spiral catalog color prompt",
              product_addon="spiral-bound catalog",
          ),
          colors=[
              ColorEntry(id="77-navy", text="deep navy blue matte cover", pilot=True),
          ],
          placement_hints=["two spiral catalogs on desk at 45 degrees"],
          composite_prompt_generator=CompositePromptGenerator(
              instructions="DL portrait catalog spiral on long edge",
          ),
      ),
      magnific=MagnificInstanceBinding(panel_name="Pipeline #77 - Katalogi"),
  )
  inst79 = PipelineInstance(
      pipeline_id="pipeline-79",
      product_id="79",
      name="Zawieszki hotelowe",
      prompts=PipelinePrompts(
          color_generator=ColorGeneratorPrompt(
              full="door hanger color prompt",
              product_addon="hotel door hanger",
          ),
          colors=[ColorEntry(id="79-red", text="bright red cardstock", pilot=True)],
          placement_hints=["hanging on hotel door handle"],
          composite_prompt_generator=CompositePromptGenerator(
              instructions="die-cut handle hole door hanger",
          ),
      ),
      magnific=MagnificInstanceBinding(panel_name="Pipeline #79 - Zawieszki"),
  )

  q77 = build_instance_provision_query(inst77)
  q79 = build_instance_provision_query(inst79)

  assert "spiral" in q77.lower() or "catalog" in q77.lower()
  assert "door hanger" in q79.lower() or "hanger" in q79.lower()
  assert q77 != q79
  assert "Composite on background" in q77
  assert "Material variations" not in q77 or "Do NOT add Material" in q77


def test_prepare_steps_have_stable_ids():
    workspace = WorkspaceManifest(
        meta=WorkspaceMeta(workspace_id="t", space_ref="t"),
        template=WorkspaceTemplate(template_id="ecommerce_raw", board_file="../ecommerce_raw/board.json"),
        pipeline_ids=["77"],
    )
    inst = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        name="Test",
        prompts=PipelinePrompts(
            colors=[ColorEntry(id="c1", text="red", pilot=True)],
            placement_hints=["on desk"],
            shot_ideas=["on desk"],
            color_generator=ColorGeneratorPrompt(full="color prompt"),
            composite_prompt_generator=CompositePromptGenerator(instructions="comp"),
        ),
        magnific=MagnificInstanceBinding(
            panel_name="Pipeline #77",
            nodes={
                "colors_list": "n-colors",
                "shot_ideas": "n-shots",
                "color_generator": "n-cg",
                "material_generator": "n-matgen",
                "product_shot_generator": "n-shotgen",
                "material_prompt_generator": "n-matprompt",
                "shots_prompt_generator": "n-shotprompt",
            },
        ),
    )
    steps = build_instance_prepare_steps(inst, workspace=workspace)
    ids = [s.step_id for s in steps]
    assert "prepare:colors_list" in ids
    assert "prepare:shot_ideas" in ids
    assert "prepare:color_generator" in ids
    assert "prepare:material_generator" in ids
    assert "prepare:product_shot_generator" in ids
    assert "prepare:material_prompt_generator" in ids
    assert "prepare:shots_prompt_generator" in ids
    assert all(isinstance(s, PrepareStep) for s in steps)
    cg_query = next(s.query for s in steps if s.step_id == "prepare:color_generator")
    assert "BOTH the prompt field AND the instructions" in cg_query
    queries = build_instance_prepare_queries(inst, workspace=workspace)
    assert queries == [s.query for s in steps]
