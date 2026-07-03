"""Prompt templates for e-commerce pipelines (v3 / ecommerce_raw).

Based on the working per-product spawn flow: natural node references (no parent Space UUIDs),
product-specific addons for #77 / #79, and optional @[uuid:Name] refs after node bind.
"""

from __future__ import annotations

from pymagnific.schemas.workspace import PipelineInstance, SharedPrompts, WorkspaceManifest

# Working spawn prompts (produkty-ecommerce-77/79) - no hardcoded Magnific UUIDs.
COLOR_GENERATOR_BASE = (
    "You are an expert in visual editing for printed products. Analyze the reference "
    "image and generate the color variation requested by the Colors list. Change ONLY "
    "the cover/background color as specified. Preserve exactly: all printed text, logos, "
    "illustrations, spot UV or embossing effects, product shape, spiral binding or "
    "die-cut hole, proportions, lighting, perspective, and camera angle. Ensure "
    "realistic shadows and highlights. Result must be commercially usable e-commerce "
    "product photography."
)

# ecommerce_raw color prompt (shorter base when using template flow)
COLOR_GENERATOR_ECOMMERCE_RAW_BASE = (
    "You are an expert in visual editing for printed products. Analyze the product "
    "reference and generate the color variation requested by the Colors list. Change "
    "only the cover/cardstock or paper stock color as specified, preserving shape, "
    "proportions, lighting, perspective, all printed text, logos, illustrations, "
    "structural details (binding, perforation, die-cuts, flaps, coatings), and "
    "realistic shadows. Result must be clean, professional e-commerce photography."
)

COMPOSITE_INSTRUCTIONS_BASE = (
    "You are a precision assistant for Nano Banana Pro image compositing. You receive: "
    "(1) a product color-variant reference image, (2) a background scene image without "
    "any product, (3) placement hints from the Placement hints list. Generate ONE "
    "instruction to place the product naturally into the background. Preserve exactly: "
    "all printed text, logos, illustrations, correct aspect ratio, product proportions, "
    "and structural details (binding, perforation, die-cuts, flaps, coatings). Match "
    "background perspective, lighting direction, shadow softness. Product should occupy "
    "roughly 30-50% of frame. Do NOT regenerate or alter the background pixels. Do NOT "
    "change product design - only position, scale, rotation, and realistic contact shadow."
)

MATERIAL_PROMPT_GENERATOR_BASE = (
    "You are a precision assistant for generating instructions for the Nano Banana Pro "
    "image model. Analyze the product reference and the Material reference image. "
    "Generate a single instruction that recreates the product photo with one change: "
    "the surface finish or paper texture of the printed product must match the "
    "Material reference. Describe faithfully from the reference: composition, framing, "
    "lighting, shadows, background, and camera angle. Replace ONLY the cover/cardstock "
    "or paper surface material and texture. Preserve exactly all printed text, logos, "
    "illustrations, product shape, structural details, and proportions."
)

SHOTS_PROMPT_GENERATOR_BASE = (
    "You are a precision assistant for generating product photography instructions for "
    "Nano Banana Pro. You receive color-variant product images and shot ideas from "
    "the Shot ideas list. Generate ONE detailed instruction for a professional "
    "e-commerce product photograph. Preserve exactly all printed text, logos, "
    "illustrations, correct aspect ratio, product proportions, and structural details. "
    "Match scene perspective, lighting direction, and shadow softness. "
    "Do NOT alter product design — only scene, placement, and styling per the shot idea."
)

_COLOR_ADDON_BY_PRODUCT: dict[str, str] = {
    "77": (
        "Product: DL portrait spiral-bound catalog (~0.47 aspect). White metal spiral on "
        "the long edge. Change ONLY cover color per Colors list. Keep white spiral coil "
        "unless a color entry says otherwise. Do not alter MOMENTS typography or the "
        "central perfume-bottle illustration."
    ),
    "79": (
        "Product: hotel door hanger with rounded top and circular handle cutout. Change "
        "ONLY cardstock background color per Colors list. Preserve all typography "
        "(Do Not Disturb, Welcome, Come In), moon/sun icons, and die-cut shape."
    ),
    "206": (
        "Product: carbonless (NCR) single-copy business form pad, stapled or glued along "
        "the top edge, perforated pages. Change ONLY the paper stock color per Colors "
        "list. Preserve all printed ruled lines, numbering, field labels, header text, "
        "and the binding/perforation edge exactly."
    ),
    "738": (
        "Product: classic A4 presentation folder with two inner pockets and a flap "
        "closure. Change ONLY the cover cardstock color per Colors list. Preserve die-cut "
        "pocket slits, flap shape, any embossed or printed logo, and corner proportions."
    ),
    "947": (
        "Product: die-cut premium flyer with selective spot UV 3D gloss coating over "
        "part of the print. Change ONLY the base print background color per Colors list. "
        "Preserve the spot UV pattern position and sheen, all typography, and the exact "
        "cut/die shape."
    ),
    "828": (
        "Product: small paper hangtag with a punched eyelet hole and string/ribbon loop. "
        "Change ONLY the cardstock color per Colors list. Preserve the eyelet position, "
        "string/ribbon, all printed text and logo, and the tag's die-cut outline."
    ),
    "130": (
        "Product: classic folding carton / rigid box with visible die-cut structure and "
        "closure flaps. Change ONLY the exterior cardstock/cardboard color per Colors "
        "list. Preserve all die-cut lines, flap folds, printed branding, and box "
        "proportions."
    ),
}

