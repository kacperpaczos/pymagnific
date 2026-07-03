"""Workspace CLI - sync (deploy) vs exec (run) are separate."""

from __future__ import annotations

from pathlib import Path

import typer

from pymagnific.cli.utils import print_json, run_async
from pymagnific.core.config import get_settings
from pymagnific.dependencies import get_project_service
from pymagnific.services.project_paths import product_ids_from_pipeline_ids
from pymagnific.templates.registry import list_templates
from pymagnific.templates.validate import validate_template

project_app = typer.Typer(help="Workspace: sync (deploy) and exec (run) are separate")

sync_app = typer.Typer(help="Synchronizacja workspace ze Space: init, provision, upload, deploy.")
exec_app = typer.Typer(
    help="Uruchamianie pipeline (spaces_run). Osobna operacja - nigdy przy sync."
)
templates_app = typer.Typer(help="Kanoniczne szablony pipeline (graf + prompty).")

project_app.add_typer(sync_app, name="sync")
project_app.add_typer(exec_app, name="exec")
project_app.add_typer(templates_app, name="templates")


@sync_app.command("init")
def sync_init_cmd(
    space_ref: str = typer.Argument(..., help="Workspace / parent space name"),
    spec: Path = typer.Option(
        None,
        "--spec",
        help="Path to pipeline-spec.json",
    ),
) -> None:
    """Build workspace from pipeline-spec.json (workspace.json + instance.json)."""
    settings = get_settings()
    spec_path = spec or (settings.projects_dir / space_ref / "pipeline-spec-draft.json")
    result = get_project_service().init_workspace(space_ref, spec_path=spec_path)
    print_json({"status": "initialized", "spec": str(spec_path), **result})


