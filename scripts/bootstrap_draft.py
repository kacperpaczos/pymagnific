#!/usr/bin/env python3
"""Regenerate workspace.json + instance.json from pipeline-spec-draft.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from pymagnific.parsers.jobs_from_template import build_ecommerce_raw_jobs  # noqa: E402
from pymagnific.parsers.pipeline_prompts import apply_prompts_to_instance  # noqa: E402
from pymagnific.parsers.workspace_builder import (  # noqa: E402
    build_ecommerce_instance_from_spec,
    build_ecommerce_workspace_from_spec,
)


def main() -> None:
    project_dir = ROOT / "projects" / "ecommerce_two_products"
    spec_path = project_dir / "pipeline-spec-draft.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    workspace = build_ecommerce_workspace_from_spec(spec, space_id=None, pkg_root=ROOT)
    workspace.meta.space_id = None
    workspace.meta.description = spec["meta"].get("description")

    workspace_path = project_dir / "workspace.json"
    workspace_path.write_text(
        json.dumps(workspace.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    for product_id in workspace.pipeline_ids:
        instance = build_ecommerce_instance_from_spec(
            spec, product_id, workspace, pkg_root=ROOT
        )
        instance = apply_prompts_to_instance(instance, workspace)
        instance.jobs = build_ecommerce_raw_jobs(instance, include_material=False)
        instance.magnific.space_id = None
        instance.magnific.nodes = {}
        instance.magnific.provisioned_at = None
        instance.magnific.note = "Gotowy do review - bez uploadu do Magnific."
        instance.enabled = True

        instance_dir = project_dir / "pipelines" / product_id
        (instance_dir / "assets" / "backgrounds").mkdir(parents=True, exist_ok=True)
        instance_path = instance_dir / "instance.json"
        instance_path.write_text(
            json.dumps(instance.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        stages = []
        for job in instance.jobs:
            if job.phase == "pilot" and job.steps:
                stages = [s.get("stage") for s in job.steps]
                break
        print(
            f"Wrote {instance_path.relative_to(ROOT)} "
            f"({len(instance.jobs)} jobs, colors={len(instance.prompts.colors)}, stages={stages})"
        )

    print(f"Wrote {workspace_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
