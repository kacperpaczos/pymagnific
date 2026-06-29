"""Spaces CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from pymagnific.cli.utils import print_json, run_async
from pymagnific.dependencies import get_assets_service, get_spaces_service

spaces_app = typer.Typer(help="MCP Spaces")


@spaces_app.command("list")
def spaces_list_cmd(
    query: str | None = None,
    ownership: str = "all",
    page: int = 1,
    per_page: int = 25,
) -> None:
    """List Spaces (MCP)."""
    kwargs: dict[str, Any] = {"ownership": ownership, "page": page, "perPage": per_page}
    if query:
        kwargs["query"] = query
    print_json(run_async(get_spaces_service().list_spaces(**kwargs)))


@spaces_app.command("create")
def spaces_create_cmd(
    name: str,
    description: str | None = None,
    edit_query: str | None = typer.Option(None, "--edit", "-e", help="Graph edit prompt"),
) -> None:
    """Create Space (+ optional edit)."""
    service = get_spaces_service()
    if edit_query:
        result = run_async(service.create_and_edit(name, edit_query, description=description))
    else:
        result = run_async(service.create_space(name, description))
    print_json(result)


@spaces_app.command("edit")
def spaces_edit_cmd(
    space_id: str,
    query: str,
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """Edit Space graph (MCP)."""
    service = get_spaces_service()
    edit_resp = run_async(service.edit_space(space_id, query))
    print_json({"edit_response": edit_resp})
    if wait:
        op_id = None
        if isinstance(edit_resp, dict):
            op_id = edit_resp.get("operationId") or edit_resp.get("threadId")
        if op_id:
            status = run_async(service.wait_for_edit(op_id))
            print_json({"edit_status": status})
        state = run_async(service.get_state(space_id))
        print_json({"state": state})


@spaces_app.command("state")
def spaces_state_cmd(
    space_id: str,
    scope: str | None = typer.Option(None, "--scope", help="current_page | all"),
) -> None:
    """Read board state (MCP)."""
    kwargs: dict[str, Any] = {}
    if scope:
        kwargs["scope"] = scope
    print_json(run_async(get_spaces_service().get_state(space_id, **kwargs)))


@spaces_app.command("inspect")
def spaces_inspect_cmd(
    space_ref: str | None = typer.Argument(None, help="Space id or name (omit with --from)"),
    from_export: Path | None = typer.Option(
        None,
        "--from",
        "-f",
        help="Summarize from local board.json export",
    ),
) -> None:
    """Summarize nodes, panels and connections in a Space or local export."""
    assets = get_assets_service()
    if from_export:
        print_json(assets.inspect_export(from_export))
        return

    if not space_ref:
        raise typer.BadParameter("space_ref or --from is required")

    print_json(run_async(assets.inspect_remote(space_ref)))


@spaces_app.command("pull")
def spaces_pull_cmd(
    space_ref: str,
    out: Path | None = typer.Option(None, "--out", "-o", help="Output directory"),
    scope: str | None = typer.Option(None, "--scope", help="current_page | all"),
    no_assets: bool = typer.Option(
        False,
        "--no-assets",
        help="Save board only, skip image downloads",
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        "-c",
        help="Remove output directory before export",
    ),
) -> None:
    """Download full board state (board.toon + board.json) and creation assets."""
    export = run_async(
        get_assets_service().pull_space(
            space_ref,
            out_dir=out,
            scope=scope,
            download_assets=not no_assets,
            clean=clean,
        )
    )
    typer.echo(f"Exported space to {export.base_dir}")
    typer.echo(f"  board: {export.board_json}")
    typer.echo(
        f"  nodes: {export.counts['nodes']}, "
        f"connections: {export.counts['connections']}, "
        f"nodeData: {export.counts['nodeData']}"
    )
    if export.assets:
        typer.echo(f"  assets ({len(export.assets)}):")
        for asset in export.assets:
            typer.echo(f"    {asset.name}: {asset.local_path}")
    elif not no_assets:
        typer.echo("  assets: none (no creation nodes with identifiers)")


@spaces_app.command("subset")
def spaces_subset_cmd(
    export_dir: Path = typer.Argument(..., help="Directory with board.json from spaces pull"),
    panel: list[str] | None = typer.Option(
        None,
        "--panel",
        "-p",
        help="Panel name (repeatable)",
    ),
    node_type: list[str] | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Node type, e.g. creation, image-generator",
    ),
    node_id: list[str] | None = typer.Option(
        None,
        "--node-id",
        "-n",
        help="Node UUID (repeatable)",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Write subset JSON to file (default: stdout)",
    ),
) -> None:
    """Filter a local board.json export by panel, type or node id."""
    subset = get_assets_service().subset_export(
        export_dir,
        panel=panel,
        node_type=node_type,
        node_id=node_id,
    )
    text = json.dumps(subset, indent=2, ensure_ascii=False)
    if out:
        out.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote subset to {out}")
    else:
        typer.echo(text)


@spaces_app.command("push")
def spaces_push_cmd(
    space_ref: str,
    image_path: Path,
    page_id: str | None = typer.Option(None, "--page-id", help="Target page id"),
) -> None:
    """Upload a local image and add it to the Space board."""
    result = run_async(get_assets_service().push_image(space_ref, image_path, page_id=page_id))
    print_json(result)


@spaces_app.command("run")
def spaces_run_cmd(
    space_id: str,
    start_node: str = typer.Option(..., "--start-node", "-n"),
    mode: str = typer.Option("connected", "--mode", "-m"),
    simulate: bool = typer.Option(True, "--simulate/--no-simulate"),
) -> None:
    """Run Space workflow (MCP)."""
    result = run_async(
        get_spaces_service().run_space(
            space_id,
            start_node,
            mode=mode,
            simulate=simulate,
        )
    )
    print_json(result)
