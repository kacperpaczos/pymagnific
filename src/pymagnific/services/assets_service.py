"""Space assets service - pull, push, inspect, subset."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any

import httpx

from pymagnific.clients.magnific_mcp import MagnificMcpClient
from pymagnific.core.config import Settings, get_settings
from pymagnific.core.exceptions import AssetsError
from pymagnific.parsers.board_toon import (
    creations_from_board,
    parse_board_json,
    split_csv_line,
    subset_board,
    summarize_board,
    summarize_space,
)
from pymagnific.schemas.board import PulledAsset, SpaceCreation, SpaceExport


class AssetsService:
    def __init__(
        self,
        mcp: MagnificMcpClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._mcp = mcp or MagnificMcpClient(settings=self._settings)

    async def resolve_space_id(self, space_ref: str) -> str:
        ref = space_ref.strip()
        if re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            ref,
            re.I,
        ):
            return ref

        listing = await self._mcp.spaces_list(query=ref, per_page=50)
        if not isinstance(listing, str):
            raise AssetsError(f"Unexpected spaces_list response: {listing!r}")

        ref_lower = ref.lower()
        matches: list[tuple[str, str]] = []
        for line in listing.splitlines():
            if not line.startswith("  "):
                continue
            parts = split_csv_line(line.strip())
            if len(parts) >= 2:
                space_id, name = parts[0], parts[1]
                if ref_lower in name.lower():
                    matches.append((space_id, name))

        if not matches:
            raise AssetsError(f"No space matching name: {ref!r}")
        if len(matches) > 1:
            names = ", ".join(f"{n} ({i})" for i, n in matches)
            raise AssetsError(f"Multiple spaces match {ref!r}: {names}")
        return matches[0][0]

    async def get_space_state(self, space_id: str, *, scope: str | None = None) -> str:
        kwargs: dict[str, Any] = {}
        if scope:
            kwargs["scope"] = scope
        state = await self._mcp.spaces_state(space_id, **kwargs)
        if not isinstance(state, str):
            raise AssetsError(f"Expected text state, got: {type(state)}")
        return state

    def load_board_export(self, export_dir: Path) -> dict[str, Any]:
        export_dir = export_dir.expanduser().resolve()
        board_json = export_dir / "board.json"
        if not board_json.is_file():
            raise AssetsError(f"No board.json in {export_dir}. Run: pymagnific spaces pull ...")
        return json.loads(board_json.read_text(encoding="utf-8"))

    def inspect_export(self, export_dir: Path) -> dict[str, Any]:
        board = self.load_board_export(export_dir)
        summary = summarize_board(board)
        summary["exportDir"] = str(export_dir.resolve())
        return summary

    async def inspect_remote(self, space_ref: str) -> dict[str, Any]:
        space_id = await self.resolve_space_id(space_ref)
        state = await self.get_space_state(space_id)
        summary = summarize_space(state)
        summary["resolvedSpaceId"] = space_id
        return summary

    def subset_export(
        self,
        export_dir: Path,
        *,
        panel: list[str] | None = None,
        node_type: list[str] | None = None,
        node_id: list[str] | None = None,
    ) -> dict[str, Any]:
        board = self.load_board_export(export_dir)
        return subset_board(
            board,
            panel=panel,
            node_type=node_type,
            node_id=node_id,
        )

    async def pull_space(
        self,
        space_ref: str,
        *,
        out_dir: Path | None = None,
        scope: str | None = None,
        download_assets: bool = True,
        clean: bool = False,
    ) -> SpaceExport:
        space_id = await self.resolve_space_id(space_ref)
        base = out_dir or (self._settings.runs_dir / "spaces" / space_id)
        if clean and base.exists():
            shutil.rmtree(base)

        state = await self.get_space_state(space_id, scope=scope)
        board = parse_board_json(state)
        board["spaceId"] = space_id
        board["exportScope"] = scope or "current_page"

        base.mkdir(parents=True, exist_ok=True)

        board_toon = base / "board.toon"
        board_json = base / "board.json"
        board_toon.write_text(state, encoding="utf-8")
        board_json.write_text(
            json.dumps(board, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        pulled: list[PulledAsset] = []
        if download_assets:
            creations = creations_from_board(board)
            if creations:
                assets_dir = base / "assets"
                if assets_dir.exists():
                    shutil.rmtree(assets_dir)
                assets_dir.mkdir(parents=True, exist_ok=True)
                pulled = await self._download_creation_assets(creations, assets_dir)

        manifest_path = base / "manifest.json"
        counts = {
            "nodes": len(board.get("nodes", [])),
            "nodeData": len(board.get("nodeData", [])),
            "connections": len(board.get("connections", [])),
            "creations": len(creations_from_board(board)),
            "assets": len(pulled),
        }
        manifest = {
            "spaceId": space_id,
            "exportScope": scope or "current_page",
            "boardToon": str(board_toon),
            "boardJson": str(board_json),
            "counts": counts,
            "assets": [
                {
                    "nodeId": a.node_id,
                    "name": a.name,
                    "creationIdentifier": a.creation_identifier,
                    "localPath": str(a.local_path),
                    "url": a.url,
                }
                for a in pulled
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return SpaceExport(
            base_dir=base,
            board_toon=board_toon,
            board_json=board_json,
            manifest=manifest_path,
            assets=pulled,
            counts=counts,
        )

    async def push_image(
        self,
        space_ref: str,
        image_path: Path,
        *,
        page_id: str | None = None,
        space_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_id = space_id or await self.resolve_space_id(space_ref)
        creation_id = await self._upload_local_image(image_path)
        result = await self._mcp.spaces_add_creations(
            resolved_id,
            [creation_id],
            page_id=page_id,
        )
        if isinstance(result, dict):
            result = {**result, "creationIdentifier": creation_id}
        return {
            "creationIdentifier": creation_id,
            "addResult": result,
        }

    async def _download_creation_assets(
        self,
        creations: list[SpaceCreation],
        base: Path,
    ) -> list[PulledAsset]:
        pulled: list[PulledAsset] = []
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as http:
            for creation in creations:
                meta = await self._mcp.creations_get(creation.creation_identifier)
                meta_dict = self._yamlish_to_dict(meta) if isinstance(meta, str) else meta
                if not isinstance(meta_dict, dict):
                    raise AssetsError(f"creations_get failed for {creation.creation_identifier}")

                url = str(meta_dict.get("url") or meta_dict.get("previewUrl") or "")
                if not url:
                    raise AssetsError(
                        f"No download URL for {creation.name} ({creation.creation_identifier})"
                    )

                resp = await http.get(url)
                resp.raise_for_status()
                mime = resp.headers.get("content-type")
                ext = self._guess_extension(url, mime)
                filename = (
                    f"{self._safe_filename(creation.name)}_{creation.creation_identifier}{ext}"
                )
                local_path = base / filename
                local_path.write_bytes(resp.content)

                pulled.append(
                    PulledAsset(
                        node_id=creation.node_id,
                        name=creation.name,
                        creation_identifier=creation.creation_identifier,
                        local_path=local_path,
                        url=url,
                        metadata=meta_dict,
                    )
                )
        return pulled

    async def _upload_local_image(self, path: Path) -> str:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise AssetsError(f"File not found: {path}")

        mime = self._mime_for_path(path)
        data = path.read_bytes()

        up = await self._mcp.creations_request_upload(mime)
        if isinstance(up, str):
            up = json.loads(up)
        if not isinstance(up, dict) or "proxyUploadUrl" not in up:
            raise AssetsError(f"Upload request failed: {up!r}")

        async with httpx.AsyncClient(timeout=120) as http:
            resp = await http.put(
                up["proxyUploadUrl"],
                content=data,
                headers={"Content-Type": mime},
            )
            resp.raise_for_status()

        fin = await self._mcp.creations_finalize_upload(up["path"])
        if isinstance(fin, str):
            fin = json.loads(fin) if fin.strip().startswith("{") else self._yamlish_to_dict(fin)
        if not isinstance(fin, dict):
            raise AssetsError(f"Finalize failed: {fin!r}")

        identifier = fin.get("identifier")
        if not identifier:
            raise AssetsError(f"No creation identifier in finalize response: {fin}")
        return str(identifier)

    @staticmethod
    def _yamlish_to_dict(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for line in text.splitlines():
            if ":" not in line or line.startswith(" "):
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"')
            if key:
                result[key] = value
        return result

    @staticmethod
    def _guess_extension(url: str, mime: str | None) -> str:
        if mime:
            ext = mimetypes.guess_extension(mime.split(";")[0].strip())
            if ext:
                return ext
        path = url.split("?", 1)[0]
        suffix = Path(path).suffix
        if suffix:
            return suffix
        return ".bin"

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = re.sub(r"[^\w\-.]+", "_", name.strip()) or "creation"
        return cleaned[:80]

    @staticmethod
    def _mime_for_path(path: Path) -> str:
        mime, _ = mimetypes.guess_type(path.name)
        if mime in {
            "image/jpeg",
            "image/png",
            "image/webp",
            "video/mp4",
            "video/quicktime",
            "video/webm",
        }:
            return mime
        suffix = path.suffix.lower()
        mapping = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        if suffix not in mapping:
            raise AssetsError(f"Unsupported file type: {path.suffix}")
        return mapping[suffix]
