"""Probe and rate-limit commands."""

from __future__ import annotations

import typer

from pymagnific.cli.utils import print_json, run_async
from pymagnific.dependencies import get_apps_service, get_spaces_service


def probe() -> None:
    """Test REST API key + MCP balance (if logged in)."""
    apps = get_apps_service()
    result = run_async(apps.probe())
    print_json({"rest": result})

    try:
        balance = run_async(get_spaces_service().account_balance())
        print_json({"mcp_balance": balance})
    except Exception as e:
        typer.echo(f"MCP (requires auth login): {e}", err=True)


def rate_limits_cmd() -> None:
    """Show REST API rate limit usage and active warnings."""
    print_json(get_apps_service().rate_limit_status())
