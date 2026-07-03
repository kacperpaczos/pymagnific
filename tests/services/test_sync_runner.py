"""Tests for sync step runner resume skip."""

from __future__ import annotations

from pathlib import Path

import pytest

from pymagnific.services.sync_checkpoint import SyncCheckpoint
from pymagnific.services.sync_progress import NullSyncProgress, SyncContext
from pymagnific.services.sync_runner import run_sync_step


@pytest.mark.asyncio
async def test_run_sync_step_skips_completed_on_resume(tmp_path: Path) -> None:
    cp = SyncCheckpoint(tmp_path / "state.json")
    state = cp.start_run("test", total_steps=2)
    cp.mark_done(state, phase="deploy", product_id="77", step_id="upload:product")
    ctx = SyncContext(checkpoint=cp, run_state=state, progress=NullSyncProgress(), resume=True)

    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "done"

    result = await run_sync_step(
        ctx,
        phase="deploy",
        product_id="77",
        step_id="upload:product",
        fn=fn,
    )
    assert result is None
    assert calls == 0

    result2 = await run_sync_step(
        ctx,
        phase="deploy",
        product_id="77",
        step_id="upload:material",
        fn=fn,
    )
    assert result2 == "done"
    assert calls == 1
    assert cp.is_done(ctx.run_state, "deploy", "77", "upload:material")
