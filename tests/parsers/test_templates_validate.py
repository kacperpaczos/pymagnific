"""Tests for template registry and validation."""

from __future__ import annotations

from pymagnific.templates.registry import list_templates, required_asset_slots
from pymagnific.templates.validate import validate_template


def test_list_templates(pkg_root):
    ids = list_templates(pkg_root)
    assert "ecommerce_raw" in ids
    assert "do3d_textures_2d" in ids


def test_validate_ecommerce_raw(pkg_root):
    result = validate_template(pkg_root, "ecommerce_raw")
    assert result["ok"] is True


def test_validate_do3d_textures(pkg_root):
    result = validate_template(pkg_root, "do3d_textures_2d")
    assert result["ok"] is True


def test_do3d_required_product_slot(pkg_root):
    slots = required_asset_slots(pkg_root, "do3d_textures_2d")
    assert any(s.slot == "product" and s.required for s in slots)
