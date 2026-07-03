#!/usr/bin/env python3
"""Bootstrap do3d_textures_2d: pipeline-spec + sync init from assets/inputs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = PKG_ROOT / "projects" / "do3d_textures_2d"
PROMPTS_PY = PKG_ROOT / "projects" / "templates" / "do3d_textures_2d" / "prompts.py"


def _load_texture_extractor():
    spec = importlib.util.spec_from_file_location("texture_extractor", PROMPTS_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {PROMPTS_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_pipeline_spec() -> dict:
    tex = _load_texture_extractor()
    inputs = sorted((PROJECT_DIR / "assets" / "inputs").glob("*.jpg"))
    if not inputs:
        raise SystemExit(f"No JPG in {PROJECT_DIR / 'assets' / 'inputs'}")

    references = []
    for f in inputs:
        ref_id = f.stem
        slug = tex.slug_from_filename(f.name)
        cat = tex.category_key(slug)
        pk_id = tex.product_id_from_filename(f.name)
        references.append(
            {
                "id": ref_id,
                "product_id": pk_id,
                "name": slug.replace("-", " ").title(),
                "category": cat,
                "source_image": f"assets/inputs/{f.name}",
                "texture_prompt": tex.build_prompt(f.name, "texture"),
                "print_flat_prompt": tex.build_prompt(f.name, "print_flat"),
            }
        )

    return {
        "$schema": "pipeline-spec/v1",
        "meta": {
            "name": "do3d-textures-2d",
            "description": (
                "Jeden Magnific Space, 53 pipeline'y — każdy generuje texture + print_flat "
                "z jednej referencji produktu."
            ),
            "space_ref": "do3d-textures-2d",
            "space_id": None,
            "status": "ready_review",
            "template": "do3d_textures_2d",
        },
        "generator": {
            "model": "imagen-nano-banana-2-flash",
            "aspect_ratio": "1:1",
            "resolution": "1k",
        },
        "references": references,
    }


def main() -> None:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from pymagnific.parsers.workspace_builder import build_workspace_from_spec_files

    spec = build_pipeline_spec()
    spec_path = PROJECT_DIR / "pipeline-spec-draft.json"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {spec_path} ({len(spec['references'])} references)")

    result = build_workspace_from_spec_files(PROJECT_DIR, spec, pkg_root=PKG_ROOT)
    print(json.dumps({k: result[k] for k in ("workspace_path", "pipeline_ids", "space_id")}, indent=2))
    print(f"instances: {len(result['instances'])}")


if __name__ == "__main__":
    main()
