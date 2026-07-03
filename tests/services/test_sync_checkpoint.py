"""Tests for sync checkpoint and resume."""

from __future__ import annotations

from pathlib import Path

import pytest

from pymagnific.schemas.sync_state import SyncRunState
from pymagnific.services.sync_checkpoint import SyncCheckpoint


@pytest.fixture
def checkpoint_path(tmp_path: Path) -> Path:
    return tmp_path / ".sync" / "state.json"


def test_checkpoint_save_load_roundtrip(checkpoint_path: Path) -> None:
    cp = SyncCheckpoint(checkpoint_path)
    state = cp.start_run("ecommerce-two-products", space_id="abc", total_steps=5)
    state = cp.mark_done(state, phase="deploy", product_id="77", step_id="upload:product")
    loaded = cp.load()
    assert loaded is not None
    assert loaded.space_ref == "ecommerce-two-products"
    assert loaded.run_id == state.run_id
    assert len(loaded.completed) == 1
    assert loaded.completed[0].step_id == "upload:product"


def test_resume_inherits_completed(checkpoint_path: Path) -> None:
    cp = SyncCheckpoint(checkpoint_path)
    state = cp.start_run("ecommerce-two-products", total_steps=3)
    cp.mark_done(state, phase="deploy", product_id="77", step_id="upload:product")
    cp.mark_failed(
        state,
        phase="deploy",
        product_id="77",
        step_id="prepare:colors_list",
        error="timeout",
    )
    resumed = cp.start_run("ecommerce-two-products", total_steps=3, resume=True)
    assert resumed.status == "in_progress"
    assert resumed.failed is None
    assert len(resumed.completed) == 1
    assert cp.is_done(resumed, "deploy", "77", "upload:product")
    assert not cp.is_done(resumed, "deploy", "77", "upload:material")


def test_clear_removes_checkpoint(checkpoint_path: Path) -> None:
    cp = SyncCheckpoint(checkpoint_path)
    cp.start_run("x", total_steps=1)
    assert cp.exists()
    cp.clear()
    assert not cp.exists()


def test_atomic_write_uses_temp_file(checkpoint_path: Path) -> None:
    cp = SyncCheckpoint(checkpoint_path)
    cp.start_run("x", total_steps=1)
    assert checkpoint_path.is_file()
    assert not checkpoint_path.with_suffix(".json.tmp").exists()


def test_is_step_done_keys(checkpoint_path: Path) -> None:
    state = SyncRunState(
        space_ref="r",
        run_id="1",
        started_at="t",
        updated_at="t",
        total_steps=2,
        completed=[],
    )
    cp = SyncCheckpoint(checkpoint_path)
    assert not cp.is_done(state, "bind", "79", "bind_nodes")
    cp.mark_done(state, phase="bind", product_id="79", step_id="bind_nodes")
    assert cp.is_done(state, "bind", "79", "bind_nodes")
