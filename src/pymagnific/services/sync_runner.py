"""Execute sync steps with checkpoint and progress."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, TypeVar

from pymagnific.schemas.sync_state import SyncPhase
from pymagnific.services.sync_checkpoint import SyncCheckpoint
from pymagnific.services.sync_progress import SyncContext, SyncProgressReporter

T = TypeVar("T")


async def run_sync_step(
    ctx: SyncContext | None,
    *,
    phase: SyncPhase,
    product_id: str | None,
    step_id: str,
    fn: Callable[[], Awaitable[T]],
) -> T | None:
    """Run one step; skip if resume says done. Returns None when skipped."""
    checkpoint: SyncCheckpoint | None = None
    state = ctx.run_state if ctx else None
    progress: SyncProgressReporter | None = ctx.progress if ctx else None

    if ctx and ctx.active:
        checkpoint = ctx.checkpoint  # type: ignore[assignment]
        if ctx.resume and checkpoint.is_done(state, phase, product_id, step_id):
            return None

    if state and checkpoint and progress:
        checkpoint.set_current(state, phase=phase, product_id=product_id, step_id=step_id)
        progress.on_step_start(
            state, phase=phase, product_id=product_id, step_id=step_id
        )

    started = time.monotonic()
    try:
        result = await fn()
    except Exception as exc:
        if state and checkpoint:
            checkpoint.mark_failed(
                state,
                phase=phase,
                product_id=product_id,
                step_id=step_id,
                error=str(exc),
            )
        if progress and state:
            progress.on_step_fail(
                state,
                phase=phase,
                product_id=product_id,
                step_id=step_id,
                error=str(exc),
            )
        raise

    elapsed = time.monotonic() - started
    if state and checkpoint:
        detail: dict[str, Any] = {}
        if isinstance(result, dict):
            detail = {k: result[k] for k in ("status", "creation_id") if k in result}
        checkpoint.mark_done(
            state,
            phase=phase,
            product_id=product_id,
            step_id=step_id,
            detail=detail,
        )
    if progress and state:
        progress.on_step_done(
            state,
            phase=phase,
            product_id=product_id,
            step_id=step_id,
            elapsed_s=elapsed,
        )
    return result
