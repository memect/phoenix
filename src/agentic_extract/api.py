"""Public Python API for agentic_extract."""

from __future__ import annotations

import asyncio
import shutil
import warnings
from pathlib import Path

from .config import AgenticExtractSettings, resolve_settings
from .events import EventWriter, emit_event, event_writer_scope, get_current_event_writer
from .prepare import inspect_prepare_decision, prepare_workspace_data
from .types import PrepareSpec, RunRequest, RunResult


async def _run_settings_async(
    settings: AgenticExtractSettings,
    *,
    dry_run: bool = False,
    on_event=None,
    heartbeat_interval_sec: float = 10.0,
) -> RunResult:
    """Internal async execution hook for resolved settings."""
    from .runner import run_settings_async

    current_writer = get_current_event_writer()
    if current_writer is None:
        writer = EventWriter.for_workspace(settings.workspace, entrypoint="run")
        with event_writer_scope(writer):
            emit_event(
                "settings_resolved",
                category="system",
                dry_run=dry_run,
                settings={
                    "workspace": str(Path(settings.workspace).expanduser().resolve()),
                    "max_iterations": settings.max_iterations,
                    "target_accuracy": settings.target_accuracy,
                    **settings.execution_budget(),
                },
            )
            return await _run_settings_async(
                settings,
                dry_run=dry_run,
                on_event=on_event,
                heartbeat_interval_sec=heartbeat_interval_sec,
            )

    return await run_settings_async(
        settings,
        dry_run=dry_run,
        on_event=on_event,
        heartbeat_interval_sec=heartbeat_interval_sec,
    )


async def _run_request_async(request: RunRequest) -> RunResult:
    """Compatibility execution hook for legacy RunRequest callers."""
    from .runner import run_request_async

    return await run_request_async(request)


def _coerce_request(
    request: RunRequest | None,
    kwargs: dict,
) -> RunRequest:
    if request is not None and kwargs:
        raise ValueError("Pass either a RunRequest or keyword arguments, not both")
    if request is not None:
        return request
    return RunRequest(**kwargs)


def _coerce_settings(settings: AgenticExtractSettings | None, kwargs: dict) -> AgenticExtractSettings:
    if settings is not None and kwargs:
        raise ValueError("Pass either AgenticExtractSettings or keyword arguments, not both")
    if settings is not None:
        return settings
    return AgenticExtractSettings(**kwargs)


def _ensure_no_active_event_loop(entrypoint_name: str, async_name: str) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return

    raise RuntimeError(
        f"{entrypoint_name}() cannot be called from an active event loop; "
        f"use {async_name}() instead",
    )


def _reset_runtime_state(workspace: str | Path) -> list[Path]:
    workspace_path = Path(workspace).expanduser().resolve()
    removed_paths: list[Path] = []

    for path in [workspace_path / "logs", workspace_path / ".agent_state"]:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed_paths.append(path)

    return removed_paths


def _resolve_auto_settings(
    workspace: str | Path,
    *,
    config_path: str | Path | None = None,
    settings_overrides: dict | None = None,
) -> AgenticExtractSettings:
    workspace_str = str(Path(workspace))
    overrides = dict(settings_overrides or {})
    overrides["workspace"] = workspace_str
    return resolve_settings(
        workspace_str,
        config_path=config_path,
        overrides=overrides,
    )


async def run_agentic_extract_async(
    settings: AgenticExtractSettings | None = None,
    /,
    *,
    dry_run: bool = False,
    on_event=None,
    heartbeat_interval_sec: float = 10.0,
    **kwargs,
) -> RunResult:
    """Run agentic_extract asynchronously using resolved settings."""
    resolved_settings = _coerce_settings(settings, kwargs)
    return await _run_settings_async(
        resolved_settings,
        dry_run=dry_run,
        on_event=on_event,
        heartbeat_interval_sec=heartbeat_interval_sec,
    )


