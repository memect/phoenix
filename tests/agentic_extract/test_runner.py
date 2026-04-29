import asyncio
from types import SimpleNamespace

import pytest
from agentscope.message import Msg

from agentic_extract.config import AgenticExtractSettings
from agentic_extract.runner import _create_agents, run_request_async, run_settings_async
from agentic_extract.types import RunRequest


class FakeStateManager:
    def __init__(self, _workspace):
        self.current_iteration = 0
        self.status = None
        self.saved = 0

    def init(self):
        return None

    def load_all_agents(self, _agents):
        return None

    def save_all_agents(self, _agents):
        self.saved += 1

    def get_iteration_number(self):
        return self.current_iteration

    def get_git_head(self):
        return "abc123"

    def git_commit(self, _message):
        return "def456"

    def record_iteration(self, decision, **kwargs):
        _ = kwargs
        self.current_iteration += 1
        self.last_action = decision.action

    def mark_completed(self):
        self.status = "completed"

    def mark_failed(self, reason):
        self.status = f"failed:{reason}"

    def get_recent_summary(self):
        return "none"


class FakeSupervisorAgent:
    async def __call__(self, msg, **kwargs):
        _ = (msg, kwargs)
        return Msg(name="Supervisor", content="ok", role="assistant")

    async def observe(self, _msg):
        return None

    def state_dict(self):
        return {}

    def load_state_dict(self, state, strict=False):
        _ = (state, strict)


class FakeBusinessAgent(FakeSupervisorAgent):
    async def __call__(self, msg, **kwargs):
        _ = (msg, kwargs)
        return Msg(name="BusinessAgent", content="business done", role="assistant")


class FakeDevAgent(FakeSupervisorAgent):
    async def __call__(self, msg, **kwargs):
        _ = (msg, kwargs)
        await asyncio.sleep(0.03)
        return Msg(name="DevAgent", content="dev done", role="assistant")


def test_create_agents_uses_per_agent_iter_budgets(monkeypatch):
    captured = {}

    def fake_create_supervisor(**kwargs):
        captured["supervisor"] = kwargs
        return FakeSupervisorAgent()

    def fake_create_business_agent(**kwargs):
        captured["business"] = kwargs
        return FakeBusinessAgent()

    def fake_create_dev_agent(**kwargs):
        captured["dev"] = kwargs
        return FakeDevAgent()

    monkeypatch.setattr("agentic_extract.runner.create_supervisor", fake_create_supervisor)
    monkeypatch.setattr("agentic_extract.runner.create_business_agent", fake_create_business_agent)
    monkeypatch.setattr("agentic_extract.runner.create_dev_agent", fake_create_dev_agent)

    settings = AgenticExtractSettings(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        agent_max_iters=8,
        supervisor_max_iters=3,
        business_max_iters=4,
        dev_max_iters=10,
    )

    agents = _create_agents(settings)

    assert set(agents) == {"supervisor", "business_agent", "dev_agent"}
    assert captured["supervisor"]["max_iters"] == 3
    assert captured["business"]["max_iters"] == 4
    assert captured["dev"]["max_iters"] == 10


def test_create_agents_falls_back_to_agent_max_iters(monkeypatch):
    captured = {}

    def fake_create_supervisor(**kwargs):
        captured["supervisor"] = kwargs
        return FakeSupervisorAgent()

    def fake_create_business_agent(**kwargs):
        captured["business"] = kwargs
        return FakeBusinessAgent()

    def fake_create_dev_agent(**kwargs):
        captured["dev"] = kwargs
        return FakeDevAgent()

    monkeypatch.setattr("agentic_extract.runner.create_supervisor", fake_create_supervisor)
    monkeypatch.setattr("agentic_extract.runner.create_business_agent", fake_create_business_agent)
    monkeypatch.setattr("agentic_extract.runner.create_dev_agent", fake_create_dev_agent)

    settings = AgenticExtractSettings(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        agent_max_iters=7,
        supervisor_max_iters=2,
    )

    _create_agents(settings)

    assert captured["supervisor"]["max_iters"] == 2
    assert captured["business"]["max_iters"] == 7
    assert captured["dev"]["max_iters"] == 7


