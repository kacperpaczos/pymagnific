"""Apps CLI commands."""

from __future__ import annotations

import typer

from pymagnific.cli.utils import print_json, run_async
from pymagnific.dependencies import get_apps_service

apps_app = typer.Typer(help="REST Apps/Flows")


@apps_app.command("list")
def apps_list(page: int = 1, per_page: int = 25) -> None:
    """List published Apps (REST)."""
    print_json(run_async(get_apps_service().list_apps(page=page, per_page=per_page)))


@apps_app.command("get")
def apps_get(app_id: str) -> None:
    """App details and input spec."""
    print_json(run_async(get_apps_service().get_app(app_id)))


@apps_app.command("run")
def apps_run(
    app_id: str,
    input_pairs: list[str] = typer.Option([], "--input", "-i", help="inputId=value"),
    poll: bool = typer.Option(True, "--poll/--no-poll"),
    webhook: str | None = typer.Option(None, "--webhook", help="Callback URL (or .env)"),
) -> None:
    """Run App via REST API."""
    inputs: dict[str, str] = {}
    for pair in input_pairs:
        if "=" not in pair:
            typer.echo(f"Invalid format: {pair} (expected key=value)", err=True)
            raise typer.Exit(1)
        k, v = pair.split("=", 1)
        inputs[k] = v

    service = get_apps_service()
    started = run_async(service.run_app(app_id, inputs, webhook=webhook))
    print_json(started)

    run_id = started.get("workflow_run_identifier") or started.get("workflowRunIdentifier")
    if poll and run_id:
        typer.echo(f"Polling run {run_id}...")
        final = run_async(service.poll_run(run_id))
        print_json(final)
