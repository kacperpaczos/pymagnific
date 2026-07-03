"""Persistent checkpoint for resumable v3 sync."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pymagnific.schemas.sync_state import (
    SyncCompletedStep,
    SyncCurrentStep,
    SyncFailedStep,
    SyncPhase,
    SyncRunState,
)


class SyncCheckpoint:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def load(self) -> SyncRunState | None:
        if not self._path.is_file():
            return None
        return SyncRunState.model_validate_json(self._path.read_text(encoding="utf-8"))

    def clear(self) -> None:
        if self._path.is_file():
            self._path.unlink()

    def _save(self, state: SyncRunState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._path)

    def start_run(
        self,
        space_ref: str,
        *,
        space_id: str | None = None,
        total_steps: int,
        resume: bool = False,
    ) -> SyncRunState:
        now = datetime.now(UTC).isoformat()
        if resume:
            existing = self.load()
            if existing and existing.space_ref == space_ref and existing.status in (
                "in_progress",
                "failed",
            ):
                existing.status = "in_progress"
                existing.failed = None
                existing.updated_at = now
                existing.total_steps = max(existing.total_steps, total_steps)
                if space_id:
                    existing.space_id = space_id
                self._save(existing)
                return existing

        state = SyncRunState(
            space_ref=space_ref,
            space_id=space_id,
            run_id=str(uuid.uuid4()),
            status="in_progress",
            started_at=now,
            updated_at=now,
            total_steps=total_steps,
        )
        self._save(state)
        return state

    def set_current(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
    ) -> SyncRunState:
        state.current = SyncCurrentStep(
            phase=phase, product_id=product_id, step_id=step_id
        )
        state.updated_at = datetime.now(UTC).isoformat()
        self._save(state)
        return state

    def mark_done(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        detail: dict | None = None,
    ) -> SyncRunState:
        state.completed.append(
            SyncCompletedStep(
                phase=phase,
                product_id=product_id,
                step_id=step_id,
                at=datetime.now(UTC).isoformat(),
                ok=True,
                detail=detail or {},
            )
        )
        state.current = None
        state.updated_at = datetime.now(UTC).isoformat()
        self._save(state)
        return state

    def mark_failed(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        error: str,
    ) -> SyncRunState:
        state.status = "failed"
        state.failed = SyncFailedStep(
            phase=phase,
            product_id=product_id,
            step_id=step_id,
            error=error,
            at=datetime.now(UTC).isoformat(),
        )
        state.updated_at = datetime.now(UTC).isoformat()
        self._save(state)
        return state

    def mark_completed(self, state: SyncRunState) -> SyncRunState:
        state.status = "completed"
        state.current = None
        state.failed = None
        state.updated_at = datetime.now(UTC).isoformat()
        self._save(state)
        return state

    def is_done(
        self,
        state: SyncRunState | None,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
    ) -> bool:
        if state is None:
            return False
        return state.is_step_done(phase, product_id, step_id)
