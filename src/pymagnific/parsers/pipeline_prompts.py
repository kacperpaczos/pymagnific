"""Prompt templates for e-commerce pipelines (ecommerce_raw template SSOT)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pymagnific.schemas.workspace import PipelineInstance, SharedPrompts, WorkspaceManifest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_PATH = _REPO_ROOT / "projects" / "templates" / "ecommerce_raw" / "prompts.json"


@lru_cache(maxsize=1)
def _load_prompts_data() -> dict[str, Any]:
    if not _PROMPTS_PATH.is_file():
        return {}
    return json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))


def _bases() -> dict[str, str]:
    return dict(_load_prompts_data().get("bases") or {})


def _product_addons(kind: str) -> dict[str, str]:
    addons = _load_prompts_data().get("product_addons") or {}
    block = addons.get(kind) or {}
    return {str(k): str(v) for k, v in block.items()}


def _node_labels() -> dict[str, str]:
    return dict(_load_prompts_data().get("node_labels") or {})


def _base(name: str, default: str = "") -> str:
    return _bases().get(name) or default


COLOR_GENERATOR_BASE = _base("color_generator")
COLOR_GENERATOR_ECOMMERCE_RAW_BASE = _base("color_generator_ecommerce_raw")
COMPOSITE_INSTRUCTIONS_BASE = _base("composite_instructions")
MATERIAL_PROMPT_GENERATOR_BASE = _base("material_prompt_generator")
SHOTS_PROMPT_GENERATOR_BASE = _base("shots_prompt_generator")

_COLOR_ADDON_BY_PRODUCT = _product_addons("color")
_MATERIAL_ADDON_BY_PRODUCT = _product_addons("material")
_SHOTS_ADDON_BY_PRODUCT = _product_addons("shots")
_COMPOSITE_ADDON_BY_PRODUCT = _product_addons("composite")
_NODE_LABELS = _node_labels()


def shared_prompts_from_templates(*, ecommerce_raw: bool = False) -> SharedPrompts:
    return SharedPrompts(
        color_generator_base=(
            COLOR_GENERATOR_ECOMMERCE_RAW_BASE if ecommerce_raw else COLOR_GENERATOR_BASE
        ),
        composite_instructions_base=COMPOSITE_INSTRUCTIONS_BASE,
        material_prompt_generator_base=MATERIAL_PROMPT_GENERATOR_BASE,
        shots_prompt_generator_base=SHOTS_PROMPT_GENERATOR_BASE,
    )


def color_product_addon(product_id: str) -> str:
    return _COLOR_ADDON_BY_PRODUCT.get(str(product_id), "")


def material_product_addon(product_id: str) -> str:
    return _MATERIAL_ADDON_BY_PRODUCT.get(str(product_id), "")


def shots_product_addon(product_id: str) -> str:
    return _SHOTS_ADDON_BY_PRODUCT.get(str(product_id), "")


def composite_product_addon(product_id: str) -> str:
    return _COMPOSITE_ADDON_BY_PRODUCT.get(str(product_id), "")


def _node_ref(nodes: dict[str, str] | None, logical_key: str, fallback_phrase: str) -> str:
    if not nodes:
        return fallback_phrase
    node_id = nodes.get(logical_key)
    label = _NODE_LABELS.get(logical_key, logical_key)
    if node_id:
        return f"@[{node_id}:{label}]"
    return fallback_phrase


def build_color_generator_prompt(
    instance: PipelineInstance,
    *,
    nodes: dict[str, str] | None = None,
    ecommerce_raw: bool = False,
) -> str:
    """Full color-generator prompt for Magnific (base + product addon, optional @ ref)."""
    colors_ref = _node_ref(nodes, "colors_list", "the Colors list")
    base_template = COLOR_GENERATOR_ECOMMERCE_RAW_BASE if ecommerce_raw else COLOR_GENERATOR_BASE
    base = base_template.replace("the Colors list", colors_ref)
    addon = instance.prompts.color_generator.product_addon or color_product_addon(
        instance.product_id
    )
    if addon:
        return f"{base}\n\n{addon}".strip()
    return base


def build_material_prompt_generator_instructions(
    instance: PipelineInstance,
    *,
    nodes: dict[str, str] | None = None,
) -> str:
    mat_ref = _node_ref(nodes, "material_reference", "the Material reference")
    base = MATERIAL_PROMPT_GENERATOR_BASE.replace("the Material reference image", f"{mat_ref} image")
    base = base.replace("the Material reference", mat_ref)
    addon = (
        instance.prompts.material_prompt_generator.product_addon
        or material_product_addon(instance.product_id)
    )
    if addon:
        return f"{base}\n\n{addon}".strip()
    return base


def build_shots_prompt_generator_instructions(
    instance: PipelineInstance,
    *,
    nodes: dict[str, str] | None = None,
) -> str:
    ideas_ref = _node_ref(nodes, "shot_ideas", "the Shot ideas list")
    base = SHOTS_PROMPT_GENERATOR_BASE.replace("the Shot ideas list", ideas_ref)
    addon = (
        instance.prompts.shots_prompt_generator.product_addon
        or shots_product_addon(instance.product_id)
    )
    if addon:
        return f"{base}\n\n{addon}".strip()
    return base


def build_composite_instructions(
    instance: PipelineInstance,
    *,
    nodes: dict[str, str] | None = None,
) -> str:
    """Full composite prompt-generator instructions (legacy non-template pipelines)."""
    hints_ref = _node_ref(nodes, "placement_hints", "the Placement hints list")
    base = COMPOSITE_INSTRUCTIONS_BASE.replace("the Placement hints list", hints_ref)
    addon = (
        instance.prompts.composite_prompt_generator.product_addon
        or composite_product_addon(instance.product_id)
    )
    if addon:
        return f"{base}\n\n{addon}".strip()
    return base


def apply_prompts_to_instance(
    instance: PipelineInstance,
    workspace: WorkspaceManifest | None = None,
    *,
    nodes: dict[str, str] | None = None,
) -> PipelineInstance:
    """Refresh product_addon and full prompt fields on a PipelineInstance."""
    ecommerce_raw = workspace.uses_ecommerce_raw_template() if workspace else False

    if not instance.prompts.color_generator.product_addon:
        instance.prompts.color_generator.product_addon = color_product_addon(instance.product_id)
    if not instance.prompts.material_prompt_generator.product_addon:
        instance.prompts.material_prompt_generator.product_addon = material_product_addon(
            instance.product_id
        )
    if not instance.prompts.shots_prompt_generator.product_addon:
        instance.prompts.shots_prompt_generator.product_addon = shots_product_addon(
            instance.product_id
        )
    if not instance.prompts.composite_prompt_generator.product_addon:
        instance.prompts.composite_prompt_generator.product_addon = composite_product_addon(
            instance.product_id
        )

    if not instance.prompts.shot_ideas and instance.prompts.placement_hints:
        instance.prompts.shot_ideas = list(instance.prompts.placement_hints)

    instance.prompts.color_generator.full = build_color_generator_prompt(
        instance, nodes=nodes, ecommerce_raw=ecommerce_raw
    )
    instance.prompts.material_prompt_generator.instructions = (
        build_material_prompt_generator_instructions(instance, nodes=nodes)
    )
    instance.prompts.shots_prompt_generator.instructions = (
        build_shots_prompt_generator_instructions(instance, nodes=nodes)
    )
    if not ecommerce_raw:
        instance.prompts.composite_prompt_generator.instructions = build_composite_instructions(
            instance, nodes=nodes
        )
    return instance


def refresh_workspace_prompts(workspace: WorkspaceManifest) -> WorkspaceManifest:
    workspace.shared_prompts = shared_prompts_from_templates(
        ecommerce_raw=workspace.uses_ecommerce_raw_template()
    )
    return workspace
