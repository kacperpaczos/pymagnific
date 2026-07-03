"""Build workspace layout from pipeline-spec.json (sync init)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pymagnific.parsers.jobs_from_template import jobs_for_instance
from pymagnific.parsers.pipeline_prompts import (
    apply_prompts_to_instance,
    color_product_addon,
    composite_product_addon,
    material_product_addon,
    shared_prompts_from_templates,
    shots_product_addon,
)
from pymagnific.schemas.workspace import (
    BackgroundAsset,
    ColorEntry,
    ColorGeneratorPrompt,
    CompositePromptGenerator,
    ImageGeneratorPrompt,
    MagnificInstanceBinding,
    MaterialPromptGenerator,
    PipelineAssets,
    PipelineInstance,
    PipelinePrompts,
    ShotsPromptGenerator,
    WorkspaceManifest,
    WorkspaceMeta,
    WorkspaceTemplate,
)
from pymagnific.templates.registry import template_project_path


def _repo_root(pkg_root: Path) -> Path:
    return pkg_root.parent


def _resolve_source(path_str: str, pkg_root: Path, project_dir: Path | None = None) -> Path:
    p = Path(path_str)
    if p.is_absolute() and p.is_file():
        return p
    candidates = [(_repo_root(pkg_root) / path_str).resolve(), (pkg_root / path_str).resolve()]
    if project_dir:
        candidates.insert(0, project_dir / path_str)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return p.expanduser().resolve()


def _load_template_node_properties(pkg_root: Path, template_id: str, logical_key: str) -> dict[str, Any]:
    path = template_project_path(pkg_root, template_id)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    for node in data.get("nodes", []):
        if node.get("logical_key") == logical_key:
            return dict(node.get("properties") or {})
    return {}


def _reference_entries(spec: dict[str, Any]) -> list[dict[str, Any]]:
    refs = spec.get("references")
    if isinstance(refs, list):
        return [r for r in refs if isinstance(r, dict) and r.get("id")]
    products = spec.get("assets", {}).get("products", {})
    out: list[dict[str, Any]] = []
    for ref_id, pdata in products.items():
        if isinstance(pdata, dict):
            row = dict(pdata)
            row.setdefault("id", ref_id)
            out.append(row)
    return out


def build_ecommerce_workspace_from_spec(
    spec: dict[str, Any],
    *,
    space_id: str | None = None,
    pkg_root: Path | None = None,
) -> WorkspaceManifest:
    meta = spec.get("meta", {})
    prompts = spec.get("prompts", {})
    shared = shared_prompts_from_templates(ecommerce_raw=True)
    shared.negative_fragments = prompts.get("shared", {}).get("negative_fragments", [])

    template = WorkspaceTemplate(
        template_id="ecommerce_raw",
        board_file="../templates/ecommerce_raw/board.json",
        space_id=meta.get("template_space_id") or "a22583d9-b7b4-43ff-9dbe-bca699c00fc8",
    )

    return WorkspaceManifest(
        meta=WorkspaceMeta(
            workspace_id=meta.get("space_ref", "workspace"),
            space_ref=meta.get("space_ref", "workspace"),
            space_id=space_id or meta.get("space_id"),
            description=meta.get("description"),
        ),
        template=template,
        shared_prompts=shared,
        pipeline_ids=[str(k) for k in spec.get("assets", {}).get("products", {})],
    )


def build_do3d_workspace_from_spec(
    spec: dict[str, Any],
    *,
    space_id: str | None = None,
) -> WorkspaceManifest:
    meta = spec.get("meta", {})
    refs = _reference_entries(spec)
    return WorkspaceManifest(
        meta=WorkspaceMeta(
            workspace_id=meta.get("space_ref", "do3d-textures-2d"),
            space_ref=meta.get("space_ref", "do3d-textures-2d"),
            space_id=space_id or meta.get("space_id"),
            description=meta.get("description"),
        ),
        template=WorkspaceTemplate(
            template_id="do3d_textures_2d",
            board_file="../templates/do3d_textures_2d/board.json",
            space_id=None,
        ),
        shared_prompts={},
        pipeline_ids=[str(r["id"]) for r in refs],
    )


def build_workspace_from_spec(
    spec: dict[str, Any],
    *,
    space_id: str | None = None,
    pkg_root: Path | None = None,
) -> WorkspaceManifest:
    template = spec.get("meta", {}).get("template", "ecommerce_raw")
    if template == "do3d_textures_2d":
        return build_do3d_workspace_from_spec(spec, space_id=space_id)
    return build_ecommerce_workspace_from_spec(spec, space_id=space_id, pkg_root=pkg_root)


def build_ecommerce_instance_from_spec(
    spec: dict[str, Any],
    product_id: str,
    workspace: WorkspaceManifest,
    *,
    pkg_root: Path | None = None,
) -> PipelineInstance:
    products = spec.get("assets", {}).get("products", {})
    pdata = products.get(product_id) or products.get(int(product_id))  # type: ignore[arg-type]
    if not pdata:
        raise ValueError(f"Product {product_id!r} not in pipeline-spec")

    prompts = spec.get("prompts", {})
    color_gen = prompts.get("color_variation_generator", {})
    composite = prompts.get("composite_prompt_generator", {})
    colors_by_product = prompts.get("colors_list", {}).get("entries_by_product", {})
    pilot_subset = set(prompts.get("colors_list", {}).get("pilot_subset", {}).get(product_id, []))
    placement_by_product = prompts.get("placement_hints", {}).get("entries_by_product", {})
    shot_ideas = [str(h) for h in placement_by_product.get(product_id, [])]

    mat_props = (
        _load_template_node_properties(pkg_root, "ecommerce_raw", "material_prompt_generator")
        if pkg_root
        else {}
    )
    shots_props = (
        _load_template_node_properties(pkg_root, "ecommerce_raw", "shots_prompt_generator")
        if pkg_root
        else {}
    )

    color_entries: list[ColorEntry] = []
    for entry in colors_by_product.get(product_id, []):
        if isinstance(entry, dict) and entry.get("id") and entry.get("text"):
            color_entries.append(
                ColorEntry(
                    id=str(entry["id"]),
                    text=str(entry["text"]),
                    pilot=entry["id"] in pilot_subset if pilot_subset else True,
                )
            )

    bg_files = pdata.get("paired_backgrounds_pilot", [])
    backgrounds = [
        BackgroundAsset(id=f"bg-{Path(name).stem.lower()}", file=f"assets/backgrounds/{name}")
        for name in bg_files
    ]

    name = pdata.get("name", f"Product {product_id}")
    instance = PipelineInstance(
        pipeline_id=f"pipeline-{product_id}",
        product_id=str(product_id),
        name=name,
        assets=PipelineAssets(
            product="assets/product.jpg",
            material="assets/material.jpg",
            backgrounds=backgrounds,
        ),
        prompts=PipelinePrompts(
            color_generator=ColorGeneratorPrompt(
                model=color_gen.get("model", "imagen-nano-banana-2"),
                aspect_ratio=color_gen.get("aspect_ratio", "1:1"),
                resolution=color_gen.get("resolution", "1k"),
                product_addon=color_product_addon(product_id),
                full="",
            ),
            colors=color_entries,
            placement_hints=shot_ideas,
            shot_ideas=shot_ideas,
            material_prompt_generator=MaterialPromptGenerator(
                model=str(mat_props.get("model", "CLAUDE_OPUS_4_5")),
                product_addon=material_product_addon(product_id),
                instructions="",
            ),
            shots_prompt_generator=ShotsPromptGenerator(
                model=str(shots_props.get("model", "GEMINI31_PRO")),
                product_addon=shots_product_addon(product_id),
                instructions="",
            ),
            composite_prompt_generator=CompositePromptGenerator(
                model=composite.get("model", "GEMINI31_PRO"),
                product_addon=composite_product_addon(product_id),
                instructions="",
            ),
        ),
        jobs=[],
        magnific=MagnificInstanceBinding(
            panel_name=f"Pipeline #{product_id} - {name}",
            space_id=workspace.meta.space_id,
        ),
    )
    instance.jobs = jobs_for_instance(instance, workspace, spec_jobs=spec.get("jobs", []))
    return apply_prompts_to_instance(instance, workspace)


def build_do3d_instance_from_spec(
    spec: dict[str, Any],
    ref_id: str,
    workspace: WorkspaceManifest,
) -> PipelineInstance:
    pdata: dict[str, Any] | None = None
    for row in _reference_entries(spec):
        if str(row.get("id")) == str(ref_id):
            pdata = row
            break
    if not pdata:
        raise ValueError(f"Reference {ref_id!r} not in pipeline-spec")

    gen = spec.get("generator", {})
    model = gen.get("model", "imagen-nano-banana-2-flash")
    aspect = gen.get("aspect_ratio", "1:1")
    resolution = gen.get("resolution", "1k")

    texture_prompt = str(pdata.get("texture_prompt") or pdata.get("prompts", {}).get("texture", ""))
    print_flat_prompt = str(
        pdata.get("print_flat_prompt") or pdata.get("prompts", {}).get("print_flat", "")
    )

    name = pdata.get("name") or ref_id
    instance = PipelineInstance(
        pipeline_id=f"pipeline-{ref_id}",
        product_id=str(ref_id),
        name=name,
        assets=PipelineAssets(product="assets/product.jpg", material="", backgrounds=[]),
        prompts=PipelinePrompts(
            texture_generator=ImageGeneratorPrompt(
                model=model,
                aspect_ratio=aspect,
                resolution=resolution,
                full=texture_prompt,
            ),
            print_flat_generator=ImageGeneratorPrompt(
                model=model,
                aspect_ratio=aspect,
                resolution=resolution,
                full=print_flat_prompt,
            ),
        ),
        jobs=[],
        magnific=MagnificInstanceBinding(
            panel_name=f"Pipeline #{ref_id} - {name}",
            space_id=workspace.meta.space_id,
        ),
    )
    instance.jobs = jobs_for_instance(instance, workspace)
    return instance


def build_instance_from_spec(
    spec: dict[str, Any],
    product_id: str,
    workspace: WorkspaceManifest,
    *,
    pkg_root: Path | None = None,
) -> PipelineInstance:
    template = spec.get("meta", {}).get("template", workspace.template.template_id if workspace.template else "ecommerce_raw")
    if template == "do3d_textures_2d":
        return build_do3d_instance_from_spec(spec, product_id, workspace)
    return build_ecommerce_instance_from_spec(spec, product_id, workspace, pkg_root=pkg_root)


def copy_ecommerce_instance_assets(
    instance: PipelineInstance,
    instance_dir: Path,
    spec: dict[str, Any],
    pkg_root: Path,
) -> list[str]:
    copied: list[str] = []
    products = spec.get("assets", {}).get("products", {})
    pdata = products.get(instance.product_id) or products.get(int(instance.product_id))  # type: ignore[arg-type]
    if not pdata:
        return copied

    assets_root = instance_dir / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)

    product_dest = assets_root / "product.jpg"
    product_src = _resolve_source(str(pdata.get("source_image", "")), pkg_root)
    if product_src.is_file():
        shutil.copy2(product_src, product_dest)
        copied.append(str(product_dest.relative_to(instance_dir)))

    material_dest = assets_root / "material.jpg"
    if not material_dest.is_file():
        template_material = pkg_root / "projects" / "templates" / "ecommerce_raw" / "assets" / "by-creation"
        if template_material.is_dir():
            for candidate in template_material.glob("Material_reference_*"):
                shutil.copy2(candidate, material_dest)
                copied.append(str(material_dest.relative_to(instance_dir)))
                break

    bg_dir = assets_root / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    bg_spec_dir = spec.get("assets", {}).get("backgrounds", {})
    bg_source_dir = Path(str(bg_spec_dir.get("source_dir", "")))

    for bg in instance.assets.backgrounds:
        fname = Path(bg.file).name
        dest = bg_dir / fname
        if dest.is_file():
            continue
        src: Path | None = None
        repo_bg = _repo_root(pkg_root) / "artykuly_zdjecia" / "tla_bez_produktu" / fname
        if repo_bg.is_file():
            src = repo_bg
        if not src:
            shared_bg = (
                pkg_root / "projects" / "shared" / "backgrounds" / "good_scenes_bez_produktu" / fname
            )
            if shared_bg.is_file():
                src = shared_bg
        if not src and bg_source_dir.is_dir():
            candidate = bg_source_dir / fname
            if candidate.is_file():
                src = candidate
        if src and src.is_file():
            shutil.copy2(src, dest)
            copied.append(str(dest.relative_to(instance_dir)))

    return copied


def copy_do3d_instance_assets(
    instance: PipelineInstance,
    instance_dir: Path,
    spec: dict[str, Any],
    pkg_root: Path,
    project_dir: Path,
) -> list[str]:
    copied: list[str] = []
    pdata: dict[str, Any] | None = None
    for row in _reference_entries(spec):
        if str(row.get("id")) == instance.product_id:
            pdata = row
            break
    if not pdata:
        return copied

    assets_root = instance_dir / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    product_dest = assets_root / "product.jpg"

    source = pdata.get("source_image") or f"assets/inputs/{instance.product_id}.jpg"
    product_src = _resolve_source(str(source), pkg_root, project_dir)
    if product_src.is_file():
        shutil.copy2(product_src, product_dest)
        copied.append(str(product_dest.relative_to(instance_dir)))
    return copied


def build_workspace_from_spec_files(
    workspace_dir: Path,
    spec: dict[str, Any],
    *,
    pkg_root: Path,
) -> dict[str, Any]:
    """Write workspace.json + pipelines/{id}/instance.json under workspace_dir."""
    workspace = build_workspace_from_spec(spec, pkg_root=pkg_root)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    template_id = spec.get("meta", {}).get("template", "ecommerce_raw")

    workspace_path = workspace_dir / "workspace.json"
    workspace_path.write_text(
        json.dumps(workspace.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    results: list[dict[str, Any]] = []
    for product_id in workspace.pipeline_ids:
        instance = build_instance_from_spec(spec, product_id, workspace, pkg_root=pkg_root)
        instance_dir = workspace_dir / "pipelines" / product_id
        instance_dir.mkdir(parents=True, exist_ok=True)
        if template_id == "do3d_textures_2d":
            copied = copy_do3d_instance_assets(
                instance, instance_dir, spec, pkg_root, workspace_dir
            )
        else:
            copied = copy_ecommerce_instance_assets(instance, instance_dir, spec, pkg_root)
        instance_path = instance_dir / "instance.json"
        instance_path.write_text(
            json.dumps(instance.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        row: dict[str, Any] = {
            "product_id": product_id,
            "instance_path": str(instance_path),
            "assets_copied": copied,
            "jobs": len(instance.jobs),
        }
        if template_id != "do3d_textures_2d":
            row["colors"] = len(instance.prompts.colors)
        results.append(row)

    return {
        "workspace_path": str(workspace_path),
        "pipeline_ids": workspace.pipeline_ids,
        "space_id": workspace.meta.space_id,
        "template_id": template_id,
        "instances": results,
    }
