"""Canonical e-commerce node names, logical keys, and bind patterns."""

from __future__ import annotations

from typing import Any

# logical_key -> magnific display name + bind name fragments + optional type rules
NODE_SPECS: dict[str, dict[str, Any]] = {
    "product": {
        "magnific_name": "Product",
        "bind_patterns": ("product",),
        "types": ("creation", "image-generator"),
    },
    "material_reference": {
        "magnific_name": "Material reference",
        "bind_patterns": ("material reference",),
        "types": ("creation", "image-generator"),
    },
    "shot_ideas": {
        "magnific_name": "Shot ideas",
        "bind_patterns": ("shot ideas",),
        "types": ("list",),
    },
    "material_prompt_generator": {
        "magnific_name": "Material concepts generator",
        "bind_patterns": ("material concepts generator",),
        "types": ("prompt-generator",),
    },
    "material_generator": {
        "magnific_name": "Material variation generator",
        "bind_patterns": ("material variation generator",),
        "types": ("image-generator",),
    },
    "colors_list": {
        "magnific_name": "Colors list",
        "bind_patterns": ("colors list",),
        "types": ("list",),
    },
    "color_generator": {
        "magnific_name": "Color variation generator",
        "bind_patterns": ("color variation generator",),
        "types": ("image-generator",),
    },
    "color_output_list": {
        "magnific_name": "Color variation list",
        "bind_patterns": ("color variation list",),
        "types": ("list",),
    },
    "shots_prompt_generator": {
        "magnific_name": "Shots prompt generator",
        "bind_patterns": ("shots prompt generator",),
        "types": ("prompt-generator",),
    },
    "shots_prompt_list": {
        "magnific_name": "Shots prompt list",
        "bind_patterns": ("shots prompt list",),
        "types": ("list",),
    },
    "product_shot_generator": {
        "magnific_name": "Product shot generator",
        "bind_patterns": ("product shot generator",),
        "types": ("image-generator",),
    },
    "product_shot_list": {
        "magnific_name": "Product shot list",
        "bind_patterns": ("product shot list",),
        "types": ("list",),
    },
    # Legacy Composite v3
    "placement_hints": {
        "magnific_name": "Placement hints",
        "bind_patterns": ("placement hints",),
        "types": ("list",),
    },
    "background_pool": {
        "magnific_name": "Background pool",
        "bind_patterns": ("background pool",),
        "types": ("creation", "image-generator"),
    },
    "composite_prompt_generator": {
        "magnific_name": "Composite prompt generator",
        "bind_patterns": ("composite prompt generator",),
        "types": ("prompt-generator",),
    },
    "composite_prompt_list": {
        "magnific_name": "Composite prompt list",
        "bind_patterns": ("composite prompt list",),
        "types": ("list",),
    },
    "composite_generator": {
        "magnific_name": "Composite generator",
        "bind_patterns": ("composite generator",),
        "types": ("image-generator",),
    },
    "composite_output_list": {
        "magnific_name": "Composite output list",
        "bind_patterns": ("composite output list",),
        "types": ("list",),
    },
    "texture_generator": {
        "magnific_name": "Texture generator",
        "bind_patterns": ("texture generator",),
        "types": ("image-generator",),
    },
    "print_flat_generator": {
        "magnific_name": "Print flat generator",
        "bind_patterns": ("print flat generator",),
        "types": ("image-generator",),
    },
}

KNOWN_LOGICAL_KEYS: dict[str, str] = {
    spec["magnific_name"]: key for key, spec in NODE_SPECS.items()
}

BIND_PATTERNS: dict[str, tuple[str, ...]] = {
    key: tuple(spec["bind_patterns"]) for key, spec in NODE_SPECS.items()
}

TYPE_OVERRIDES: dict[str, tuple[str, ...]] = {
    key: tuple(spec["types"])
    for key, spec in NODE_SPECS.items()
    if len(spec.get("types", ())) > 1
}

PROMPT_GENERATOR_KEYS = frozenset(
    k for k, spec in NODE_SPECS.items() if spec.get("types") == ("prompt-generator",)
)

LIST_KEYS = frozenset(k for k, spec in NODE_SPECS.items() if spec.get("types") == ("list",))

IMAGE_GENERATOR_KEYS = frozenset(
    k for k, spec in NODE_SPECS.items() if spec.get("types") == ("image-generator",)
)
