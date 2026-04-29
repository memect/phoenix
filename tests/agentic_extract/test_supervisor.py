import sys
from types import ModuleType, SimpleNamespace

import pytest
from agentscope.message import Msg

from agentic_extract.supervisor import (
    decision_from_structured,
    get_supervisor_decision,
    get_supervisor_decision_inner,
    parse_supervisor_decision,
    probe_structured_output,
    try_parse_decision,
    validate_api_connectivity,
)


def test_try_parse_decision_accepts_valid_json():
    decision = try_parse_decision(
        '{"action":"call_dev","reasoning":"because","task":"do it"}'
    )

    assert decision is not None
    assert decision.action == "call_dev"
    assert decision.reasoning == "because"


def test_parse_supervisor_decision_reads_json_code_block():
    text = """
before
```json
{"action":"evaluate","reasoning":"need metrics","task":"run eval"}
```
after
"""

    decision = parse_supervisor_decision(text)

    assert decision is not None
    assert decision.action == "evaluate"
    assert decision.task == "run eval"


def test_decision_from_structured_reads_metadata():
    response = SimpleNamespace(metadata={"action": "done", "reasoning": "ok", "task": ""})

    decision = decision_from_structured(response)

    assert decision is not None
    assert decision.action == "done"


def test_validate_api_connectivity_retries_bare_model_with_provider_prefix(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "GLM-5":
            raise RuntimeError("Provider List: https://docs.litellm.ai/docs/providers")
        return SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=6,
                completion_tokens=1,
                total_tokens=7,
            )
        )

    fake_litellm = ModuleType("litellm")
    fake_litellm.completion = fake_completion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = validate_api_connectivity(
        model="GLM-5",
        api_base="http://example.com",
        api_key="secret",
    )

    assert result.ok is True
    assert result.model == "GLM-5"
    assert result.usage is not None
    assert result.usage.total_tokens == 7
    assert calls == ["GLM-5", "openai/GLM-5"]


@pytest.mark.asyncio
async def test_probe_structured_output_retries_bare_model_with_provider_prefix(monkeypatch):
    calls = []
    captured_messages = []
    captured_tools = []
    captured_tool_choices = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs["model"])
        captured_messages.append(kwargs["messages"])
        captured_tools.append(kwargs.get("tools"))
        captured_tool_choices.append(kwargs.get("tool_choice"))
        if kwargs["model"] == "GLM-5":
            raise RuntimeError("LLM Provider NOT provided")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(name="generate_response")
                            )
                        ]
                    )
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=6,
                completion_tokens=1,
                total_tokens=7,
            )
        )

    fake_litellm = ModuleType("litellm")
    fake_litellm.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = await probe_structured_output(
        model="GLM-5",
        api_base="http://example.com",
        api_key="secret",
    )

    assert result.supported is True
    assert result.usage is not None
    assert result.usage.total_tokens == 7
    assert calls == ["GLM-5", "openai/GLM-5"]
    assert any("json" in message[0]["content"].lower() for message in captured_messages)
    assert captured_tool_choices == ["required", "required"]
    assert captured_tools[-1][0]["function"]["name"] == "generate_response"


@pytest.mark.asyncio
async def test_probe_structured_output_rejects_models_without_tool_choice(monkeypatch):
    async def fake_acompletion(**kwargs):
        assert kwargs["tool_choice"] == "required"
        raise RuntimeError("deepseek-reasoner does not support this tool_choice")

    fake_litellm = ModuleType("litellm")
    fake_litellm.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = await probe_structured_output(
        model="deepseek/deepseek-reasoner",
        api_base="http://example.com",
        api_key="secret",
    )

    assert result.supported is False
    assert "tool_choice" in result.error


@pytest.mark.asyncio
async def test_probe_structured_output_requires_actual_tool_call(monkeypatch):
    async def fake_acompletion(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[]))])

    fake_litellm = ModuleType("litellm")
    fake_litellm.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    result = await probe_structured_output(
        model="openai/test-model",
        api_base="http://example.com",
        api_key="secret",
    )

    assert result.supported is False
    assert "did not include" in result.error


@pytest.mark.asyncio
async def test_get_supervisor_decision_inner_retries_text_mode():
    class FakeResponse:
        def __init__(self, text):
            self._text = text

        def get_text_content(self):
            return self._text

    responses = [
        FakeResponse("not json"),
        FakeResponse('{"action":"call_business","reasoning":"need domain input","task":"ask business"}'),
    ]

    async def fake_supervisor(_msg, structured_model=None):
        _ = structured_model
        return responses.pop(0)

    decision = await get_supervisor_decision_inner(
        fake_supervisor,
        Msg(name="user", content="go", role="user"),
        use_structured=False,
    )

    assert decision.action == "call_business"


@pytest.mark.asyncio
async def test_get_supervisor_decision_handles_network_retry():
    class FakeSupervisor:
        def __init__(self):
            self.calls = 0
            self.observed = []

        async def __call__(self, _msg, structured_model=None):
            _ = structured_model
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient")
            return SimpleNamespace(
                metadata={},
                get_text_content=lambda: '{"action":"evaluate","reasoning":"retry ok","task":"run eval"}',
            )

        async def observe(self, msg):
            self.observed.append(msg.content)

    supervisor = FakeSupervisor()

    decision = await get_supervisor_decision(
        supervisor,
        Msg(name="user", content="go", role="user"),
        use_structured=False,
    )

    assert decision.action == "evaluate"
    assert supervisor.observed
