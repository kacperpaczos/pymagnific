"""Build Magnific spaces_edit queries for pipeline instances (single shared Space)."""

from __future__ import annotations

from pymagnific.core.exceptions import AssetsError
from pymagnific.parsers.pipeline_prompts import (
    build_color_generator_prompt,
    build_composite_instructions,
    build_material_prompt_generator_instructions,
    build_shots_prompt_generator_instructions,
    material_product_addon,
    shots_product_addon,
)
from pymagnific.parsers.template_clone import (
    build_do3d_textures_provision_query,
    build_ecommerce_raw_provision_query,
)
from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest


class PrepareStep:
    """One prepare edit with stable id for checkpoint resume."""

    __slots__ = ("step_id", "query")

    def __init__(self, step_id: str, query: str) -> None:
        self.step_id = step_id
        self.query = query


def _set_image_generator_fields_query(node_id: str, node_label: str, text: str) -> str:
    """ecommerce_raw image-generators use prompt + instructions; clear Magnific placeholders."""
    return (
        f"On {node_label} node ({node_id}): set BOTH the prompt field AND the instructions "
        f"field to exactly this text. Remove any placeholder text "
        f"(e.g. 'Placeholder prompt for color variations'): {text!r}"
    )


def _material_generator_prompt(instance: PipelineInstance) -> str:
    base = (
        "Generate a material variation of the product using the prompt from the "
        "connected Material prompt list. Preserve all printed text, logos, shape, and proportions."
    )
    addon = material_product_addon(instance.product_id)
    return f"{base}\n\n{addon}".strip() if addon else base


def _product_shot_generator_prompt(instance: PipelineInstance) -> str:
    base = (
        "Generate a professional e-commerce product photograph using the prompt from the "
        "connected Shots prompt list. Preserve product design, typography, and proportions."
    )
    addon = shots_product_addon(instance.product_id)
    return f"{base}\n\n{addon}".strip() if addon else base


def build_instance_provision_query(
    instance: PipelineInstance,
    workspace: WorkspaceManifest | None = None,
) -> str:
    """Create one multiplied pipeline chain in shared Space."""
    if workspace and workspace.uses_ecommerce_raw_template():
        return build_ecommerce_raw_provision_query(instance)
    if workspace and workspace.uses_do3d_textures_template():
        return build_do3d_textures_provision_query(instance)
    template_id = workspace.template.template_id if workspace and workspace.template else "unknown"
    raise AssetsError(
        f"Unknown or missing template for provision: {template_id!r}. "
        "Use sync init with a supported template (ecommerce_raw, do3d_textures_2d)."
    )


