"""Remote audit: instance.json + asset_bindings vs pulled .remote/board.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest
from pymagnific.templates.registry import load_template_prompts_json


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _node_by_id(board: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for n in board.get("nodes", []):
        if str(n.get("id")) == node_id:
            return n
    return None


def _props_map(board: dict[str, Any]) -> dict[tuple[str, str], Any]:
    out: dict[tuple[str, str], Any] = {}
    for p in board.get("nodeData", []):
        eid = str(p.get("elementId", ""))
        key = str(p.get("key", ""))
        if eid and key:
            out[(eid, key)] = p.get("value")
    return out


def _node_prompt(props: dict[tuple[str, str], Any], node_id: str) -> str:
    for key in ("instructions", "prompt"):
        val = props.get((node_id, key))
        if val and str(val).strip() and str(val) != "Placeholder prompt for color variations":
            return str(val).replace("\\n", "\n")
    return ""


def _checkpoint_ok(project_dir: Path, product_id: str, step_id: str) -> bool:
    cp_path = project_dir / ".sync" / "state.json"
    if not cp_path.is_file():
        return False
    state = json.loads(cp_path.read_text(encoding="utf-8"))
    return any(
        c.get("phase") == "deploy"
        and c.get("product_id") == product_id
        and c.get("step_id") == step_id
        and c.get("ok")
        for c in state.get("completed", [])
    )


def _check(
    results: list[dict[str, Any]],
    *,
    product_id: str,
    check: str,
    ok: bool,
    detail: str = "",
    severity: str = "fail",
) -> None:
    results.append(
        {
            "product_id": product_id,
            "check": check,
            "status": "ok" if ok else severity,
            "detail": detail,
        }
    )


def _audit_product_bindings(
    instance: PipelineInstance,
    props: dict[tuple[str, str], Any],
    results: list[dict[str, Any]],
) -> None:
    pid = instance.product_id
    nodes = instance.magnific.nodes
    product_node = nodes.get("product")
    if not product_node:
        return
    remote_cid = props.get((product_node, "creationIdentifier"))
    binding = (instance.magnific.asset_bindings or {}).get("product") or {}
    bound_cid = binding.get("creation_id") if isinstance(binding, dict) else None
    if bound_cid and remote_cid:
        _check(
            results,
            product_id=pid,
            check="product_binding_matches_remote",
            ok=str(bound_cid) == str(remote_cid),
            detail=f"binding={bound_cid} remote={remote_cid}",
        )
    inst_dir = Path(instance.assets.product).parent if instance.assets.product else None
    if inst_dir and isinstance(binding, dict) and binding.get("sha256"):
        prod_path = inst_dir.parent / instance.assets.product
        if prod_path.is_file():
            local_sha = _sha256(prod_path)
            _check(
                results,
                product_id=pid,
                check="product_sha256_matches_binding",
                ok=local_sha == binding.get("sha256"),
                detail=f"local={local_sha[:16]} binding={str(binding.get('sha256', ''))[:16]}",
            )


def audit_ecommerce_product(
    instance: PipelineInstance,
    board: dict[str, Any],
    props: dict[tuple[str, str], Any],
    remote_assets_dir: Path,
    project_dir: Path,
) -> list[dict[str, Any]]:
    pid = instance.product_id
    results: list[dict[str, Any]] = []
    nodes = instance.magnific.nodes

    product_id = nodes.get("product")
    shot_gen_id = nodes.get("product_shot_generator")
    _check(
        results,
        product_id=pid,
        check="bind_product_present",
        ok=bool(product_id),
        detail=f"product={product_id}",
    )
    _check(
        results,
        product_id=pid,
        check="product_ne_shot_generator",
        ok=bool(product_id and shot_gen_id and product_id != shot_gen_id),
        detail=f"product={product_id} shot_gen={shot_gen_id}",
    )

    if product_id:
        rn = _node_by_id(board, product_id)
        _check(
            results,
            product_id=pid,
            check="product_node_type_creation",
            ok=rn is not None and rn.get("type") == "creation",
            detail=f"type={rn.get('type') if rn else None} name={rn.get('name') if rn else None}",
        )
        cid = props.get((product_id, "creationIdentifier"))
        _check(
            results,
            product_id=pid,
            check="product_creation_id",
            ok=bool(cid),
            detail=f"creationIdentifier={cid}",
        )
        if cid and remote_assets_dir.is_dir():
            matches = list(remote_assets_dir.glob(f"*{cid}*"))
            _check(
                results,
                product_id=pid,
                check="product_asset_in_remote",
                ok=len(matches) > 0,
                detail=str(matches[0].name) if matches else "no file",
            )

    mat_id = nodes.get("material_reference")
    if mat_id:
        cid = props.get((mat_id, "creationIdentifier"))
        _check(
            results,
            product_id=pid,
            check="material_creation_id",
            ok=bool(cid),
            detail=f"creationIdentifier={cid}",
        )

    local_colors = [c.text for c in instance.prompts.colors]
    prep_colors = _checkpoint_ok(project_dir, pid, "prepare:colors_list")
    _check(
        results,
        product_id=pid,
        check="colors_list_prepare",
        ok=prep_colors and len(local_colors) == 3,
        detail=f"local={len(local_colors)} checkpoint_prepare={prep_colors}",
    )

    local_shots = instance.prompts.shot_ideas or instance.prompts.placement_hints
    prep_shots = _checkpoint_ok(project_dir, pid, "prepare:shot_ideas")
    _check(
        results,
        product_id=pid,
        check="shot_ideas_prepare",
        ok=prep_shots and len(local_shots) == 3,
        detail=f"local={len(local_shots)} checkpoint_prepare={prep_shots}",
    )

    cg_id = nodes.get("color_generator")
    local_prompt = (instance.prompts.color_generator.full or "").replace("\n", " ")
    remote_prompt = _node_prompt(props, cg_id).replace("\n", " ") if cg_id else ""
    remote_prompt_field = str(props.get((cg_id, "prompt"), "")).replace("\n", " ") if cg_id else ""
    _check(
        results,
        product_id=pid,
        check="color_generator_prompt",
        ok=len(local_prompt) > 50
        and len(remote_prompt) > 50
        and local_prompt[:80] == remote_prompt[:80],
        detail=f"local_len={len(local_prompt)} remote_len={len(remote_prompt)}",
    )
    _check(
        results,
        product_id=pid,
        check="color_generator_no_placeholder",
        ok="placeholder" not in remote_prompt_field.lower(),
        detail=f"prompt_field={remote_prompt_field[:60]!r}",
    )

    for img_key in ("material_generator", "product_shot_generator"):
        nid = nodes.get(img_key)
        if not nid:
            continue
        pf = str(props.get((nid, "prompt"), ""))
        _check(
            results,
            product_id=pid,
            check=f"{img_key}_no_placeholder",
            ok="placeholder" not in pf.lower() and len(pf) > 20,
            detail=f"prompt_field={pf[:60]!r}",
        )

    for key, attr in (
        ("material_prompt_generator", "material_prompt_generator"),
        ("shots_prompt_generator", "shots_prompt_generator"),
    ):
        nid = nodes.get(key)
        local_instr = getattr(instance.prompts, attr).instructions or ""
        remote_instr = _node_prompt(props, nid) if nid else ""
        _check(
            results,
            product_id=pid,
            check=f"{key}_instructions",
            ok=len(local_instr) > 30 and len(remote_instr) > 30,
            detail=f"local_len={len(local_instr)} remote_len={len(remote_instr)}",
        )

    _audit_product_bindings(instance, props, results)
    return results


def audit_do3d_product(
    instance: PipelineInstance,
    board: dict[str, Any],
    props: dict[tuple[str, str], Any],
    remote_assets_dir: Path,
    project_dir: Path,
) -> list[dict[str, Any]]:
    pid = instance.product_id
    results: list[dict[str, Any]] = []
    nodes = instance.magnific.nodes

    product_id = nodes.get("product")
    _check(
        results,
        product_id=pid,
        check="bind_product_present",
        ok=bool(product_id),
        detail=f"product={product_id}",
    )

    if product_id:
        rn = _node_by_id(board, product_id)
        _check(
            results,
            product_id=pid,
            check="product_node_type_creation",
            ok=rn is not None and rn.get("type") == "creation",
            detail=f"type={rn.get('type') if rn else None}",
        )
        cid = props.get((product_id, "creationIdentifier"))
        _check(
            results,
            product_id=pid,
            check="product_creation_id",
            ok=bool(cid),
            detail=f"creationIdentifier={cid}",
        )
        if cid and remote_assets_dir.is_dir():
            matches = list(remote_assets_dir.glob(f"*{cid}*"))
            _check(
                results,
                product_id=pid,
                check="product_asset_in_remote",
                ok=len(matches) > 0,
                detail=str(matches[0].name) if matches else "no file",
            )

    for logical_key, label in (
        ("texture_generator", "Texture generator"),
        ("print_flat_generator", "Print flat generator"),
    ):
        nid = nodes.get(logical_key)
        local_full = getattr(getattr(instance.prompts, logical_key), "full", "") or ""
        remote_prompt = _node_prompt(props, nid) if nid else ""
        prep_ok = _checkpoint_ok(project_dir, pid, f"prepare:{logical_key}")
        _check(
            results,
            product_id=pid,
            check=f"{logical_key}_prepare",
            ok=prep_ok or len(remote_prompt) > 40,
            detail=f"checkpoint={prep_ok} remote_len={len(remote_prompt)}",
        )
        _check(
            results,
            product_id=pid,
            check=f"{logical_key}_no_placeholder",
            ok="placeholder" not in remote_prompt.lower() and len(remote_prompt) > 40,
            detail=f"local_len={len(local_full)} remote={remote_prompt[:60]!r}",
        )

    _audit_product_bindings(instance, props, results)
    return results


def audit_workspace_remote(
    project_dir: Path,
    *,
    pipeline_ids: list[str] | None = None,
    pkg_root: Path | None = None,
) -> dict[str, Any]:
    workspace_path = project_dir / "workspace.json"
    if not workspace_path.is_file():
        return {"ok": False, "checks": [{"status": "fail", "detail": "missing workspace.json"}]}

    workspace = WorkspaceManifest.model_validate_json(workspace_path.read_text(encoding="utf-8"))
    template_id = workspace.template.template_id if workspace.template else ""

    remote_dir = project_dir / ".remote"
    board_path = remote_dir / "board.json"
    if not board_path.is_file():
        return {
            "ok": False,
            "space_ref": project_dir.name,
            "template_id": template_id,
            "checks": [
                {
                    "status": "fail",
                    "detail": f"missing {board_path}. Pull board (bind-nodes) before audit.",
                }
            ],
        }

    board = json.loads(board_path.read_text(encoding="utf-8"))
    props = _props_map(board)
    ids = pipeline_ids or workspace.pipeline_ids
    all_results: list[dict[str, Any]] = []

    for pid in ids:
        inst_path = project_dir / "pipelines" / pid / "instance.json"
        if not inst_path.is_file():
            _check(
                all_results,
                product_id=pid,
                check="instance.json",
                ok=False,
                detail="missing",
            )
            continue
        instance = PipelineInstance.model_validate_json(inst_path.read_text(encoding="utf-8"))
        if template_id == "do3d_textures_2d":
            all_results.extend(
                audit_do3d_product(
                    instance,
                    board,
                    props,
                    remote_dir / "assets",
                    project_dir,
                )
            )
        else:
            all_results.extend(
                audit_ecommerce_product(
                    instance,
                    board,
                    props,
                    remote_dir / "assets",
                    project_dir,
                )
            )

    fails = [r for r in all_results if r["status"] == "fail"]
    warns = [r for r in all_results if r["status"] == "warn"]
    ok = len(fails) == 0
    return {
        "ok": ok,
        "space_ref": project_dir.name,
        "template_id": template_id,
        "remote_board": str(board_path),
        "summary": {
            "total": len(all_results),
            "ok": len(all_results) - len(fails) - len(warns),
            "warn": len(warns),
            "fail": len(fails),
            "passed": ok,
        },
        "results": all_results,
    }


def load_ecommerce_prompt_bases(pkg_root: Path) -> dict[str, str]:
    """Bases from template prompts.json for instance lint."""
    data = load_template_prompts_json(pkg_root, "ecommerce_raw")
    return dict(data.get("bases") or {})