@project_app.command("validate")
def project_validate_cmd(
    space_ref: str = typer.Argument(..., help="Workspace name"),
    pipeline: list[str] = typer.Option(None, "--pipeline", help="Pipeline id(s)"),
) -> None:
    """Validate local workspace files and required assets."""
    result = get_project_service().validate_workspace_local(
        space_ref, pipeline_ids=pipeline or None
    )
    print_json(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@project_app.command("audit")
def project_audit_cmd(
    space_ref: str = typer.Argument(..., help="Workspace name"),
    pipeline: list[str] = typer.Option(None, "--pipeline", help="Pipeline id(s)"),
    strict: bool = typer.Option(False, "--strict", help="Exit 1 on any failed check"),
) -> None:
    """Audit local instance.json vs pulled .remote/board.json (requires bind/pull)."""
    result = get_project_service().audit_workspace_remote(
        space_ref, pipeline_ids=pipeline or None
    )
    print_json(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@templates_app.command("validate")
def templates_validate_cmd(
    template_id: str = typer.Argument(..., help="Template id, e.g. ecommerce_raw"),
) -> None:
    """Validate a canonical template under projects/templates/."""
    settings = get_settings()
    result = validate_template(settings.pkg_root, template_id)
    print_json(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@templates_app.command("list")
def templates_list_cmd() -> None:
    """List available templates."""
    settings = get_settings()
    print_json({"templates": list_templates(settings.pkg_root)})


@sync_app.command("upload")
def sync_upload_cmd(
    space_ref: str = typer.Argument(..., help="Parent space / project name"),
    apply: bool = typer.Option(False, "--apply", help="Upload images (default: dry-run)"),
    pipeline: list[str] = typer.Option(
        None,
        "--pipeline",
        help="Pipeline id(s) to upload (repeatable)",
    ),
) -> None:
    """Upload product images to pipeline Spaces. No run."""
    result = run_async(
        get_project_service().upload_pipelines(
            space_ref,
            pipeline_ids=pipeline or None,
            apply=apply,
        )
    )
    print_json(result)


@sync_app.command("prepare")
def sync_prepare_cmd(
    space_ref: str = typer.Argument(..., help="Parent space / project name"),
    apply: bool = typer.Option(False, "--apply", help="Apply list bindings"),
    pipeline: list[str] = typer.Option(None, "--pipeline", help="Pipeline id(s)"),
) -> None:
    """Set Colors/Shot ideas lists on pipeline Spaces. No run."""
    result = run_async(
        get_project_service().prepare_pipelines(
            space_ref,
            pipeline_ids=pipeline or None,
            apply=apply,
        )
    )
    print_json(result)


@sync_app.command("deploy")
def sync_deploy_cmd(
    space_ref: str = typer.Argument(..., help="Parent space / project name"),
    apply: bool = typer.Option(False, "--apply", help="Upload + prepare (default: dry-run)"),
    pipeline: list[str] = typer.Option(None, "--pipeline", help="Pipeline id(s)"),
    resume: bool = typer.Option(False, "--resume", help="Wznów od checkpointu"),
    fresh: bool = typer.Option(False, "--fresh", help="Usuń checkpoint przed startem"),
    quiet: bool = typer.Option(False, "--quiet", help="Bez live progress na stderr"),
) -> None:
    """Deploy local pipeline project to Magnific. Upload + prepare, no run."""
    result = run_async(
        get_project_service().deploy_pipelines(
            space_ref,
            pipeline_ids=pipeline or None,
            apply=apply,
            resume=resume,
            fresh=fresh,
            quiet=quiet,
        )
    )
    print_json(result)


@sync_app.command("provision")
def sync_provision_cmd(
    space_ref: str = typer.Argument(..., help="Workspace name"),
    apply: bool = typer.Option(False, "--apply", help="Add pipeline panels to shared Space"),
    pipeline: list[str] = typer.Option(
        None,
        "--pipeline",
        help="Product id(s), e.g. 77 or pipeline-77 (repeatable)",
    ),
    resume: bool = typer.Option(False, "--resume", help="Wznów od checkpointu"),
    fresh: bool = typer.Option(False, "--fresh", help="Usuń checkpoint przed startem"),
    quiet: bool = typer.Option(False, "--quiet", help="Bez live progress na stderr"),
) -> None:
    """Provision multiplied pipeline chains in one Magnific Space. No upload, no run."""
    result = run_async(
        get_project_service().provision_instances(
            space_ref,
            product_ids=product_ids_from_pipeline_ids(pipeline or None),
            apply=apply,
            resume=resume,
            fresh=fresh,
            quiet=quiet,
        )
    )
    print_json(result)
    readiness = result.get("asset_readiness") or {}
    if readiness.get("warning"):
        typer.echo(f"WARNING: {readiness['warning']}", err=True)


@sync_app.command("status")
def sync_status_cmd(
    space_ref: str = typer.Argument(..., help="Workspace name"),
) -> None:
    """Pokaż postęp ostatniego sync (checkpoint .sync/state.json)."""
    print_json(get_project_service().sync_status(space_ref))


@sync_app.command("full")
def sync_full_cmd(
    space_ref: str = typer.Argument(..., help="Workspace name"),
    apply: bool = typer.Option(False, "--apply", help="provision → bind → deploy"),
    pipeline: list[str] = typer.Option(
        None,
        "--pipeline",
        help="Product id(s), e.g. 77 (repeatable)",
    ),
    resume: bool = typer.Option(False, "--resume", help="Wznów od checkpointu"),
    fresh: bool = typer.Option(False, "--fresh", help="Usuń checkpoint przed startem"),
    quiet: bool = typer.Option(False, "--quiet", help="Bez live progress na stderr"),
) -> None:
    """Pełny sync: provision, bind, upload, repair, prepare w jednym przebiegu."""
    result = run_async(
        get_project_service().sync_full(
            space_ref,
            product_ids=product_ids_from_pipeline_ids(pipeline or None),
            apply=apply,
            resume=resume,
            fresh=fresh,
            quiet=quiet,
        )
    )
    print_json(result)


@sync_app.command("bind-nodes")
def sync_bind_nodes_cmd(
    space_ref: str = typer.Argument(..., help="Workspace name"),
    pipeline: list[str] = typer.Option(None, "--pipeline", help="Product id(s)"),
    resume: bool = typer.Option(False, "--resume", help="Wznów od checkpointu"),
    fresh: bool = typer.Option(False, "--fresh", help="Usuń checkpoint przed startem"),
    quiet: bool = typer.Option(False, "--quiet", help="Bez live progress na stderr"),
) -> None:
    """Pull board and refresh magnific.nodes in instance.json."""
    svc = get_project_service()
    result = run_async(
        svc.bind_instances_from_remote(
            space_ref,
            product_ids=product_ids_from_pipeline_ids(pipeline or None),
            resume=resume,
            fresh=fresh,
            quiet=quiet,
        )
    )
    print_json(result)


@exec_app.command("run")
def exec_run_cmd(
    space_ref: str = typer.Argument(..., help="Parent or pipeline space name"),
    job: str = typer.Option(..., "--job", help="Job id from instance.json"),
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        help="Product id, e.g. 77 - disambiguates job lookup",
    ),
    skip_gates: bool = typer.Option(False, "--skip-gates", help="Skip upload checkpoint gate"),
) -> None:
    """Run one job on Magnific (spaces_run). Requires deploy upload first."""
    result = run_async(
        get_project_service().run_job(
            space_ref, job, product_id=pipeline, skip_gates=skip_gates
        )
    )
    print_json(result)


@exec_app.command("batch")
def exec_batch_cmd(
    space_ref: str = typer.Argument(..., help="Parent space / project name"),
    phase: str | None = typer.Option(None, "--phase", help="Filter jobs by phase (pilot, batch)"),
    job: list[str] = typer.Option(None, "--job", help="Job id(s) to run (repeatable)"),
    parallel: int = typer.Option(1, "--parallel", help="Max concurrent pipeline runs"),
    pipeline: list[str] = typer.Option(
        None,
        "--pipeline",
        help="Product id(s) for workspace (repeatable)",
    ),
    skip_gates: bool = typer.Option(False, "--skip-gates", help="Skip upload checkpoint gate"),
) -> None:
    """Run multiple jobs. Requires deploy upload first unless --skip-gates."""
    svc = get_project_service()
    result = run_async(
        svc.run_batch(
            space_ref,
            phase=phase,
            job_ids=job or None,
            parallel=parallel,
            product_ids=product_ids_from_pipeline_ids(pipeline or None),
            skip_gates=skip_gates,
        )
    )
    print_json(result)