def build_instance_prepare_steps(
    instance: PipelineInstance,
    workspace: WorkspaceManifest | None = None,
) -> list[PrepareStep]:
    """Edit steps to sync lists, prompts, and assets after upload."""
    nodes = instance.magnific.nodes
    steps: list[PrepareStep] = []
    ecommerce_raw = workspace.uses_ecommerce_raw_template() if workspace else False
    do3d = workspace.uses_do3d_textures_template() if workspace else False

    if do3d:
        tex_id = nodes.get("texture_generator")
        tex_prompt = instance.prompts.texture_generator.full
        if tex_id and tex_prompt:
            steps.append(
                PrepareStep(
                    "prepare:texture_generator",
                    _set_image_generator_fields_query(tex_id, "Texture generator", tex_prompt),
                )
            )
        flat_id = nodes.get("print_flat_generator")
        flat_prompt = instance.prompts.print_flat_generator.full
        if flat_id and flat_prompt:
            steps.append(
                PrepareStep(
                    "prepare:print_flat_generator",
                    _set_image_generator_fields_query(
                        flat_id, "Print flat generator", flat_prompt
                    ),
                )
            )
        return steps

    colors_id = nodes.get("colors_list")
    if colors_id and instance.prompts.colors:
        items = "\n".join(f"- {c.text}" for c in instance.prompts.colors)
        steps.append(
            PrepareStep(
                "prepare:colors_list",
                f"Set the list items on node Colors List ({colors_id}) to:\n{items}",
            )
        )

    shot_ideas_id = nodes.get("shot_ideas")
    shot_items = instance.prompts.shot_ideas or instance.prompts.placement_hints
    if shot_ideas_id and shot_items:
        items = "\n".join(f"- {h}" for h in shot_items)
        steps.append(
            PrepareStep(
                "prepare:shot_ideas",
                f"Set the list items on node Shot Ideas ({shot_ideas_id}) to:\n{items}",
            )
        )

    placement_id = nodes.get("placement_hints")
    if placement_id and instance.prompts.placement_hints and not ecommerce_raw:
        items = "\n".join(f"- {h}" for h in instance.prompts.placement_hints)
        steps.append(
            PrepareStep(
                "prepare:placement_hints",
                f"Set the list items on node Placement Hints ({placement_id}) to:\n{items}",
            )
        )

    color_gen_id = nodes.get("color_generator")
    full_prompt = build_color_generator_prompt(instance, nodes=nodes, ecommerce_raw=ecommerce_raw)
    if color_gen_id and full_prompt:
        steps.append(
            PrepareStep(
                "prepare:color_generator",
                _set_image_generator_fields_query(
                    color_gen_id,
                    "Color variation generator",
                    full_prompt,
                ),
            )
        )

    mat_var_id = nodes.get("material_generator")
    if mat_var_id and ecommerce_raw:
        mat_var_prompt = _material_generator_prompt(instance)
        steps.append(
            PrepareStep(
                "prepare:material_generator",
                _set_image_generator_fields_query(
                    mat_var_id,
                    "Material variation generator",
                    mat_var_prompt,
                ),
            )
        )

    shot_gen_id = nodes.get("product_shot_generator")
    if shot_gen_id and ecommerce_raw:
        shot_prompt = _product_shot_generator_prompt(instance)
        steps.append(
            PrepareStep(
                "prepare:product_shot_generator",
                _set_image_generator_fields_query(
                    shot_gen_id,
                    "Product shot generator",
                    shot_prompt,
                ),
            )
        )

    mat_gen_id = nodes.get("material_prompt_generator")
    mat_instr = build_material_prompt_generator_instructions(instance, nodes=nodes)
    if mat_gen_id and mat_instr:
        steps.append(
            PrepareStep(
                "prepare:material_prompt_generator",
                f"Update Material concepts generator node ({mat_gen_id}): set instructions to: {mat_instr!r}",
            )
        )

    shots_gen_id = nodes.get("shots_prompt_generator")
    shots_instr = build_shots_prompt_generator_instructions(instance, nodes=nodes)
    if shots_gen_id and shots_instr:
        steps.append(
            PrepareStep(
                "prepare:shots_prompt_generator",
                f"Update Shots prompt generator node ({shots_gen_id}): set instructions to: {shots_instr!r}",
            )
        )

    comp_gen_id = nodes.get("composite_prompt_generator")
    comp_instr = build_composite_instructions(instance, nodes=nodes)
    if comp_gen_id and comp_instr and not ecommerce_raw:
        steps.append(
            PrepareStep(
                "prepare:composite_prompt_generator",
                f"Update Composite prompt generator node ({comp_gen_id}): set instructions to: {comp_instr!r}",
            )
        )

    return steps


def build_instance_prepare_queries(
    instance: PipelineInstance,
    workspace: WorkspaceManifest | None = None,
) -> list[str]:
    """Return prepare edit query strings (legacy helper)."""
    return [s.query for s in build_instance_prepare_steps(instance, workspace=workspace)]


def build_instance_asset_repair_query(
    instance: PipelineInstance,
    *,
    product_creation_id: str | None,
    material_creation_id: str | None = None,
    background_creation_id: str | None = None,
    ecommerce_raw: bool = False,
    do3d_textures: bool = False,
) -> str | None:
    """Fix Product/Material/Background nodes so uploaded images show in Magnific UI."""
    if not product_creation_id and not material_creation_id and not background_creation_id:
        return None
    marker = f"Pipeline #{instance.product_id}"
    nodes = instance.magnific.nodes
    parts = [
        f"Fix asset nodes for {marker} only. Do not modify other pipelines.",
    ]
    if ecommerce_raw:
        parts.append(
            "Product and Material reference must be type creation (upload/reference photo nodes), "
            "NOT image-generator."
        )
    elif do3d_textures:
        parts.append(
            "Product must be type creation (upload/reference photo node), NOT image-generator."
        )
    else:
        parts.append(
            "Product and Background pool must be type creation (upload/reference photo nodes), "
            "NOT image-generator."
        )

    product_id = nodes.get("product")
    if product_creation_id and product_id:
        parts.append(
            f"Convert node Product ({marker}) id {product_id} to creation type. "
            f"Set creationIdentifier to {product_creation_id}."
        )
    mat_id = nodes.get("material_reference")
    if material_creation_id and mat_id:
        parts.append(
            f"Convert node Material reference ({marker}) id {mat_id} to creation type. "
            f"Set creationIdentifier to {material_creation_id}."
        )
    bg_id = nodes.get("background_pool")
    if background_creation_id and bg_id:
        parts.append(
            f"Convert node Background pool ({marker}) id {bg_id} to creation type. "
            f"Set creationIdentifier to {background_creation_id}."
        )
    if ecommerce_raw:
        parts.append("Keep all existing connections to Material, Color, and Photoshoot nodes.")
    elif do3d_textures:
        parts.append("Keep all existing connections to Texture generator and Print flat generator.")
    else:
        parts.append("Keep all existing connections to Color variation generator and Composite nodes.")
    return " ".join(parts)


def child_space_ref(parent_ref: str, product_id: str) -> str:
    """Historical per-product space naming (unused in workspace/1)."""
    return f"{parent_ref}-{product_id}"