@pytest.mark.asyncio
async def test_runner_success_path_emits_events_and_heartbeat(monkeypatch, tmp_path):
    events = []
    decisions = [
        SimpleNamespace(action="call_dev", reasoning="write code", task="implement"),
        SimpleNamespace(action="done", reasoning="done", task=""),
    ]

    async def fake_get_supervisor_decision(*args, **kwargs):
        _ = (args, kwargs)
        return decisions.pop(0)

    async def fake_probe(*args, **kwargs):
        _ = (args, kwargs)
        return SimpleNamespace(supported=True, usage=None)

    monkeypatch.setattr("agentic_extract.runner.create_workspace", lambda path: tmp_path / path)
    monkeypatch.setattr("agentic_extract.runner.setup_environment", lambda _workspace: None)
    monkeypatch.setattr("agentic_extract.runner.init_workspace", lambda _workspace: None)
    monkeypatch.setattr("agentic_extract.runner.ensure_workspace_ready", lambda _workspace: None)
    monkeypatch.setattr("agentic_extract.runner.StateManager", FakeStateManager)
    monkeypatch.setattr("agentic_extract.runner.probe_structured_output", fake_probe)
    monkeypatch.setattr("agentic_extract.runner.get_supervisor_decision", fake_get_supervisor_decision)
    monkeypatch.setattr("agentic_extract.runner.create_supervisor", lambda **kwargs: FakeSupervisorAgent())
    monkeypatch.setattr("agentic_extract.runner.create_business_agent", lambda **kwargs: FakeBusinessAgent())
    monkeypatch.setattr("agentic_extract.runner.create_dev_agent", lambda **kwargs: FakeDevAgent())

    settings = AgenticExtractSettings(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        workspace="workspace",
    )

    result = await run_settings_async(
        settings,
        on_event=events.append,
        heartbeat_interval_sec=0.01,
    )

    event_types = [event.type for event in events]
    assert result.status == "completed"
    assert result.iteration_count == 2
    assert "run_started" in event_types
    assert "supervisor_decided" in event_types
    assert "iteration_completed" in event_types
    assert "run_completed" in event_types
    assert any(event.type == "heartbeat" and event.step == "dev_agent" for event in events)


@pytest.mark.asyncio
async def test_runner_failure_returns_failed_result(monkeypatch, tmp_path):
    events = []

    async def fake_get_supervisor_decision(*args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError("supervisor exploded")

    async def fake_probe(*args, **kwargs):
        _ = (args, kwargs)
        return SimpleNamespace(supported=True, usage=None)

    monkeypatch.setattr("agentic_extract.runner.create_workspace", lambda path: tmp_path / path)
    monkeypatch.setattr("agentic_extract.runner.setup_environment", lambda _workspace: None)
    monkeypatch.setattr("agentic_extract.runner.init_workspace", lambda _workspace: None)
    monkeypatch.setattr("agentic_extract.runner.ensure_workspace_ready", lambda _workspace: None)
    monkeypatch.setattr("agentic_extract.runner.StateManager", FakeStateManager)
    monkeypatch.setattr("agentic_extract.runner.probe_structured_output", fake_probe)
    monkeypatch.setattr("agentic_extract.runner.get_supervisor_decision", fake_get_supervisor_decision)
    monkeypatch.setattr("agentic_extract.runner.create_supervisor", lambda **kwargs: FakeSupervisorAgent())
    monkeypatch.setattr("agentic_extract.runner.create_business_agent", lambda **kwargs: FakeBusinessAgent())
    monkeypatch.setattr("agentic_extract.runner.create_dev_agent", lambda **kwargs: FakeDevAgent())

    settings = AgenticExtractSettings(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        workspace="workspace",
    )

    result = await run_settings_async(settings, on_event=events.append)

    assert result.status == "failed"
    assert "supervisor exploded" in (result.error or "")
    assert any(event.type == "run_failed" for event in events)


@pytest.mark.asyncio
async def test_legacy_run_request_async_warns_and_delegates(monkeypatch):
    captured = {}

    async def fake_run(settings, *, dry_run=False, on_event=None, heartbeat_interval_sec=10.0):
        captured["settings"] = settings
        captured["dry_run"] = dry_run
        captured["on_event"] = on_event
        captured["heartbeat_interval_sec"] = heartbeat_interval_sec
        return SimpleNamespace(status="completed")

    monkeypatch.setattr("agentic_extract.runner.run_settings_async", fake_run)

    request = RunRequest(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        workspace="workspace",
        dry_run=True,
        heartbeat_interval_sec=2.5,
        on_event=events.append if (events := []) is not None else None,
    )

    with pytest.deprecated_call(match="RunRequest-based execution is deprecated"):
        result = await run_request_async(request)

    assert result.status == "completed"
    assert captured["settings"].model == "demo"
    assert captured["dry_run"] is True
    assert captured["heartbeat_interval_sec"] == 2.5
    assert captured["on_event"] is request.on_event
