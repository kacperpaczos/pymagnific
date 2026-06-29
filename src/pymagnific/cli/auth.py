"""Auth CLI commands."""

from __future__ import annotations

import typer

from pymagnific.cli.utils import print_json, run_async
from pymagnific.dependencies import get_auth_service

auth_app = typer.Typer(help="MCP OAuth")


@auth_app.command("login")
def auth_login(
    no_browser: bool = typer.Option(False, "--no-browser", help="Print URL only"),
) -> None:
    """OAuth login for Magnific MCP (device authorization flow)."""
    service = get_auth_service()
    tokens = run_async(service.login(open_browser=not no_browser))
    typer.echo(f"Logged in. Token saved to {service.token_path}")
    status = run_async(service.status())
    if status.get("client_id"):
        typer.echo(f"Client ID: {status['client_id']}")
    if tokens.expires_in:
        typer.echo(f"Access token expires in {tokens.expires_in}s")


@auth_app.command("status")
def auth_status_cmd() -> None:
    """OAuth token status."""
    print_json(run_async(get_auth_service().status()))
