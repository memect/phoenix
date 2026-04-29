import asyncio
import json

import pytest

from agentic_extract.events import EventWriter, event_writer_scope
from agentic_extract.runtime import RunRecorder, run_with_heartbeat, runtime_scope
from agentic_extract.types import TokenUsage


@pytest.mark.asyncio
async def test_run_recorder_tracks_events_and_iteration_usage():
    events = []
    recorder = RunRecorder(on_event=events.append, heartbeat_interval_sec=0.01)

    with runtime_scope(recorder=recorder):
        await recorder.start_run(message="start")
        await recorder.start_phase("setup")
        await recorder.finish_phase("setup")
        await recorder.start_iteration(1)
        with runtime_scope(iteration=1):
            await recorder.start_step("dev_agent")
            with runtime_scope(step="dev_agent"):
                recorder.record_usage(TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5))
            await recorder.finish_step("dev_agent", message="dev done")
        await recorder.finish_iteration(action="call_dev", summary="iteration done")
        result = await recorder.finish_run(status="completed")

    assert [event.type for event in events] == [
        "run_started",
        "phase_started",
        "phase_completed",
        "iteration_started",
        "step_started",
        "step_completed",
        "iteration_completed",
        "run_completed",
    ]
    assert result.status == "completed"
    assert result.iteration_count == 1
    assert result.token_usage.total_tokens == 5
    assert result.iteration_token_usage.total_tokens == 5
    assert result.iterations[0].token_usage.total_tokens == 5
    assert result.iterations[0].duration_sec >= 0


@pytest.mark.asyncio
async def test_callback_failure_does_not_break_main_flow():
    seen = []

    def flaky_callback(event):
        seen.append(event.type)
        raise RuntimeError("callback failed")

    recorder = RunRecorder(on_event=flaky_callback)

    await recorder.start_run()
    result = await recorder.finish_run(status="completed")

    assert seen == ["run_started", "run_completed"]
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_run_with_heartbeat_emits_periodic_events():
    events = []
    recorder = RunRecorder(on_event=events.append, heartbeat_interval_sec=0.01)

    with runtime_scope(recorder=recorder):
        await recorder.start_run()
        await recorder.start_iteration(1)
        with runtime_scope(iteration=1):
            await recorder.start_step("dev_agent")
            with runtime_scope(step="dev_agent"):
                result = await run_with_heartbeat(
                    asyncio.sleep(0.03, result="ok"),
                    recorder=recorder,
                    message="still running",
                )
            await recorder.finish_step("dev_agent")
        await recorder.finish_iteration(action="call_dev")
        await recorder.finish_run(status="completed")

    heartbeat_events = [event for event in events if event.type == "heartbeat"]
    assert result == "ok"
    assert heartbeat_events
    assert all(event.step == "dev_agent" for event in heartbeat_events)


@pytest.mark.asyncio
async def test_run_recorder_writes_progress_events_to_events_jsonl(tmp_path):
    recorder = RunRecorder()
    writer = EventWriter.for_workspace(tmp_path, entrypoint="run")

    with event_writer_scope(writer):
        with runtime_scope(recorder=recorder):
            await recorder.start_run(message="start")
            await recorder.finish_run(status="completed", message="done")

    lines = [
        json.loads(line)
        for line in (tmp_path / ".agent_state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [line["type"] for line in lines] == ["run_started", "run_completed"]
    assert lines[0]["category"] == "progress"
    assert lines[1]["data"]["iteration_count"] == 0
