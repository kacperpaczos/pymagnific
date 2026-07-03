"""Validate templates and workspace instances."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pymagnific.schemas.workspace import PipelineInstance, WorkspaceManifest
from pymagnific.templates.registry import (
    list_templates,
    load_template_meta,
    required_asset_slots,
    template_dir,
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
) -> None:
    results.append({"scope": scope, "check": check, "status": "ok" if ok else "fail", "detail": detail})


def validate_template(pkg_root: Path, template_id: str) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    try:
        tdir = template_dir(pkg_root, template_id)
    except FileNotFoundError as exc:
        return {"template_id": template_id, "ok": False, "checks": [{"status": "fail", "detail": str(exc)}]}

    for name in ("template.json", "board.json", "project.json"):
        _check(results, scope=template_id, check=f"file:{name}", ok=(tdir / name).is_file())

    meta = load_template_meta(pkg_root, template_id)
    _check(
        results,
        scope=template_id,
        check="schema_version",
        ok=bool(meta.get("schema_version")),
        detail=str(meta.get("schema_version", "")),
    )

    project = json.loads((tdir / "project.json").read_text(encoding="utf-8"))
    logical_keys = {n.get("logical_key") for n in project.get("nodes", []) if n.get("logical_key")}
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
        ok=prompts_py.is_file() or prompts_json.is_file() or template_id == "ecommerce_raw",
        detail="prompts.py|prompts.json|pipeline_prompts",
    )

    ok = all(r["status"] == "ok" for r in results)
    return {"template_id": template_id, "ok": ok, "checks": results}


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

    ids = pipeline_ids or workspace.pipeline_ids
    slots = required_asset_slots(pkg_root, template_id) if template_id in known else []

    for pid in ids:
        inst_path = space_ref / "pipelines" / pid / "instance.json"
        _check(results, scope=pid, check="instance.json", ok=inst_path.is_file())
        if not inst_path.is_file():
            continue
        instance = PipelineInstance.model_validate_json(inst_path.read_text(encoding="utf-8"))
        inst_dir = inst_path.parent
        for slot in slots:
            if not slot.required:
                continue
            rel = getattr(instance.assets, slot.slot, "")
            if not rel:
                _check(results, scope=pid, check=f"asset:{slot.slot}", ok=False, detail="missing path")
                continue
            path = inst_dir / rel
            _check(
                results,
                scope=pid,
                check=f"asset:{slot.slot}",
                ok=path.is_file(),
                detail=str(path),
            )

    ok = all(r["status"] == "ok" for r in results)
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
