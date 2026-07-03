"""Clone ecommerce_raw template structure into multiplied pipeline instances."""

from __future__ import annotations

from pymagnific.schemas.workspace import PipelineInstance

_MAX_QUERY_CHARS = 4000

# Canonical panel + node layout from projects/ecommerce_raw (4 panels, no Composite).
_ECOMMERCE_RAW_PANELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Input", ("Product", "Material reference", "Shot ideas")),
    (
        "Material variations",
        ("Material concepts generator", "Material variation generator"),
    ),
    (
        "Change color",
        ("Colors list", "Color variation generator", "Color variation list"),
    ),
    (
        "Create photoshoot",
        (
            "Shots prompt generator",
            "Shots prompt list",
            "Product shot generator",
            "Product shot list",
        ),
    ),
)

_ECOMMERCE_RAW_CONNECTIONS: tuple[str, ...] = (
    "Product output -> Material variation generator reference",
    "Material reference output -> Material concepts generator attachments",
    "Material concepts generator generated_prompt -> Material variation generator prompt",
    "Material variation generator output -> Color variation generator reference",
    "Colors list output-texts -> Color variation generator prompt",
    "Color variation generator output -> Color variation list images",
    "Color variation list output-images -> Shots prompt generator attachments",
    "Color variation list output-images -> Product shot generator reference",
    "Shot ideas output-texts -> Shots prompt generator prompt",
    "Shots prompt generator generated_prompt -> Shots prompt list texts",
    "Shots prompt list output-texts -> Product shot generator prompt",
    "Product shot generator output -> Product shot list images",
)


def instance_panel_label(instance: PipelineInstance) -> str:
    if instance.magnific.panel_name:
        return instance.magnific.panel_name
    if instance.name:
        return f"Pipeline #{instance.product_id} - {instance.name}"
    return f"Pipeline #{instance.product_id}"


def build_ecommerce_raw_provision_query(instance: PipelineInstance) -> str:
    """Provision one ecommerce_raw clone (Input + Material + Color + Photoshoot).

    Prompts and list items are applied later via prepare (4000 char limit).
    """
    label = instance_panel_label(instance)
    marker = f"({label})"

    panel_lines: list[str] = []
    for panel_name, nodes in _ECOMMERCE_RAW_PANELS:
        node_specs: list[str] = []
        for node_name in nodes:
            if node_name == "Product":
                node_specs.append(f"{node_name}: type creation (upload/reference), NOT image-generator")
            elif node_name == "Material reference":
                node_specs.append(
                    f"{node_name}: type creation (upload/reference), NOT image-generator"
                )
            elif node_name.endswith("list") or node_name in ("Shot ideas", "Colors list"):
                mode = "accumulate" if node_name in ("Shot ideas", "Colors list") else "replace"
                node_specs.append(f"{node_name} (list, {mode} mode, leave empty)")
            elif node_name == "Material concepts generator":
                node_specs.append(
                    f"{node_name} (prompt-generator, CLAUDE_OPUS_4_5, empty instructions)"
                )
            elif node_name == "Shots prompt generator":
                node_specs.append(f"{node_name} (prompt-generator, GEMINI31_PRO, empty instructions)")
            elif "generator" in node_name.lower():
                node_specs.append(
                    f"{node_name} (image-generator, imagen-nano-banana-2, 1k, 1:1, placeholder prompt)"
                )
            else:
                node_specs.append(node_name)
        panel_lines.append(f"- {panel_name} {marker}: " + "; ".join(node_specs))

    connections = "\n".join(f"- {c}" for c in _ECOMMERCE_RAW_CONNECTIONS)

    query = f"""Add a new independent e-commerce pipeline for {label} matching the ecommerce_raw template.

Create exactly 4 workflow panels {marker} with these nodes:
{chr(10).join(panel_lines)}

Wire connections for {label} only:
{connections}

Product and Material reference MUST be creation nodes. Do NOT add Composite on background.
Do NOT modify existing panels or other product pipelines. Label every node with {marker}."""

    if len(query) > _MAX_QUERY_CHARS:
        raise ValueError(
            f"ecommerce_raw provision query exceeds {_MAX_QUERY_CHARS} chars ({len(query)})"
        )
    return query


_DO3D_TEXTURES_PANELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Input", ("Product",)),
    ("Extract 2D", ("Texture generator", "Print flat generator")),
)

_DO3D_TEXTURES_CONNECTIONS: tuple[str, ...] = (
    "Product output -> Texture generator reference",
    "Product output -> Print flat generator reference",
)


def build_do3d_textures_provision_query(instance: PipelineInstance) -> str:
    """Provision one do3d_textures_2d clone (Input + 2 image-generators)."""
    label = instance_panel_label(instance)
    marker = f"({label})"

    panel_lines: list[str] = []
    for panel_name, nodes in _DO3D_TEXTURES_PANELS:
        node_specs: list[str] = []
        for node_name in nodes:
            if node_name == "Product":
                node_specs.append(f"{node_name}: type creation (upload/reference), NOT image-generator")
            elif "generator" in node_name.lower():
                node_specs.append(
                    f"{node_name} (image-generator, imagen-nano-banana-2-flash, 1k, 1:1, placeholder prompt)"
                )
            else:
                node_specs.append(node_name)
        panel_lines.append(f"- {panel_name} {marker}: " + "; ".join(node_specs))

    connections = "\n".join(f"- {c}" for c in _DO3D_TEXTURES_CONNECTIONS)

    query = f"""Add a new independent 2D texture extraction pipeline for {label}.

Create exactly 2 workflow panels {marker} with these nodes:
{chr(10).join(panel_lines)}

Wire connections for {label} only:
{connections}

Product MUST be a creation node. Texture generator and Print flat generator are image-generator nodes.
Do NOT add color lists, photoshoot panels, or composite panels.
Do NOT modify existing panels or other pipelines. Label every node with {marker}."""

    if len(query) > _MAX_QUERY_CHARS:
        raise ValueError(
            f"do3d_textures provision query exceeds {_MAX_QUERY_CHARS} chars ({len(query)})"
        )
    return query
