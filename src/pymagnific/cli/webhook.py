"""Webhook CLI commands."""

from __future__ import annotations

import typer

webhook_app = typer.Typer(help="Webhook receiver")


@webhook_app.command("serve")
def webhook_serve(
    host: str = "127.0.0.1",
    port: int = 8787,
) -> None:
    """Local webhook server (FastAPI + uvicorn)."""
    import uvicorn

    typer.echo(f"Webhook: http://{host}:{port}/webhook")
    uvicorn.run("pymagnific.api.webhook:app", host=host, port=port, log_level="info")