async def run_agentic_extract_auto_async(
    workspace: str | Path,
    *,
    prepare: PrepareSpec | None = None,
    config_path: str | Path | None = None,
    settings_overrides: dict | None = None,
    dry_run: bool = False,
    reset: bool = False,
    on_event=None,
    heartbeat_interval_sec: float = 10.0,
) -> RunResult:
    """High-level async API that resolves config, prepares data if needed, then runs."""
    if dry_run and reset:
        raise ValueError("reset 与 dry_run 不能同时使用")

    settings = _resolve_auto_settings(
        workspace,
        config_path=config_path,
        settings_overrides=settings_overrides,
    )

    removed_paths: list[Path] = []
    if not dry_run and reset:
        removed_paths = _reset_runtime_state(settings.workspace)

    writer = EventWriter.for_workspace(settings.workspace, entrypoint="auto")
    with event_writer_scope(writer):
        emit_event(
            "settings_resolved",
            category="system",
            dry_run=dry_run,
            settings={
                "workspace": str(Path(settings.workspace).expanduser().resolve()),
                "max_iterations": settings.max_iterations,
                "target_accuracy": settings.target_accuracy,
                **settings.execution_budget(),
            },
        )
        if removed_paths:
            emit_event(
                "runtime_reset",
                category="system",
                removed_paths=[str(path) for path in removed_paths],
            )

        if dry_run:
            emit_event(
                "prepare_skipped",
                category="system",
                reason="dry_run only validates runtime configuration",
            )
        else:
            decision = inspect_prepare_decision(settings.workspace, prepare, allow_normalize=True)
            emit_event(
                "prepare_decided",
                category="system",
                action=decision.action,
                reason=decision.reason,
            )
            emit_event(
                "prepare_started",
                category="system",
                prepare=(prepare.model_dump(mode="json") if prepare is not None else None),
            )
            try:
                applied_decision = prepare_workspace_data(settings.workspace, prepare)
            except Exception as exc:
                emit_event(
                    "prepare_failed",
                    category="system",
                    error=str(exc),
                )
                raise
            emit_event(
                "prepare_completed",
                category="system",
                action=applied_decision.action,
                reason=applied_decision.reason,
            )

        return await _run_settings_async(
            settings,
            dry_run=dry_run,
            on_event=on_event,
            heartbeat_interval_sec=heartbeat_interval_sec,
        )


async def run_agentic_extract_request_async(
    request: RunRequest | None = None,
    /,
    **kwargs,
) -> RunResult:
    """Compatibility async API for legacy RunRequest callers."""
    resolved_request = _coerce_request(request, kwargs)
    warnings.warn(
        "run_agentic_extract_request_async() / RunRequest is deprecated; use resolved "
        "AgenticExtractSettings with run_agentic_extract_async() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return await _run_request_async(resolved_request)


def run_agentic_extract(
    settings: AgenticExtractSettings | None = None,
    /,
    *,
    dry_run: bool = False,
    on_event=None,
    heartbeat_interval_sec: float = 10.0,
    **kwargs,
) -> RunResult:
    """Run agentic_extract synchronously.

    Raises:
        RuntimeError: If called from an active event loop.
    """
    _ensure_no_active_event_loop("run_agentic_extract", "run_agentic_extract_async")

    resolved_settings = _coerce_settings(settings, kwargs)
    return asyncio.run(
        _run_settings_async(
            resolved_settings,
            dry_run=dry_run,
            on_event=on_event,
            heartbeat_interval_sec=heartbeat_interval_sec,
        )
    )


def run_agentic_extract_auto(
    workspace: str | Path,
    *,
    prepare: PrepareSpec | None = None,
    config_path: str | Path | None = None,
    settings_overrides: dict | None = None,
    dry_run: bool = False,
    reset: bool = False,
    on_event=None,
    heartbeat_interval_sec: float = 10.0,
) -> RunResult:
    """High-level sync API that resolves config, prepares data if needed, then runs."""
    _ensure_no_active_event_loop("run_agentic_extract_auto", "run_agentic_extract_auto_async")

    return asyncio.run(
        run_agentic_extract_auto_async(
            workspace,
            prepare=prepare,
            config_path=config_path,
            settings_overrides=settings_overrides,
            dry_run=dry_run,
            reset=reset,
            on_event=on_event,
            heartbeat_interval_sec=heartbeat_interval_sec,
        )
    )


def run_agentic_extract_request(
    request: RunRequest | None = None,
    /,
    **kwargs,
) -> RunResult:
    """Compatibility sync API for legacy RunRequest callers."""
    _ensure_no_active_event_loop("run_agentic_extract_request", "run_agentic_extract_request_async")

    resolved_request = _coerce_request(request, kwargs)
    warnings.warn(
        "run_agentic_extract_request() / RunRequest is deprecated; use resolved "
        "AgenticExtractSettings with run_agentic_extract() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return asyncio.run(_run_request_async(resolved_request))
