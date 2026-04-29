from types import SimpleNamespace

import pytest

from agentic_extract.model_factory import UsageTrackingWrapper
from agentic_extract.runtime import RunRecorder, runtime_scope
from agentic_extract.types import TokenUsage
from agentic_extract.usage import add_usage, normalize_usage


def test_normalize_usage_from_openai_responses_shape():
    usage = SimpleNamespace(
        input_tokens=11,
        output_tokens=5,
        total_tokens=16,
        input_tokens_details=SimpleNamespace(cached_tokens=4),
        output_tokens_details=SimpleNamespace(reasoning_tokens=2),
    )

    normalized = normalize_usage(usage)

    assert normalized == TokenUsage(
        input_tokens=11,
        output_tokens=5,
        total_tokens=16,
        cached_input_tokens=4,
        reasoning_output_tokens=2,
        details_complete=True,
    )


def test_normalize_usage_from_chat_completions_shape():
    usage = SimpleNamespace(
        prompt_tokens=9,
        completion_tokens=3,
        total_tokens=12,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=2),
    )

    normalized = normalize_usage(usage)

    assert normalized == TokenUsage(
        input_tokens=9,
        output_tokens=3,
        total_tokens=12,
        cached_input_tokens=1,
        reasoning_output_tokens=2,
        details_complete=True,
    )


def test_add_usage_marks_detail_completeness_false_when_mixed():
    left = TokenUsage(
        input_tokens=10,
        output_tokens=1,
        total_tokens=11,
        cached_input_tokens=3,
        reasoning_output_tokens=1,
        details_complete=True,
    )
    right = TokenUsage(input_tokens=5, output_tokens=2, total_tokens=7, details_complete=False)

    combined = add_usage(left, right)

    assert combined.total_tokens == 18
    assert combined.cached_input_tokens == 3
    assert combined.reasoning_output_tokens == 1
    assert combined.details_complete is False


@pytest.mark.asyncio
async def test_usage_tracking_wrapper_records_non_stream_usage():
    from agentscope.model import ChatResponse
    from agentscope.model._model_usage import ChatUsage

    class FakeModel:
        model_name = "demo"
        stream = False

        async def __call__(self, messages, **kwargs):
            _ = (messages, kwargs)
            return ChatResponse(
                content=[],
                usage=ChatUsage(
                    input_tokens=7,
                    output_tokens=3,
                    time=0.1,
                    metadata=SimpleNamespace(
                        input_tokens_details=SimpleNamespace(cached_tokens=2),
                        output_tokens_details=SimpleNamespace(reasoning_tokens=1),
                    ),
                ),
            )

    recorder = RunRecorder()
    wrapper = UsageTrackingWrapper(FakeModel())

    with runtime_scope(recorder=recorder):
        await recorder.start_run()
        await recorder.start_iteration(1)
        await recorder.start_step("dev_agent")
        with runtime_scope(iteration=1, step="dev_agent"):
            await wrapper(messages=[])
        await recorder.finish_step("dev_agent")
        await recorder.finish_iteration(action="call_dev")
        result = await recorder.finish_run(status="completed")

    assert result.token_usage.total_tokens == 10
    assert result.iteration_token_usage.total_tokens == 10
    assert result.token_usage.cached_input_tokens == 2
    assert result.token_usage.reasoning_output_tokens == 1


@pytest.mark.asyncio
async def test_usage_tracking_wrapper_records_stream_usage_once():
    from agentscope.model import ChatResponse
    from agentscope.model._model_usage import ChatUsage

    class FakeModel:
        model_name = "demo"
        stream = True

        async def __call__(self, messages, **kwargs):
            _ = (messages, kwargs)

            async def _gen():
                yield ChatResponse(content=[])
                yield ChatResponse(
                    content=[],
                    usage=ChatUsage(
                        input_tokens=4,
                        output_tokens=2,
                        time=0.1,
                    ),
                )

            return _gen()

    recorder = RunRecorder()
    wrapper = UsageTrackingWrapper(FakeModel())

    with runtime_scope(recorder=recorder):
        await recorder.start_run()
        await recorder.start_iteration(1)
        await recorder.start_step("dev_agent")
        with runtime_scope(iteration=1, step="dev_agent"):
            stream = await wrapper(messages=[])
            async for _chunk in stream:
                pass
        await recorder.finish_step("dev_agent")
        await recorder.finish_iteration(action="call_dev")
        result = await recorder.finish_run(status="completed")

    assert result.token_usage.total_tokens == 6
    assert result.iteration_token_usage.total_tokens == 6


def test_probe_scope_usage_only_affects_run_total():
    recorder = RunRecorder()

    with runtime_scope(recorder=recorder, phase="probe"):
        recorder.record_usage(TokenUsage(input_tokens=2, output_tokens=1, total_tokens=3))

    result = recorder.build_result(status="completed")
    assert result.token_usage.total_tokens == 3
    assert result.iteration_token_usage.total_tokens == 0
