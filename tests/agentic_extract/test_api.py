import asyncio
import json

import pytest

from agentic_extract.api import (
    run_agentic_extract,
    run_agentic_extract_auto,
    run_agentic_extract_auto_async,
    run_agentic_extract_async,
    run_agentic_extract_request,
    run_agentic_extract_request_async,
)
from agentic_extract.config import AgenticExtractSettings
from agentic_extract.prepare import PrepareDecision
from agentic_extract.types import PrepareSourcePdfDir, PrepareSpec, RunRequest, RunResult


@pytest.mark.asyncio
async def test_async_api_accepts_settings_and_delegates(monkeypatch):
    captured = {}

    async def fake_run(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        captured["settings"] = settings
        captured["dry_run"] = dry_run
        captured["on_event"] = on_event
        captured["heartbeat_interval_sec"] = heartbeat_interval_sec
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.api._run_settings_async", fake_run)

    settings = AgenticExtractSettings(model="demo", api_base="https://example.com", api_key="secret")
    result = await run_agentic_extract_async(settings, dry_run=True, heartbeat_interval_sec=3.5)

    assert result.status == "completed"
    assert captured["settings"] == settings
    assert captured["dry_run"] is True
    assert captured["heartbeat_interval_sec"] == 3.5


def test_sync_api_accepts_settings_kwargs_and_delegates(monkeypatch):
    captured = {}

    async def fake_run(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        captured["settings"] = settings
        return RunResult(status="completed", iteration_count=1)

    monkeypatch.setattr("agentic_extract.api._run_settings_async", fake_run)

    result = run_agentic_extract(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
    )

    assert result.status == "completed"
    assert result.iteration_count == 1
    assert captured["settings"].model == "demo"


@pytest.mark.asyncio
async def test_sync_api_rejects_active_event_loop(monkeypatch):
    async def fake_run(_settings, **_kwargs):
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.api._run_settings_async", fake_run)

    with pytest.raises(RuntimeError, match="active event loop"):
        run_agentic_extract(
            model="demo",
            api_base="https://example.com",
            api_key="secret",
        )


@pytest.mark.asyncio
async def test_auto_async_resolves_prepare_and_runs(monkeypatch, tmp_path):
    captured = {}
    settings = AgenticExtractSettings(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        workspace=str(tmp_path),
    )
    prepare = PrepareSpec(source=PrepareSourcePdfDir(pdfs_dir=str(tmp_path / "pdfs")))

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        captured["workspace"] = workspace
        captured["config_path"] = config_path
        captured["overrides"] = overrides
        captured["include_env"] = include_env
        return settings

    def fake_reset_runtime_state(workspace):
        captured["reset_workspace"] = workspace
        return [tmp_path / ".agent_state"]

    def fake_prepare_workspace_data(workspace, prepare_spec):
        captured["prepare_workspace"] = workspace
        captured["prepare_spec"] = prepare_spec
        return PrepareDecision(action="bootstrap", reason="bootstrapped")

    async def fake_run(resolved_settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        captured["run_settings"] = resolved_settings
        captured["dry_run"] = dry_run
        captured["on_event"] = on_event
        captured["heartbeat_interval_sec"] = heartbeat_interval_sec
        return RunResult(status="completed", iteration_count=2)

    monkeypatch.setattr("agentic_extract.api.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr("agentic_extract.api._reset_runtime_state", fake_reset_runtime_state)
    monkeypatch.setattr("agentic_extract.api.prepare_workspace_data", fake_prepare_workspace_data)
    monkeypatch.setattr("agentic_extract.api._run_settings_async", fake_run)

    result = await run_agentic_extract_auto_async(
        str(tmp_path),
        prepare=prepare,
        config_path="custom.json",
        settings_overrides={"model": "override-model"},
        reset=True,
        heartbeat_interval_sec=2.5,
    )

    assert result.status == "completed"
    assert captured["workspace"] == str(tmp_path)
    assert captured["config_path"] == "custom.json"
    assert captured["overrides"]["workspace"] == str(tmp_path)
    assert captured["overrides"]["model"] == "override-model"
    assert captured["reset_workspace"] == str(tmp_path)
    assert captured["prepare_workspace"] == str(tmp_path)
    assert captured["prepare_spec"] == prepare
    assert captured["run_settings"] == settings
    assert captured["dry_run"] is False
    assert captured["heartbeat_interval_sec"] == 2.5
    lines = [
        json.loads(line)
        for line in (tmp_path / ".agent_state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [line["type"] for line in lines[:5]] == [
        "settings_resolved",
        "runtime_reset",
        "prepare_decided",
        "prepare_started",
        "prepare_completed",
    ]


@pytest.mark.asyncio
async def test_auto_async_dry_run_skips_prepare_entirely(monkeypatch, tmp_path):
    captured = {}
    settings = AgenticExtractSettings(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        workspace=str(tmp_path),
    )
    prepare = PrepareSpec(source=PrepareSourcePdfDir(pdfs_dir=str(tmp_path / "pdfs")))

    def fake_resolve_settings(workspace, *, config_path=None, overrides=None, include_env=True):
        _ = (config_path, overrides, include_env)
        captured["workspace"] = workspace
        return settings

    async def fake_run(resolved_settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        _ = (on_event, heartbeat_interval_sec)
        captured["run_settings"] = resolved_settings
        captured["dry_run"] = dry_run
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.api.resolve_settings", fake_resolve_settings)
    monkeypatch.setattr(
        "agentic_extract.api.prepare_workspace_data",
        lambda *_args, **_kwargs: pytest.fail("prepare_workspace_data should not run during dry-run"),
    )
    monkeypatch.setattr(
        "agentic_extract.api._reset_runtime_state",
        lambda *_args, **_kwargs: pytest.fail("_reset_runtime_state should not run during dry-run"),
    )
    monkeypatch.setattr("agentic_extract.api._run_settings_async", fake_run)

    result = await run_agentic_extract_auto_async(
        str(tmp_path),
        prepare=prepare,
        settings_overrides={"model": "override-model"},
        dry_run=True,
    )

    assert result.status == "completed"
    assert captured["workspace"] == str(tmp_path)
    assert captured["run_settings"] == settings
    assert captured["dry_run"] is True
    lines = [
        json.loads(line)
        for line in (tmp_path / ".agent_state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [line["type"] for line in lines[:2]] == [
        "settings_resolved",
        "prepare_skipped",
    ]


def test_api_rejects_settings_and_kwargs_mixed():
    settings = AgenticExtractSettings(model="demo", api_base="https://example.com", api_key="secret")

    with pytest.raises(ValueError, match="either AgenticExtractSettings or keyword arguments"):
        asyncio.run(
            run_agentic_extract_async(
                settings,
                workspace="other",
            )
        )


@pytest.mark.asyncio
async def test_sync_auto_api_rejects_active_event_loop():
    with pytest.raises(RuntimeError, match="active event loop"):
        run_agentic_extract_auto(
            "workspace",
            settings_overrides={"model": "demo", "api_base": "https://example.com", "api_key": "secret"},
        )


def test_auto_api_rejects_reset_and_dry_run():
    with pytest.raises(ValueError, match="reset 与 dry_run"):
        asyncio.run(
            run_agentic_extract_auto_async(
                "workspace",
                dry_run=True,
                reset=True,
            )
        )


@pytest.mark.asyncio
async def test_legacy_request_async_api_accepts_request(monkeypatch):
    captured = {}

    async def fake_run(request):
        captured["request"] = request
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.api._run_request_async", fake_run)

    request = RunRequest(model="demo", api_base="https://example.com", api_key="secret")
    with pytest.deprecated_call(match="RunRequest is deprecated"):
        result = await run_agentic_extract_request_async(request)

    assert result.status == "completed"
    assert captured["request"] == request


def test_legacy_request_sync_api_accepts_request(monkeypatch):
    captured = {}

    async def fake_run(request):
        captured["request"] = request
        return RunResult(status="completed")

    monkeypatch.setattr("agentic_extract.api._run_request_async", fake_run)

    request = RunRequest(model="demo", api_base="https://example.com", api_key="secret")
    with pytest.deprecated_call(match="RunRequest is deprecated"):
        result = run_agentic_extract_request(request)

    assert result.status == "completed"
    assert captured["request"] == request
