"""Validate templates and workspace instances."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest
from pymagnific.templates.audit import load_ecommerce_prompt_bases
from pymagnific.templates.registry import (
    list_templates,
    load_template_meta,
    load_template_prompts_json,
    required_asset_slots,
    template_dir,
    template_panel_names,
    template_required_nodes,
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _check(
    results: list[dict[str, Any]],
    *,
    scope: str,
    check: str,
    ok: bool,
    detail: str = "",
    severity: str = "fail",
) -> None:
    results.append(
        {
            "scope": scope,
            "check": check,
            "status": "ok" if ok else severity,
            "detail": detail,
        }
    )


def _board_panel_names(board: dict[str, Any]) -> set[str]:
    return {
        str(n.get("name"))
        for n in board.get("nodes", [])
        if n.get("type") == "panel" and n.get("name")
    }


def _panel_in_board(panel_name: str, board_panels: set[str]) -> bool:
    if panel_name in board_panels:
        return True
    return any(
        bp == panel_name or bp.startswith(f"{panel_name} ") or bp.startswith(f"{panel_name}(")
        for bp in board_panels
    )


def validate_template(pkg_root: Path, template_id: str) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    try:
        tdir = template_dir(pkg_root, template_id)
    except FileNotFoundError as exc:
        return {"template_id": template_id, "ok": False, "checks": [{"status": "fail", "detail": str(exc)}]}

    for name in ("template.json", "board.json", "project.json"):
        _check(results, scope=template_id, check=f"file:{name}", ok=(tdir / name).is_file())

    meta = load_template_meta(pkg_root, template_id)
    schema = str(meta.get("schema_version", ""))
    _check(
        results,
        scope=template_id,
        check="schema_version",
        ok=schema == "template/1",
        detail=schema,
    )

    project = json.loads((tdir / "project.json").read_text(encoding="utf-8"))
    project_schema = str((project.get("meta") or {}).get("schema_version", ""))
    _check(
        results,
        scope=template_id,
        check="project_schema_version",
        ok=project_schema == "space-project/1",
        detail=project_schema,
    )

    logical_keys = {n.get("logical_key") for n in project.get("nodes", []) if n.get("logical_key")}
    for node_key in template_required_nodes(pkg_root, template_id):
        _check(
            results,
            scope=template_id,
            check=f"required_node:{node_key}",
            ok=node_key in logical_keys,
            detail=node_key,
        )

    slots = required_asset_slots(pkg_root, template_id)
    for slot in slots:
        _check(
            results,
            scope=template_id,
            check=f"slot:{slot.slot}",
            ok=slot.logical_key in logical_keys or slot.slot == "product",
            detail=slot.logical_key,
        )

    prompts_py = tdir / "prompts.py"
    prompts_json = tdir / "prompts.json"
    _check(
        results,
        scope=template_id,
        check="prompts_file",
        ok=prompts_py.is_file() or prompts_json.is_file(),
        detail="prompts.py|prompts.json",
    )

    if prompts_json.is_file():
        pdata = load_template_prompts_json(pkg_root, template_id)
        bases = pdata.get("bases") or {}
        _check(
            results,
            scope=template_id,
            check="prompts_bases_nonempty",
            ok=bool(bases) and all(len(str(v)) > 20 for v in bases.values()),
            detail=f"bases={len(bases)}",
        )

    board_path = tdir / "board.json"
    if board_path.is_file():
        board = json.loads(board_path.read_text(encoding="utf-8"))
        board_panels = _board_panel_names(board)
        for panel_name in template_panel_names(pkg_root, template_id):
            _check(
                results,
                scope=template_id,
                check=f"panel:{panel_name}",
                ok=_panel_in_board(panel_name, board_panels),
                detail=panel_name,
            )

    ok = all(r["status"] == "ok" for r in results)
    return {"template_id": template_id, "ok": ok, "checks": results}


def _lint_instance_prompts(
    results: list[dict[str, Any]],
    *,
    scope: str,
    instance: PipelineInstance,
    bases: dict[str, str],
) -> None:
    """Warn when canonical base prompts are copied into instance.json."""
    color_full = instance.prompts.color_generator.full or ""
    raw_base = bases.get("color_generator_ecommerce_raw") or bases.get("color_generator") or ""
    if raw_base and raw_base[:80] in color_full and len(color_full) > len(raw_base) + 50:
        _check(
            results,
            scope=scope,
            check="lint:color_generator_base_in_instance",
            ok=False,
            severity="warn",
            detail="base prompt duplicated in instance.json; use template at runtime",
        )
    mat_instr = instance.prompts.material_prompt_generator.instructions or ""
    mat_base = bases.get("material_prompt_generator") or ""
    if mat_base and mat_base[:80] in mat_instr:
        _check(
            results,
            scope=scope,
            check="lint:material_base_in_instance",
            ok=False,
            severity="warn",
            detail="material base duplicated in instance.json",
        )


def _check_deploy_status(
    results: list[dict[str, Any]],
    *,
    scope: str,
    instance: PipelineInstance,
    project_dir: Path,
) -> None:
    pid = instance.product_id
    status = instance.deploy_status
    has_checkpoint = checkpoint_has_upload(project_dir, pid)
    if status in ("uploaded", "prepared", "ready") and not has_checkpoint:
        _check(
            results,
            scope=scope,
            check="deploy_status_vs_checkpoint",
            ok=False,
            severity="warn",
            detail=f"deploy_status={status} but no upload:product checkpoint",
        )
    if has_checkpoint and status == "pending":
        _check(
            results,
            scope=scope,
            check="deploy_status_vs_checkpoint",
            ok=False,
            severity="warn",
            detail="upload checkpoint OK but deploy_status still pending",
        )


def validate_workspace(
    pkg_root: Path,
    space_ref: Path,
    *,
    pipeline_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Local validation: schema, template ref, required asset files."""
    results: list[dict[str, Any]] = []
    workspace_path = space_ref / "workspace.json"
    if not workspace_path.is_file():
        return {"ok": False, "checks": [{"status": "fail", "detail": f"missing {workspace_path}"}]}

    workspace = WorkspaceManifest.model_validate_json(workspace_path.read_text(encoding="utf-8"))
    template_id = workspace.template.template_id if workspace.template else ""
    known = list_templates(pkg_root)
    _check(
        results,
        scope=space_ref.name,
        check="template_exists",
        ok=template_id in known,
        detail=template_id,
    )
    _check(
        results,
        scope=space_ref.name,
        check="workspace_schema_version",
        ok=workspace.meta.schema_version == "workspace/1",
        detail=workspace.meta.schema_version,
    )

    ids = pipeline_ids or workspace.pipeline_ids
    slots = required_asset_slots(pkg_root, template_id) if template_id in known else []
    bases = load_ecommerce_prompt_bases(pkg_root) if template_id == "ecommerce_raw" else {}

    sha_by_pipeline: dict[str, str] = {}
    sha_counts: dict[str, list[str]] = {}

    for pid in ids:
        inst_path = space_ref / "pipelines" / pid / "instance.json"
        _check(results, scope=pid, check="instance.json", ok=inst_path.is_file())
        if not inst_path.is_file():
            continue
        instance = PipelineInstance.model_validate_json(inst_path.read_text(encoding="utf-8"))
        _check(
            results,
            scope=pid,
            check="instance_schema_version",
            ok=instance.schema_version == "instance/1",
            detail=instance.schema_version,
        )
        inst_dir = inst_path.parent
        for slot in slots:
            if not slot.required:
                continue
            rel = getattr(instance.assets, slot.slot, "")
            if not rel:
                _check(results, scope=pid, check=f"asset:{slot.slot}", ok=False, detail="missing path")
                continue
            path = inst_dir / rel
            ext = path.suffix.lower().lstrip(".")
            _check(
                results,
                scope=pid,
                check=f"asset:{slot.slot}",
                ok=path.is_file(),
                detail=str(path),
            )
            if path.is_file() and slot.formats and ext not in slot.formats:
                _check(
                    results,
                    scope=pid,
                    check=f"asset_format:{slot.slot}",
                    ok=False,
                    detail=f"format .{ext} not in {slot.formats}",
                )
            if path.is_file() and slot.slot == "product":
                digest = _sha256(path)
                sha_by_pipeline[pid] = digest
                sha_counts.setdefault(digest, []).append(pid)

        if bases:
            _lint_instance_prompts(results, scope=pid, instance=instance, bases=bases)
        _check_deploy_status(results, scope=pid, instance=instance, project_dir=space_ref)

    for digest, pids in sha_counts.items():
        if len(pids) > 1:
            _check(
                results,
                scope=space_ref.name,
                check="sha256_duplicate_product",
                ok=False,
                severity="warn",
                detail=f"pipelines {', '.join(pids)} share product sha256 {digest[:16]}",
            )

    ok = all(r["status"] != "fail" for r in results)
    return {
        "space_ref": space_ref.name,
        "template_id": template_id,
        "ok": ok,
        "checks": results,
    }


def checkpoint_has_upload(space_ref: Path, product_id: str, step_id: str = "upload:product") -> bool:
    cp_path = space_ref / ".sync" / "state.json"
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


def asset_binding_sha256(instance: PipelineInstance, slot: str) -> str | None:
    bindings = getattr(instance.magnific, "asset_bindings", None) or {}
    row = bindings.get(slot) if isinstance(bindings, dict) else None
    if isinstance(row, dict):
        return row.get("sha256")
    return None


def record_asset_binding(
    instance: PipelineInstance,
    slot: str,
    *,
    sha256: str,
    creation_id: str,
) -> None:
    from datetime import UTC, datetime

    instance.magnific.asset_bindings[slot] = {
        "sha256": sha256,
        "creation_id": creation_id,
        "uploaded_at": datetime.now(UTC).isoformat(),
    }
    instance.deploy_status = "uploaded"
