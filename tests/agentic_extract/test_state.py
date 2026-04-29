import json
from datetime import datetime, timedelta, timezone

from agentic_extract.state import (
    CurrentState,
    EvaluationSnapshot,
    IterationRecord,
    StateManager,
    SupervisorDecision,
)
from agentic_extract.types import TokenUsage


def test_state_record_iteration_persists_runtime_fields(tmp_path):
    state = StateManager(tmp_path)
    state.init()

    started_at = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
    finished_at = started_at + timedelta(seconds=12.5)
    token_usage = TokenUsage(
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        cached_input_tokens=40,
        reasoning_output_tokens=8,
        details_complete=True,
    )
    evaluation = EvaluationSnapshot(
        accuracy=0.91,
        field_average=0.89,
        doc_count=10,
        error_count=1,
    )

    state.record_iteration(
        decision=SupervisorDecision(
            action="call_dev",
            reasoning="need code changes",
            task="update extractor",
        ),
        agent_output="done",
        evaluation=evaluation,
        git_commit_before="abc123",
        git_commit_after="def456",
        started_at=started_at,
        finished_at=finished_at,
        duration_sec=12.5,
        token_usage=token_usage,
        summary="call_dev completed",
        error="minor issue",
    )

    record = state.get_iteration_record(1)
    assert record is not None
    assert record.started_at == started_at
    assert record.finished_at == finished_at
    assert record.duration_sec == 12.5
    assert record.token_usage == token_usage
    assert record.summary == "call_dev completed"
    assert record.error == "minor issue"
    assert record.git_commit_before == "abc123"
    assert record.git_commit_after == "def456"

    raw = json.loads(
        (tmp_path / ".agent_state" / "iterations" / "iter_001.json").read_text()
    )
    assert raw["duration_sec"] == 12.5
    assert raw["token_usage"]["cached_input_tokens"] == 40
    assert raw["summary"] == "call_dev completed"
    assert raw["error"] == "minor issue"
    assert (tmp_path / ".agent_state" / "current.json").exists()


def test_current_state_updates_in_agent_state(tmp_path):
    state = StateManager(tmp_path)
    state.init()

    state.record_iteration(
        decision=SupervisorDecision(action="evaluate", reasoning="check", task="run eval"),
        summary="evaluate completed",
    )
    state.mark_failed("boom")

    failed_state = StateManager(tmp_path).current
    assert failed_state.current_iteration == 1
    assert failed_state.status == "failed"
    assert failed_state.error == "boom"
    assert failed_state.finished_at is not None
    assert failed_state.total_run_duration_sec is not None

    current_path = tmp_path / ".agent_state" / "current.json"
    raw = json.loads(current_path.read_text(encoding="utf-8"))
    assert raw["current_iteration"] == 1
    assert raw["status"] == "failed"
    assert raw["error"] == "boom"


def test_current_state_falls_back_to_legacy_logs_current_json(tmp_path):
    legacy_logs_dir = tmp_path / "logs"
    legacy_logs_dir.mkdir(parents=True)
    (legacy_logs_dir / "current.json").write_text(
        json.dumps(
            {
                "current_iteration": 3,
                "status": "failed: legacy boom",
                "last_update": "2026-04-15T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    state = StateManager(tmp_path)
    state.init()

    legacy_state = state.current
    assert legacy_state.current_iteration == 3
    assert legacy_state.status == "failed"
    assert legacy_state.error == "legacy boom"
    assert not (tmp_path / ".agent_state" / "current.json").exists()


def test_recent_summary_falls_back_to_legacy_iteration_records(tmp_path):
    legacy_logs_dir = tmp_path / "logs"
    legacy_iterations_dir = legacy_logs_dir / "iterations"
    legacy_iterations_dir.mkdir(parents=True)
    (legacy_logs_dir / "current.json").write_text(
        CurrentState(
            current_iteration=2,
            status="running",
            started_at=datetime(2026, 4, 15, 0, 0, 0, tzinfo=timezone.utc),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    (legacy_iterations_dir / "iter_001.json").write_text(
        IterationRecord(
            iteration=1,
            supervisor_decision=SupervisorDecision(
                action="call_dev",
                reasoning="first pass",
                task="write extractor",
            ),
            evaluation=EvaluationSnapshot(accuracy=0.75),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    (legacy_iterations_dir / "iter_002.json").write_text(
        IterationRecord(
            iteration=2,
            supervisor_decision=SupervisorDecision(
                action="evaluate",
                reasoning="check quality",
                task="run eval",
            ),
            evaluation=EvaluationSnapshot(accuracy=0.80),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    state = StateManager(tmp_path)
    state.init()

    summary = state.get_recent_summary()
    assert "iter 1: call_dev - write extractor" in summary
    assert "iter 2: evaluate - run eval" in summary
    assert "准确率趋势: iter1 75.0% → iter2 80.0% (Δ+5.0%)" in summary


class FakeAgent:
    def __init__(self, payload=None):
        self.payload = payload or {"messages": ["hello"]}
        self.loaded = None

    def state_dict(self):
        return self.payload

    def load_state_dict(self, state, strict=False):
        self.loaded = (state, strict)


def test_state_save_and_load_agent_memory_round_trip(tmp_path):
    state = StateManager(tmp_path)
    state.init()

    original = FakeAgent(payload={"messages": ["hello"], "count": 2})
    restored = FakeAgent(payload={})

    state.save_all_agents({"supervisor": original})
    state.load_all_agents({"supervisor": restored})

    assert restored.loaded == ({"messages": ["hello"], "count": 2}, False)
