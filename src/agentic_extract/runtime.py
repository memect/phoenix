"""Runtime orchestration helpers: recorder, scope, and heartbeat."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator

from .types import (
    ActionType,
    EvaluationSummary,
    ProgressCallback,
    ProgressEvent,
    RunResult,
    RunStatus,
    StepType,
    TokenUsage,
    utc_now,
)
from .events import emit_progress_event
from .usage import add_usage, clone_usage

logger = logging.getLogger(__name__)

_UNSET = object()

_current_recorder: ContextVar["RunRecorder | None"] = ContextVar(
    "agentic_extract_current_recorder",
    default=None,
)
_current_phase: ContextVar[StepType | None] = ContextVar(
    "agentic_extract_current_phase",
    default=None,
)
_current_iteration: ContextVar[int | None] = ContextVar(
    "agentic_extract_current_iteration",
    default=None,
)
_current_step: ContextVar[StepType | None] = ContextVar(
    "agentic_extract_current_step",
    default=None,
)


@dataclass(frozen=True)
class RuntimeScope:
    phase: StepType | None
    iteration: int | None
    step: StepType | None


def get_current_recorder() -> "RunRecorder | None":
    return _current_recorder.get()


def get_current_scope() -> RuntimeScope:
    return RuntimeScope(
        phase=_current_phase.get(),
        iteration=_current_iteration.get(),
        step=_current_step.get(),
    )


@contextmanager
def runtime_scope(
    *,
    recorder: "RunRecorder | object" = _UNSET,
    phase: StepType | None | object = _UNSET,
    iteration: int | None | object = _UNSET,
    step: StepType | None | object = _UNSET,
) -> Iterator[None]:
    """Bind runtime context for downstream usage tracking."""
    tokens: list[tuple[ContextVar, Token]] = []
    if recorder is not _UNSET:
        tokens.append((_current_recorder, _current_recorder.set(recorder)))
    if phase is not _UNSET:
        tokens.append((_current_phase, _current_phase.set(phase)))
    if iteration is not _UNSET:
        tokens.append((_current_iteration, _current_iteration.set(iteration)))
    if step is not _UNSET:
        tokens.append((_current_step, _current_step.set(step)))

    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class RunRecorder:
    """Single source of truth for runtime events, timing, and token usage."""

    def __init__(
        self,
        *,
        on_event: ProgressCallback | None = None,
        heartbeat_interval_sec: float = 10.0,
    ) -> None:
        self.on_event = on_event
        self.heartbeat_interval_sec = heartbeat_interval_sec

        self.started_at = utc_now()
        self.finished_at: Any = None
        self._run_started_monotonic: float | None = None

        self._run_usage = TokenUsage()
        self._iteration_total_usage = TokenUsage()
        self._iterations: list[Any] = []

        self._current_phase: StepType | None = None
        self._current_phase_started_monotonic: float | None = None

        self._current_iteration_index: int | None = None
        self._current_iteration_started_at = None
        self._current_iteration_started_monotonic: float | None = None
        self._current_iteration_usage: TokenUsage | None = None

        self._current_step: StepType | None = None
        self._current_step_started_monotonic: float | None = None
        self._current_step_usage: TokenUsage | None = None

    @property
    def iterations(self):
        return list(self._iterations)

    def record_usage(self, delta: TokenUsage | None) -> None:
        """Record usage against the current bound runtime scope."""
        if delta is None:
            return

        self._run_usage = add_usage(self._run_usage, delta)
        if self._current_iteration_usage is not None:
            self._current_iteration_usage = add_usage(self._current_iteration_usage, delta)
            self._iteration_total_usage = add_usage(self._iteration_total_usage, delta)
        if self._current_step_usage is not None:
            self._current_step_usage = add_usage(self._current_step_usage, delta)

    async def start_run(self, *, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        self.started_at = utc_now()
        self._run_started_monotonic = time.monotonic()
        await self._emit(
            ProgressEvent(
                type="run_started",
                message=message,
                data=data or {},
                token_usage_total=clone_usage(self._run_usage),
            )
        )

    async def finish_run(
        self,
        *,
        status: RunStatus,
        error: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> RunResult:
        self.finished_at = utc_now()
        result = self.build_result(status=status, error=error)
        payload = {
            "iteration_count": result.iteration_count,
            **(data or {}),
        }
        await self._emit(
            ProgressEvent(
                type="run_completed" if status == "completed" else "run_failed",
                status="completed" if status == "completed" else "failed",
                message=message,
                elapsed_total_iteration_sec=result.total_iteration_duration_sec,
                elapsed_total_run_sec=result.total_run_duration_sec,
                token_usage_total=clone_usage(self._run_usage),
                data=payload,
            )
        )
        return result

    async def start_phase(
        self,
        phase: StepType,
        *,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._current_phase = phase
        self._current_phase_started_monotonic = time.monotonic()
        await self._emit(
            ProgressEvent(
                type="phase_started",
                step=phase,
                message=message,
                token_usage_total=clone_usage(self._run_usage),
                data=data or {},
            )
        )

    async def finish_phase(
        self,
        phase: StepType,
        *,
        status: str = "completed",
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        elapsed = self._elapsed(self._current_phase_started_monotonic)
        await self._emit(
            ProgressEvent(
                type="phase_completed",
                step=phase,
                status=status,
                message=message,
                elapsed_step_sec=elapsed,
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_total=clone_usage(self._run_usage),
                data=data or {},
            )
        )
        self._current_phase = None
        self._current_phase_started_monotonic = None

    async def start_iteration(self, iteration: int, *, message: str | None = None) -> None:
        self._current_iteration_index = iteration
        self._current_iteration_started_at = utc_now()
        self._current_iteration_started_monotonic = time.monotonic()
        self._current_iteration_usage = TokenUsage()
        await self._emit(
            ProgressEvent(
                type="iteration_started",
                iteration=iteration,
                message=message,
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_total=clone_usage(self._run_usage),
            )
        )

    async def finish_iteration(
        self,
        *,
        action: ActionType | None = None,
        evaluation: EvaluationSummary | None = None,
        summary: str | None = None,
        error: str | None = None,
    ):
        if self._current_iteration_index is None or self._current_iteration_started_at is None:
            raise RuntimeError("No active iteration to finish")

        finished_at = utc_now()
        duration_sec = self._elapsed(self._current_iteration_started_monotonic)
        iteration_usage = self._current_iteration_usage or TokenUsage()
        result = self._build_iteration_result(
            iteration=self._current_iteration_index,
            action=action,
            evaluation=evaluation,
            summary=summary,
            error=error,
            started_at=self._current_iteration_started_at,
            finished_at=finished_at,
            duration_sec=duration_sec,
            token_usage=iteration_usage,
        )
        self._iterations.append(result)

        await self._emit(
            ProgressEvent(
                type="iteration_completed",
                status="failed" if error else "completed",
                iteration=self._current_iteration_index,
                message=summary,
                elapsed_iteration_sec=duration_sec,
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_delta=clone_usage(iteration_usage),
                token_usage_total=clone_usage(self._run_usage),
                data={
                    "action": action,
                    "iteration_status": "failed" if error else "completed",
                },
            )
        )

        self._current_iteration_index = None
        self._current_iteration_started_at = None
        self._current_iteration_started_monotonic = None
        self._current_iteration_usage = None
        return result

    async def start_step(
        self,
        step: StepType,
        *,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._current_step = step
        self._current_step_started_monotonic = time.monotonic()
        self._current_step_usage = TokenUsage()
        await self._emit(
            ProgressEvent(
                type="step_started",
                iteration=self._current_iteration_index,
                step=step,
                message=message,
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_total=clone_usage(self._run_usage),
                data=data or {},
            )
        )

    async def finish_step(
        self,
        step: StepType,
        *,
        status: str = "completed",
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        step_usage = clone_usage(self._current_step_usage or TokenUsage())
        await self._emit(
            ProgressEvent(
                type="step_completed",
                status=status,
                iteration=self._current_iteration_index,
                step=step,
                message=message,
                elapsed_step_sec=self._elapsed(self._current_step_started_monotonic),
                elapsed_iteration_sec=self._elapsed(self._current_iteration_started_monotonic),
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_delta=step_usage,
                token_usage_total=clone_usage(self._run_usage),
                data=data or {},
            )
        )
        self._current_step = None
        self._current_step_started_monotonic = None
        self._current_step_usage = None

    async def emit_supervisor_decided(
        self,
        *,
        action: ActionType,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload = {"action": action, **(data or {})}
        await self._emit(
            ProgressEvent(
                type="supervisor_decided",
                iteration=self._current_iteration_index,
                step="supervisor",
                message=message,
                elapsed_step_sec=self._elapsed(self._current_step_started_monotonic),
                elapsed_iteration_sec=self._elapsed(self._current_iteration_started_monotonic),
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_total=clone_usage(self._run_usage),
                data=payload,
            )
        )

    async def emit_heartbeat(
        self,
        *,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        await self._emit(
            ProgressEvent(
                type="heartbeat",
                iteration=self._current_iteration_index,
                step=self._current_step,
                message=message,
                elapsed_step_sec=self._elapsed(self._current_step_started_monotonic),
                elapsed_iteration_sec=self._elapsed(self._current_iteration_started_monotonic),
                elapsed_total_iteration_sec=self.total_iteration_duration_sec,
                elapsed_total_run_sec=self._elapsed_total_run(),
                token_usage_total=clone_usage(self._run_usage),
                data=data or {},
            )
        )

    @property
    def total_iteration_duration_sec(self) -> float:
        return sum(iteration.duration_sec for iteration in self._iterations)

    def build_result(self, *, status: RunStatus, error: str | None = None) -> RunResult:
        finished_at = self.finished_at or utc_now()
        total_run_duration = 0.0
        if self._run_started_monotonic is not None:
            if self.finished_at is None:
                total_run_duration = self._elapsed_total_run()
            else:
                total_run_duration = max(time.monotonic() - self._run_started_monotonic, 0.0)

        return RunResult(
            status=status,
            started_at=self.started_at,
            finished_at=finished_at,
            total_iteration_duration_sec=self.total_iteration_duration_sec,
            total_run_duration_sec=total_run_duration,
            iteration_count=len(self._iterations),
            token_usage=clone_usage(self._run_usage),
            iteration_token_usage=clone_usage(self._iteration_total_usage),
            iterations=self.iterations,
            error=error,
        )

    async def _emit(self, event: ProgressEvent) -> None:
        emit_progress_event(event)
        if self.on_event is None:
            return
        try:
            result = self.on_event(event)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Progress callback failed: %s", exc)

    @staticmethod
    def _elapsed(start_monotonic: float | None) -> float | None:
        if start_monotonic is None:
            return None
        return max(time.monotonic() - start_monotonic, 0.0)

    def _elapsed_total_run(self) -> float | None:
        return self._elapsed(self._run_started_monotonic)

    @staticmethod
    def _build_iteration_result(**kwargs):
        from .types import IterationResult

        return IterationResult(**kwargs)


def record_current_usage(delta: TokenUsage | None) -> None:
    recorder = get_current_recorder()
    if recorder is not None:
        recorder.record_usage(delta)


async def run_with_heartbeat(
    awaitable,
    *,
    recorder: RunRecorder,
    message: str | None = None,
    interval_sec: float | None = None,
):
    """Await a task while periodically emitting heartbeat events."""
    interval = recorder.heartbeat_interval_sec if interval_sec is None else interval_sec
    if interval <= 0:
        return await awaitable

    task = asyncio.create_task(awaitable)
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=interval)
        except asyncio.TimeoutError:
            await recorder.emit_heartbeat(message=message)


async def run_in_thread_with_heartbeat(
    func,
    *args,
    recorder: RunRecorder,
    message: str | None = None,
    interval_sec: float | None = None,
    **kwargs,
):
    """Run a blocking function in a worker thread with heartbeat support."""
    return await run_with_heartbeat(
        asyncio.to_thread(func, *args, **kwargs),
        recorder=recorder,
        message=message,
        interval_sec=interval_sec,
    )
