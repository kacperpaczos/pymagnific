"""pymagnific CLI entry point."""

from __future__ import annotations

import sys

import typer

from pymagnific.cli.apps import apps_app
from pymagnific.cli.auth import auth_app
from pymagnific.cli.main import probe, rate_limits_cmd
from pymagnific.cli.spaces import spaces_app
from pymagnific.cli.webhook import webhook_app
from pymagnific.core.exceptions import (
    AssetsError,
    AuthError,
    ConfigError,
    MagnificMcpError,
    MagnificRateLimitExceeded,
    MagnificRestError,
    PymagnificError,
)

app = typer.Typer(help="Magnific Spaces - REST (API key) + MCP (OAuth)")

app.add_typer(auth_app, name="auth")
app.add_typer(apps_app, name="apps")
app.add_typer(spaces_app, name="spaces")
app.add_typer(webhook_app, name="webhook")

app.command()(probe)
app.command("rate-limits")(rate_limits_cmd)


def main() -> None:
    try:
        app()
    except MagnificRestError as e:
        typer.echo(f"REST error {e.status}: {e.body}", err=True)
        sys.exit(1)
    except MagnificRateLimitExceeded as e:
        typer.echo(str(e), err=True)
        sys.exit(1)
    except (PymagnificError, ConfigError, AuthError, AssetsError, MagnificMcpError) as e:
        typer.echo(str(e), err=True)
        sys.exit(1)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
