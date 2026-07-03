"""Checkpoint state for sync operations (provision, bind, deploy)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SyncPhase = Literal["provision", "bind", "deploy", "full"]
SyncRunStatus = Literal["in_progress", "failed", "completed"]


class SyncCurrentStep(BaseModel):
    phase: SyncPhase
    product_id: str | None = None
    step_id: str = ""


class SyncCompletedStep(BaseModel):
    phase: SyncPhase
    product_id: str | None = None
    step_id: str
    at: str
    ok: bool = True
    detail: dict[str, Any] = Field(default_factory=dict)


class SyncFailedStep(BaseModel):
    phase: SyncPhase
    product_id: str | None = None
    step_id: str
    error: str
    at: str


class SyncRunState(BaseModel):
    space_ref: str
    space_id: str | None = None
    run_id: str
    status: SyncRunStatus = "in_progress"
    started_at: str
    updated_at: str
    current: SyncCurrentStep | None = None
    completed: list[SyncCompletedStep] = Field(default_factory=list)
    failed: SyncFailedStep | None = None
    total_steps: int = 0

    def completed_keys(self) -> set[tuple[str, str | None, str]]:
        return {(c.phase, c.product_id, c.step_id) for c in self.completed}

    def is_step_done(self, phase: SyncPhase, product_id: str | None, step_id: str) -> bool:
        return (phase, product_id, step_id) in self.completed_keys()

    def progress_fraction(self) -> tuple[int, int]:
        done = len(self.completed)
        total = max(self.total_steps, done, 1)
        return done, total
