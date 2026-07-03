#!/usr/bin/env python3
"""Audit workspace v3 instance.json vs pulled .remote/board.json."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest  # noqa: E402


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


def _checkpoint_prepare_ok(project_dir: Path, product_id: str, step_id: str) -> bool:
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
) -> None:
    results.append(
        {
            "product_id": product_id,
            "check": check,
            "status": "ok" if ok else "fail",
            "detail": detail,
        }
    )


def audit_product(
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

    colors_id = nodes.get("colors_list")
    local_colors = [c.text for c in instance.prompts.colors]
    # Magnific board export does not include list item texts in nodeData.
    prep_colors = _checkpoint_prepare_ok(project_dir, pid, "prepare:colors_list")
    _check(
        results,
        product_id=pid,
        check="colors_list_prepare",
        ok=prep_colors and len(local_colors) == 3,
        detail=f"local={len(local_colors)} checkpoint_prepare={prep_colors}",
    )

    shots_id = nodes.get("shot_ideas")
    local_shots = instance.prompts.shot_ideas or instance.prompts.placement_hints
    prep_shots = _checkpoint_prepare_ok(project_dir, pid, "prepare:shot_ideas")
    _check(
        results,
        product_id=pid,
        check="shot_ideas_prepare",
        ok=prep_shots and len(local_shots) == 3,
        detail=f"local={len(local_shots)} checkpoint_prepare={prep_shots}",
    )

    cg_id = nodes.get("color_generator")
    local_prompt = (instance.prompts.color_generator.full or "").replace("\n", " ")
    remote_prompt = _node_prompt(props, cg_id).replace("\n", " ")
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

    for img_key, label in (
        ("material_generator", "material_generator"),
        ("product_shot_generator", "product_shot_generator"),
    ):
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

    inst_dir = project_dir / "pipelines" / pid / "assets"
    prod_path = inst_dir / "product.jpg"
    if prod_path.is_file():
        _check(
            results,
            product_id=pid,
            check="local_product_asset_exists",
            ok=True,
            detail=f"sha256={_sha256(prod_path)[:16]}",
        )

    return results


def main() -> None:
    project_dir = ROOT / "projects" / "ecommerce_two_products"
    remote_dir = project_dir / ".remote"
    board_path = remote_dir / "board.json"
    if not board_path.is_file():
        print(f"Missing {board_path}. Run spaces pull first.", file=sys.stderr)
        sys.exit(1)

    board = json.loads(board_path.read_text(encoding="utf-8"))
    props = _props_map(board)
    workspace = WorkspaceManifest.model_validate_json(
        (project_dir / "workspace.json").read_text(encoding="utf-8")
    )

    all_results: list[dict[str, Any]] = []
    for pid in workspace.pipeline_ids:
        inst_path = project_dir / "pipelines" / pid / "instance.json"
        instance = PipelineInstance.model_validate_json(inst_path.read_text(encoding="utf-8"))
        all_results.extend(
            audit_product(
                instance,
                board,
                props,
                remote_dir / "assets",
                project_dir,
            )
        )

    fails = [r for r in all_results if r["status"] == "fail"]
    report = {
        "space_id": workspace.meta.space_id,
        "remote_board": str(board_path),
        "note": "List item texts are not exported in Magnific board pull; colors/shot checks use sync checkpoint.",
        "summary": {
            "total": len(all_results),
            "ok": len(all_results) - len(fails),
            "fail": len(fails),
            "passed": len(fails) == 0,
        },
        "results": all_results,
    }

    out_path = project_dir / "diff" / "audit-last.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(report["summary"], indent=2))
    if fails:
        print("\nFailures:", file=sys.stderr)
        for f in fails:
            print(f"  #{f['product_id']} {f['check']}: {f['detail']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
