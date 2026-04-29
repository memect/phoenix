from datetime import timezone

from agentic_extract.types import ProgressEvent, RunRequest, RunResult, TokenUsage


def test_public_models_have_stable_defaults():
    request = RunRequest(model="demo", api_base="https://example.com", api_key="secret")
    event = ProgressEvent(type="run_started")
    result = RunResult(status="completed")

    assert request.workspace == "workspace"
    assert request.heartbeat_interval_sec == 10.0
    assert request.supervisor_mode == "simple"
    assert request.max_iterations == 10
    assert request.agent_max_iters == 25
    assert request.supervisor_max_iters is None
    assert request.business_max_iters is None
    assert request.dev_max_iters is None
    assert event.status == "running"
    assert event.token_usage_total.total_tokens == 0
    assert result.iteration_count == 0
    assert result.token_usage.total_tokens == 0


def test_models_serialize_and_deserialize_cleanly():
    result = RunResult(status="failed", error="boom")
    payload = result.model_dump(mode="json")
    reloaded = RunResult.model_validate(payload)

    assert reloaded.status == "failed"
    assert reloaded.error == "boom"
    assert reloaded.started_at.tzinfo == timezone.utc
    assert reloaded.finished_at.tzinfo == timezone.utc


def test_run_request_excludes_callback_from_dump():
    def _callback(_event):
        return None

    request = RunRequest(
        model="demo",
        api_base="https://example.com",
        api_key="secret",
        on_event=_callback,
    )
    dumped = request.model_dump()

    assert "on_event" not in dumped


def test_token_usage_defaults_are_zero_safe():
    usage = TokenUsage()

    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.total_tokens == 0
    assert usage.cached_input_tokens is None
    assert usage.reasoning_output_tokens is None
    assert usage.details_complete is False