_MATERIAL_ADDON_BY_PRODUCT: dict[str, str] = {
    "77": (
        "Printed catalog cover: apply paper/coating texture from Material reference only "
        "to the cover surface. Keep spiral binding metal finish unchanged unless the "
        "material reference clearly shows coated stock."
    ),
    "79": (
        "Printed door hanger cardstock: apply paper texture from Material reference to "
        "the hanger body. Preserve die-cut hole and all typography."
    ),
    "206": (
        "Carbonless form pad: apply paper/coating texture from Material reference only "
        "to the visible top-sheet surface. Keep the perforation and binding edge "
        "unchanged unless the material reference clearly shows a different stock."
    ),
    "738": (
        "Presentation folder cover: apply cardstock lamination/texture (matte, gloss, or "
        "soft-touch) from Material reference to the outer cover only. Keep inner pockets "
        "and flap shape unchanged."
    ),
    "947": (
        "Flyer base stock: apply paper texture from Material reference to the non-UV "
        "printed area only. Keep the spot UV 3D coating glossy and untouched by the "
        "texture change."
    ),
    "828": (
        "Hangtag cardstock: apply paper texture from Material reference to the tag body "
        "only. Keep the eyelet, string/ribbon, and die-cut outline unchanged."
    ),
    "130": (
        "Box exterior: apply cardboard/cardstock texture (matte, gloss, or kraft) from "
        "Material reference to the outer box surface only. Keep die-cut lines and flap "
        "folds unchanged."
    ),
}

_SHOTS_ADDON_BY_PRODUCT: dict[str, str] = {
    "77": (
        "Scenes: desk, shelf, or flat lay for spiral-bound DL catalog. Portrait format "
        "~0.47 aspect. Show spiral binding clearly."
    ),
    "79": (
        "Scenes: hotel door, reception counter, or flat lay for door hanger. Show handle "
        "hole and hanger proportions."
    ),
    "206": (
        "Scenes: office desk with pen, filing cabinet, or retail counter for carbonless "
        "form pad. Landscape framing. Show perforation and binding edge clearly."
    ),
    "738": (
        "Scenes: office desk, meeting table, or shelf for A4 presentation folder. "
        "Landscape framing. Show pocket openings and flap closure."
    ),
    "947": (
        "Scenes: flat lay on desk, held in hand, or stacked on a counter for premium "
        "flyer. Landscape framing. Show the spot UV gloss catching light."
    ),
    "828": (
        "Scenes: hanging from a product loop, flat lay on fabric or table, or a small "
        "stack for paper hangtag. Landscape framing. Show the string/ribbon loop."
    ),
    "130": (
        "Scenes: on a shelf, stacked, or on a shipping/packing table for classic box. "
        "Landscape framing. Show die-cut structure and closure flaps."
    ),
}

_COMPOSITE_ADDON_BY_PRODUCT: dict[str, str] = {
    "77": (
        "Placement context: spiral catalog on desk, shelf, or flat lay. Portrait DL "
        "format (~0.47 aspect). Preserve spiral binding and all cover print."
    ),
    "79": (
        "Placement context: door hanger on hotel door, reception counter, or flat lay. "
        "Preserve handle hole and hanger proportions."
    ),
}

_NODE_LABELS: dict[str, str] = {
    "colors_list": "Colors list",
    "placement_hints": "Placement hints",
    "shot_ideas": "Shot ideas",
    "material_reference": "Material reference",
}


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
    """Full composite prompt-generator instructions."""
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
