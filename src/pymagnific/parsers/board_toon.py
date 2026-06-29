"""Parse Space board state (TOON) - pure functions, no I/O."""

from __future__ import annotations

import re
from typing import Any

from pymagnific.schemas.board import SpaceCreation

_CREATION_ID_KEY = "creationIdentifier"
_TABLE_HEADER_RE = re.compile(r"^(\w+)\[(\d+)\]\{([^}]+)\}:\s*$")
_TABLE_EMPTY_RE = re.compile(r"^(\w+)\[(\d+)\]:\s*$")


def split_csv_line(line: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    parts.append("".join(current).strip())
    return parts


def coerce_value(raw: str) -> Any:
    if raw in ("null", "None", ""):
        return None
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _parse_scalar_block(lines: list[str], start: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _TABLE_HEADER_RE.match(line) or _TABLE_EMPTY_RE.match(line):
            break
        if re.match(r"^\w+:\s*$", line.rstrip()):
            break
        if line.startswith("  ") and ":" in line:
            key, _, value = line.strip().partition(":")
            result[key.strip()] = coerce_value(value.strip())
            i += 1
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = coerce_value(value.strip())
            i += 1
            continue
        break
    return result, i


def parse_board_json(state: str) -> dict[str, Any]:
    """Parse MCP spaces_state TOON text into structured JSON."""
    lines = state.splitlines()
    board: dict[str, Any] = {
        "board": {},
        "page": {},
        "pageIndex": [],
        "nodes": [],
        "nodeData": [],
        "connections": [],
        "rawSections": {},
    }
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue

        if line == "board:":
            board["board"], i = _parse_scalar_block(lines, i + 1)
            continue
        if line == "page:":
            board["page"], i = _parse_scalar_block(lines, i + 1)
            continue

        header = _TABLE_HEADER_RE.match(line)
        if header:
            section, _count, fields_csv = header.groups()
            fields = [f.strip() for f in fields_csv.split(",")]
            rows: list[dict[str, Any]] = []
            i += 1
            while i < len(lines):
                row_line = lines[i]
                if not row_line.startswith("  "):
                    break
                if _TABLE_HEADER_RE.match(row_line) or _TABLE_EMPTY_RE.match(row_line):
                    break
                if row_line.strip().endswith(":") and ":" in row_line.strip()[:-1]:
                    break
                values = split_csv_line(row_line.strip())
                row = {
                    fields[idx]: coerce_value(values[idx])
                    for idx in range(min(len(fields), len(values)))
                }
                rows.append(row)
                i += 1
            board[section] = rows
            continue

        empty_table = _TABLE_EMPTY_RE.match(line)
        if empty_table:
            section = empty_table.group(1)
            board[section] = []
            i += 1
            continue

        if line.endswith(":") and not line.startswith(" "):
            section = line[:-1]
            if section not in board:
                block, i = _parse_scalar_block(lines, i + 1)
                board["rawSections"][section] = block
            else:
                i += 1
            continue

        i += 1

    return board


def node_data_map(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in board.get("nodeData", []):
        eid = row.get("elementId")
        if not eid:
            continue
        result.setdefault(str(eid), {})[str(row.get("key"))] = row.get("value")
    return result


def creations_from_board(board: dict[str, Any]) -> list[SpaceCreation]:
    data = node_data_map(board)
    result: list[SpaceCreation] = []
    for node in board.get("nodes", []):
        if node.get("type") != "creation":
            continue
        node_id = str(node["id"])
        cid = data.get(node_id, {}).get(_CREATION_ID_KEY)
        if cid:
            result.append(
                SpaceCreation(
                    node_id=node_id,
                    name=str(node.get("name") or "Creation"),
                    creation_identifier=str(cid),
                )
            )
    return result


def parse_creations(state: str) -> list[SpaceCreation]:
    return creations_from_board(parse_board_json(state))


def summarize_board(board: dict[str, Any]) -> dict[str, Any]:
    creations = creations_from_board(board)
    panels = [
        {"id": n["id"], "name": n.get("name")}
        for n in board.get("nodes", [])
        if n.get("type") == "panel"
    ]
    return {
        "spaceId": board.get("spaceId") or board.get("board", {}).get("uuid"),
        "elementsCount": board.get("board", {}).get("elementsCount"),
        "connectionsCount": board.get("board", {}).get("connectionsCount"),
        "panels": panels,
        "creations": [
            {
                "nodeId": c.node_id,
                "name": c.name,
                "creationIdentifier": c.creation_identifier,
            }
            for c in creations
        ],
        "creationCount": len(creations),
        "nodeCount": len(board.get("nodes", [])),
        "connectionCount": len(board.get("connections", [])),
    }


def summarize_space(state: str) -> dict[str, Any]:
    return summarize_board(parse_board_json(state))


def subset_board(
    board: dict[str, Any],
    *,
    panel: list[str] | None = None,
    node_type: list[str] | None = None,
    node_id: list[str] | None = None,
    include_connections: bool = True,
) -> dict[str, Any]:
    nodes = board.get("nodes", [])
    selected_ids: set[str] = set(node_id or [])

    if panel:
        panel_names = {p.lower() for p in panel}
        panel_ids = {
            str(n["id"])
            for n in nodes
            if n.get("type") == "panel" and str(n.get("name", "")).lower() in panel_names
        }
        selected_ids.update(str(n["id"]) for n in nodes if str(n.get("groupId") or "") in panel_ids)
        selected_ids.update(panel_ids)

    if node_type:
        types = {t.lower() for t in node_type}
        selected_ids.update(str(n["id"]) for n in nodes if str(n.get("type", "")).lower() in types)

    if not selected_ids and not panel and not node_type and not node_id:
        return board

    filtered_nodes = [n for n in nodes if str(n.get("id")) in selected_ids]
    filtered_node_ids = {str(n["id"]) for n in filtered_nodes}

    filtered_data = [
        row for row in board.get("nodeData", []) if str(row.get("elementId")) in filtered_node_ids
    ]

    filtered_connections: list[dict[str, Any]] = []
    if include_connections:
        for conn in board.get("connections", []):
            src = str(conn.get("sourceElementId") or "")
            tgt = str(conn.get("targetElementId") or "")
            if src in filtered_node_ids and tgt in filtered_node_ids:
                filtered_connections.append(conn)

    return {
        **{k: v for k, v in board.items() if k not in ("nodes", "nodeData", "connections")},
        "nodes": filtered_nodes,
        "nodeData": filtered_data,
        "connections": filtered_connections,
        "subset": {
            "panel": panel,
            "nodeType": node_type,
            "nodeId": node_id,
            "nodeCount": len(filtered_nodes),
            "connectionCount": len(filtered_connections),
        },
    }
