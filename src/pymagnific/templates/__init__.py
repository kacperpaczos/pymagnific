"""Magnific pipeline template registry and validation."""

from pymagnific.templates.registry import (
    list_templates,
    load_template_meta,
    required_asset_slots,
    template_dir,
)
from pymagnific.templates.validate import validate_template, validate_workspace

__all__ = [
    "list_templates",
    "load_template_meta",
    "required_asset_slots",
    "template_dir",
    "validate_template",
    "validate_workspace",
]
