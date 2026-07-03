#!/usr/bin/env python3
"""Audit workspace instance.json vs pulled .remote/board.json (CLI wrapper)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from pymagnific.templates.audit import audit_workspace_remote  # noqa: E402


def main() -> None:
    project_dir = ROOT / "projects" / (sys.argv[1] if len(sys.argv) > 1 else "ecommerce_two_products")
    report = audit_workspace_remote(project_dir, pkg_root=ROOT)
    out_path = project_dir / "diff" / "audit-last.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), indent=2))
    if not report.get("ok"):
        fails = [r for r in report.get("results", []) if r.get("status") == "fail"]
        if fails:
            print("\nFailures:", file=sys.stderr)
            for f in fails:
                print(f"  #{f['product_id']} {f['check']}: {f['detail']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
