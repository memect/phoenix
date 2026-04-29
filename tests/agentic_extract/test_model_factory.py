from agentscope.formatter import DeepSeekMultiAgentFormatter, OpenAIMultiAgentFormatter

from agentic_extract import model_factory


class DummyOpenAIChatModel:
    def __init__(self, model_name, api_key, stream, client_kwargs, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.stream = stream
        self.client_kwargs = client_kwargs
        self.kwargs = kwargs


def test_create_model_uses_deepseek_formatter_for_official_endpoint(monkeypatch):
    monkeypatch.setattr(model_factory, "OpenAIChatModel", DummyOpenAIChatModel)

    model, formatter = model_factory.create_model(
        model_spec="deepseek/deepseek-v4-pro",
        api_base="https://api.deepseek.com/v1",
        api_key="secret",
    )

    assert isinstance(formatter, DeepSeekMultiAgentFormatter)
    assert isinstance(model, model_factory.UsageTrackingWrapper)
    assert model._model.client_kwargs["base_url"] == "https://api.deepseek.com/v1"


def test_create_model_preserve_thinking_skips_text_wrapper_for_deepseek(monkeypatch, caplog):
    monkeypatch.setattr(model_factory, "OpenAIChatModel", DummyOpenAIChatModel)
    caplog.set_level("INFO")

    model, formatter = model_factory.create_model(
        model_spec="deepseek/deepseek-v4-pro",
        api_base="https://api.deepseek.com/v1",
        api_key="secret",
        preserve_thinking=True,
    )

    assert isinstance(formatter, DeepSeekMultiAgentFormatter)
    assert isinstance(model, model_factory.UsageTrackingWrapper)
    assert not isinstance(model, model_factory.ThinkingToTextWrapper)
    assert "跳过 preserve_thinking 文本降级" in caplog.text


def test_create_model_keeps_openai_formatter_for_non_deepseek_model(monkeypatch):
    monkeypatch.setattr(model_factory, "OpenAIChatModel", DummyOpenAIChatModel)

    model, formatter = model_factory.create_model(
        model_spec="openai/gpt-4o-mini",
        api_base="https://api.openai.com/v1",
        api_key="secret",
        preserve_thinking=True,
    )

    assert isinstance(formatter, OpenAIMultiAgentFormatter)
    assert isinstance(model, model_factory.ThinkingToTextWrapper)
    assert isinstance(model._model, model_factory.UsageTrackingWrapper)
