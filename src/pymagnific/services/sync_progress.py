"""Live progress reporting for v3 sync."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Protocol

from pymagnific.core.logging import get_logger
from pymagnific.schemas.sync_state import SyncPhase, SyncRunState

_log = get_logger("sync")


class SyncProgressReporter(Protocol):
    def on_run_start(self, state: SyncRunState) -> None: ...

    def on_step_start(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        message: str = "",
    ) -> None: ...

    def on_step_done(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        elapsed_s: float,
    ) -> None: ...

    def on_step_fail(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        error: str,
    ) -> None: ...

    def on_wait(self, operation_id: str, poll_n: int) -> None: ...


@dataclass
class NullSyncProgress:
    """No-op progress reporter."""

    def on_run_start(self, state: SyncRunState) -> None:
        pass

    def on_step_start(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        message: str = "",
    ) -> None:
        pass

    def on_step_done(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        elapsed_s: float,
    ) -> None:
        pass

    def on_step_fail(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        error: str,
    ) -> None:
        pass

    def on_wait(self, operation_id: str, poll_n: int) -> None:
        pass


@dataclass
class CliSyncProgress:
    """Line-by-line progress on stderr."""

    _step_starts: dict[tuple[str, str | None, str], float] = field(default_factory=dict)

    def _label(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
    ) -> str:
        done, total = state.progress_fraction()
        pid = f" #{product_id}" if product_id else ""
        return f"[{done + 1}/{total}] {phase}{pid} {step_id}"

    def on_run_start(self, state: SyncRunState) -> None:
        msg = f"sync run {state.run_id[:8]}... ({state.total_steps} steps)"
        print(msg, file=sys.stderr, flush=True)
        _log.info(msg)

    def on_step_start(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        message: str = "",
    ) -> None:
        key = (phase, product_id, step_id)
        self._step_starts[key] = time.monotonic()
        extra = f" {message}" if message else ""
        line = f"{self._label(state, phase=phase, product_id=product_id, step_id=step_id)} ... started{extra}"
        print(line, file=sys.stderr, flush=True)
        _log.info(line)

    def on_step_done(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        elapsed_s: float,
    ) -> None:
        line = f"{self._label(state, phase=phase, product_id=product_id, step_id=step_id)} ... ok ({elapsed_s:.1f}s)"
        print(line, file=sys.stderr, flush=True)
        _log.info(line)

    def on_step_fail(
        self,
        state: SyncRunState,
        *,
        phase: SyncPhase,
        product_id: str | None,
        step_id: str,
        error: str,
    ) -> None:
        line = f"{self._label(state, phase=phase, product_id=product_id, step_id=step_id)} ... FAILED: {error}"
        print(line, file=sys.stderr, flush=True)
        _log.error(line)

    def on_wait(self, operation_id: str, poll_n: int) -> None:
        line = f"  waiting for edit {operation_id[:12]}... (poll {poll_n})"
        print(line, file=sys.stderr, flush=True)
        _log.info(line)


@dataclass
class SyncContext:
    """Optional checkpoint + progress for a sync run."""

    checkpoint: object | None = None
    run_state: SyncRunState | None = None
    progress: SyncProgressReporter | None = None
    resume: bool = False

    @property
    def active(self) -> bool:
        return self.checkpoint is not None and self.run_state is not None
