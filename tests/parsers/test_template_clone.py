"""Tests for ecommerce_raw template clone provision queries."""

from __future__ import annotations

from pymagnific.parsers.template_clone import build_ecommerce_raw_provision_query
from pymagnific.parsers.pipeline_spawn import build_instance_provision_query
from pymagnific.schemas.workspace import (
    ColorEntry,
    ColorGeneratorPrompt,
    MagnificInstanceBinding,
    PipelineInstance,
    PipelinePrompts,
    WorkspaceManifest,
    WorkspaceMeta,
    WorkspaceTemplate,
)


def _ecommerce_workspace() -> WorkspaceManifest:
    return WorkspaceManifest(
        meta=WorkspaceMeta(workspace_id="ws", space_ref="ws"),
        template=WorkspaceTemplate(template_id="ecommerce_raw"),
    )


def test_ecommerce_raw_provision_under_4000_chars():
    inst = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        name="Katalogi spiralowane",
        magnific=MagnificInstanceBinding(panel_name="Pipeline #77 - Katalogi spiralowane"),
    )
    query = build_ecommerce_raw_provision_query(inst)
    assert len(query) < 4000
    assert "Composite on background" in query
    assert "Do NOT add Composite" in query or "Do NOT add Composite on background" in query
    assert "Material variations" in query
    assert "Create photoshoot" in query


def test_build_instance_provision_query_uses_template_when_configured():
    inst77 = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        name="Katalogi",
        prompts=PipelinePrompts(
            color_generator=ColorGeneratorPrompt(product_addon="spiral catalog"),
            colors=[ColorEntry(id="c1", text="navy cover", pilot=True)],
            shot_ideas=["catalog on desk flat lay"],
        ),
        magnific=MagnificInstanceBinding(panel_name="Pipeline #77 - Katalogi"),
    )
    inst79 = PipelineInstance(
        pipeline_id="pipeline-79",
        product_id="79",
        name="Zawieszki",
        prompts=PipelinePrompts(
            color_generator=ColorGeneratorPrompt(product_addon="door hanger"),
            colors=[ColorEntry(id="c2", text="red cardstock", pilot=True)],
            shot_ideas=["hanger on hotel door"],
        ),
        magnific=MagnificInstanceBinding(panel_name="Pipeline #79 - Zawieszki"),
    )
    ws = _ecommerce_workspace()
    q77 = build_instance_provision_query(inst77, workspace=ws)
    q79 = build_instance_provision_query(inst79, workspace=ws)
    assert q77 != q79
    assert "Pipeline #77" in q77
    assert "Pipeline #79" in q79
    assert "Create photoshoot" in q77
    assert "Composite on background panel" not in q77
