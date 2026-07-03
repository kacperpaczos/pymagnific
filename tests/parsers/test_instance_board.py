"""Tests for instance board node binding."""

from __future__ import annotations

from pymagnific.parsers.instance_board import bind_nodes_from_board
from pymagnific.schemas.workspace import MagnificInstanceBinding, PipelineInstance


def test_bind_nodes_by_pipeline_suffix():
    board = {
        "nodes": [
            {"id": "p1", "type": "panel", "name": "Input (Pipeline #79)"},
            {"id": "p2", "type": "panel", "name": "Change color (Pipeline #79)"},
            {"id": "n1", "type": "image-generator", "name": "Product (Pipeline #79)", "groupId": "p1"},
            {
                "id": "n2",
                "type": "list",
                "name": "Colors list (Pipeline #79)",
                "groupId": "p2",
            },
            {
                "id": "n3",
                "type": "image-generator",
                "name": "Color variation generator (Pipeline #79)",
                "groupId": "p2",
            },
        ]
    }
    instance = PipelineInstance(
        pipeline_id="pipeline-79",
        product_id="79",
        name="Zawieszki",
        magnific=MagnificInstanceBinding(panel_name="Pipeline #79 - Zawieszki"),
    )
    nodes = bind_nodes_from_board(instance, board)
    assert nodes["product"] == "n1"
    assert nodes["colors_list"] == "n2"
    assert nodes["color_generator"] == "n3"


def test_bind_ecommerce_raw_four_panels():
    """Fixture mirrors ecommerce_raw × Pipeline #77 suffix."""
    board = {
        "nodes": [
            {"id": "pi", "type": "panel", "name": "Input (Pipeline #77)"},
            {"id": "pm", "type": "panel", "name": "Material variations (Pipeline #77)"},
            {"id": "pc", "type": "panel", "name": "Change color (Pipeline #77)"},
            {"id": "pp", "type": "panel", "name": "Create photoshoot (Pipeline #77)"},
            {"id": "product", "type": "creation", "name": "Product (Pipeline #77)", "groupId": "pi"},
            {
                "id": "matref",
                "type": "creation",
                "name": "Material reference (Pipeline #77)",
                "groupId": "pi",
            },
            {"id": "shots", "type": "list", "name": "Shot ideas (Pipeline #77)", "groupId": "pi"},
            {
                "id": "matprompt",
                "type": "prompt-generator",
                "name": "Material concepts generator (Pipeline #77)",
                "groupId": "pm",
            },
            {
                "id": "matgen",
                "type": "image-generator",
                "name": "Material variation generator (Pipeline #77)",
                "groupId": "pm",
            },
            {"id": "colors", "type": "list", "name": "Colors list (Pipeline #77)", "groupId": "pc"},
            {
                "id": "colorgen",
                "type": "image-generator",
                "name": "Color variation generator (Pipeline #77)",
                "groupId": "pc",
            },
            {
                "id": "colorout",
                "type": "list",
                "name": "Color variation list (Pipeline #77)",
                "groupId": "pc",
            },
            {
                "id": "shotprompt",
                "type": "prompt-generator",
                "name": "Shots prompt generator (Pipeline #77)",
                "groupId": "pp",
            },
            {
                "id": "shotlist",
                "type": "list",
                "name": "Shots prompt list (Pipeline #77)",
                "groupId": "pp",
            },
            {
                "id": "shotgen",
                "type": "image-generator",
                "name": "Product shot generator (Pipeline #77)",
                "groupId": "pp",
            },
            {
                "id": "shotout",
                "type": "list",
                "name": "Product shot list (Pipeline #77)",
                "groupId": "pp",
            },
        ]
    }
    instance = PipelineInstance(
        pipeline_id="pipeline-77",
        product_id="77",
        name="Katalogi",
        magnific=MagnificInstanceBinding(panel_name="Pipeline #77 - Katalogi"),
    )
    nodes = bind_nodes_from_board(instance, board)
    assert nodes["product"] == "product"
    assert nodes["material_reference"] == "matref"
    assert nodes["shot_ideas"] == "shots"
    assert nodes["material_prompt_generator"] == "matprompt"
    assert nodes["material_generator"] == "matgen"
    assert nodes["colors_list"] == "colors"
    assert nodes["color_generator"] == "colorgen"
    assert nodes["color_output_list"] == "colorout"
    assert nodes["shots_prompt_generator"] == "shotprompt"
    assert nodes["shots_prompt_list"] == "shotlist"
    assert nodes["product_shot_generator"] == "shotgen"
    assert nodes["product_shot_list"] == "shotout"
    assert len(nodes) == 12
