"""Spaces service - create, edit, poll, run."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pymagnific.clients.magnific_mcp import MagnificMcpClient
from pymagnific.core.config import Settings, get_settings
from pymagnific.core.logging import get_logger

log = get_logger("spaces")


def _is_terminal_edit_status(status: Any) -> bool:
    if isinstance(status, dict):
        if status.get("allTerminal") is True:
            return True
        if status.get("status") in ("completed", "failed", "terminal"):
            return True
    if isinstance(status, str) and status.lower() in ("completed", "failed", "terminal"):
        return True
    return False


def _is_terminal_run_status(status: Any) -> bool:
    if isinstance(status, dict):
        s = str(status.get("status", "")).lower()
        if s in (
            "finished",
            "failed",
            "completed",
            "completed_with_errors",
            "error",
            "terminal",
        ):
            return True
        if status.get("terminal") is True:
            return True
        if status.get("allTerminal") is True:
            return True
    return False


def _operation_id(edit_response: Any) -> str | None:
    if isinstance(edit_response, dict):
        return (
            edit_response.get("operationId")
            or edit_response.get("operation_id")
            or edit_response.get("threadId")
            or edit_response.get("thread_id")
        )
    return None


def _workflow_run_id(run_response: Any) -> str | None:
    if isinstance(run_response, dict):
        return run_response.get("workflowRunIdentifier") or run_response.get(
            "workflow_run_identifier"
        )
    return None


class SpacesService:
    def __init__(
        self,
        mcp: MagnificMcpClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._mcp = mcp or MagnificMcpClient(settings=self._settings)

    @property
    def mcp(self) -> MagnificMcpClient:
        return self._mcp

    async def list_spaces(self, **kwargs: Any) -> Any:
        return await self._mcp.spaces_list(**kwargs)

    async def create_space(self, name: str, description: str | None = None) -> Any:
        return await self._mcp.spaces_create(name, description)

    async def edit_space(self, space_id: str, query: str, **kwargs: Any) -> Any:
        return await self._mcp.spaces_edit(space_id, query, **kwargs)

    async def get_state(self, space_id: str, **kwargs: Any) -> Any:
        return await self._mcp.spaces_state(space_id, **kwargs)

    async def account_balance(self) -> Any:
        return await self._mcp.account_balance()

    async def wait_for_edit(
        self,
        operation_id: str,
        *,
        timeout: float = 300.0,
        poll_seconds: int = 25,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last: Any = None
        poll_n = 0
        log.info("waiting for spaces_edit %s (timeout %.0fs)", operation_id[:16], timeout)
        while time.monotonic() < deadline:
            poll_n += 1
            last = await self._mcp.spaces_edit_status(
                operationId=operation_id,
                timeoutSeconds=min(poll_seconds, 25),
            )
            status = last.get("status") if isinstance(last, dict) else str(last)
            log.info(
                "spaces_edit %s poll %d status=%s",
                operation_id[:16],
                poll_n,
                status,
            )
            if _is_terminal_edit_status(last):
                log.info("spaces_edit %s finished after %d polls", operation_id[:16], poll_n)
                return last
            hint = 5
            if isinstance(last, dict):
                hint = int(last.get("poll_after_seconds", hint))
            await asyncio.sleep(hint)
        log.error("spaces_edit %s timeout after %d polls", operation_id[:16], poll_n)
        raise TimeoutError(f"spaces_edit_status timeout after {timeout}s (last: {last})")

    async def wait_for_run(
        self,
        workflow_run_id: str,
        *,
        timeout: float = 600.0,
        poll_seconds: int = 25,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last: Any = None
        poll_n = 0
        log.info("waiting for spaces_run %s (timeout %.0fs)", workflow_run_id[:16], timeout)
        while time.monotonic() < deadline:
            poll_n += 1
            last = await self._mcp.spaces_run_status(
                workflow_run_id,
                timeout_seconds=min(poll_seconds, 25),
            )
            status = last.get("status") if isinstance(last, dict) else str(last)
            log.info(
                "spaces_run %s poll %d status=%s",
                workflow_run_id[:16],
                poll_n,
                status,
            )
            if _is_terminal_run_status(last):
                log.info("spaces_run %s finished after %d polls", workflow_run_id[:16], poll_n)
                return last
            hint = 5
            if isinstance(last, dict):
                hint = int(last.get("poll_after_seconds", hint))
            await asyncio.sleep(hint)
        log.error("spaces_run %s timeout after %d polls", workflow_run_id[:16], poll_n)
        raise TimeoutError(f"spaces_run_status timeout after {timeout}s (last: {last})")

    async def create_and_edit(
        self,
        name: str,
        edit_query: str,
        *,
        description: str | None = None,
        edit_timeout: float = 300.0,
    ) -> dict[str, Any]:
        created = await self._mcp.spaces_create(name, description)
        space_id = None
        if isinstance(created, dict):
            space_id = created.get("spaceId") or created.get("id") or created.get("space_id")
        if not space_id:
            raise RuntimeError(f"spaces_create - no spaceId in response: {created}")

        edit_resp = await self._mcp.spaces_edit(space_id, edit_query)
        op_id = _operation_id(edit_resp)
        edit_status = None
        if op_id:
            edit_status = await self.wait_for_edit(op_id, timeout=edit_timeout)

        state = await self._mcp.spaces_state(space_id)
        return {
            "space_id": space_id,
            "created": created,
            "edit_response": edit_resp,
            "edit_status": edit_status,
            "state": state,
        }

    async def run_space(
        self,
        space_id: str,
        start_node_id: str,
        *,
        mode: str = "connected",
        simulate: bool = True,
        run_timeout: float = 600.0,
    ) -> dict[str, Any]:
        cost = None
        if simulate:
            try:
                log.info(
                    "simulate_spaces space=%s start_node=%s mode=%s",
                    space_id[:12],
                    start_node_id[:12],
                    mode,
                )
                cost = await self._mcp.simulate_spaces(space_id, start_node_id, mode=mode)
            except Exception as exc:  # noqa: BLE001
                log.warning("simulate_spaces failed: %s", exc)
                cost = {"simulate": "skipped", "reason": "simulate_spaces failed"}

        log.info(
            "spaces_run space=%s start_node=%s mode=%s",
            space_id[:12],
            start_node_id[:12],
            mode,
        )
        run_resp = await self._mcp.spaces_run(space_id, start_node_id, mode=mode)
        run_id = _workflow_run_id(run_resp)
        run_status = None
        if run_id:
            run_status = await self.wait_for_run(run_id, timeout=run_timeout)
        else:
            log.warning("spaces_run returned no workflowRunIdentifier: %r", run_resp)

        return {
            "space_id": space_id,
            "start_node_id": start_node_id,
            "simulate": cost,
            "run_response": run_resp,
            "run_status": run_status,
        }
