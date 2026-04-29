"""
模型工厂：根据模型前缀创建对应的模型和 formatter

支持的前缀：
- gemini/xxx    → GeminiChatModel + GeminiMultiAgentFormatter
- openai/xxx    → OpenAIChatModel + OpenAIMultiAgentFormatter
- deepseek/xxx  → OpenAIChatModel + DeepSeekMultiAgentFormatter
- anthropic/xxx → AnthropicChatModel + AnthropicMultiAgentFormatter
- 无前缀默认使用 OpenAI
"""

import logging
import os
from urllib.parse import urlparse
from typing import Tuple, Any

import httpx
from agentscope.model import ChatModelBase, OpenAIChatModel, GeminiChatModel, AnthropicChatModel
from agentscope.formatter import (
    DeepSeekMultiAgentFormatter,
    GeminiMultiAgentFormatter,
    OpenAIMultiAgentFormatter,
    AnthropicMultiAgentFormatter,
)
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

_DEEPSEEK_API_HOST_HINTS = (
    "deepseek.com",
    "deepseek.cn",
)


def _is_deepseek_compatible(model_spec: str, api_base: str) -> bool:
    """Return True when the request should preserve DeepSeek reasoning state.

    DeepSeek thinking mode requires passing prior assistant reasoning back
    through the dedicated `reasoning_content` field after tool calls. When we
    detect a DeepSeek-compatible chat.completions endpoint, prefer the native
    formatter instead of the generic OpenAI formatter so thinking blocks are not
    dropped between turns.
    """
    model_text = model_spec.lower()
    if model_text.startswith("deepseek/") or "deepseek" in model_text:
        return True

    parsed = urlparse(api_base)
    host = (parsed.netloc or parsed.path).lower()
    return any(hint in host for hint in _DEEPSEEK_API_HOST_HINTS)


class UsageTrackingWrapper(ChatModelBase):
    """Track provider usage and forward it into the active runtime recorder."""

    def __init__(self, model: Any) -> None:
        super().__init__(model_name=model.model_name, stream=model.stream)
        self._model = model

    async def __call__(
        self,
        messages: list[dict],
        **kwargs: Any,
    ) -> Any:
        from .runtime import record_current_usage
        from .usage import normalize_usage

        response = await self._model(messages, **kwargs)

        if self.stream:
            async def _tracked_stream():
                recorded = False
                async for chunk in response:
                    if not recorded:
                        usage = normalize_usage(chunk)
                        if usage is not None:
                            record_current_usage(usage)
                            recorded = True
                    yield chunk

            return _tracked_stream()

        usage = normalize_usage(response)
        if usage is not None:
            record_current_usage(usage)
        return response


def parse_model_spec(model_spec: str) -> Tuple[str, str]:
    """
    解析模型规格字符串

    Args:
        model_spec: 模型规格，格式为 "provider/model_name" 或 "model_name"

    Returns:
        (provider, model_name) 元组

    Examples:
        >>> parse_model_spec("gemini/gemini-2.0-flash")
        ('gemini', 'gemini-2.0-flash')
        >>> parse_model_spec("gpt-4o")
        ('openai', 'gpt-4o')
        >>> parse_model_spec("deepseek/deepseek-v4")
        ('deepseek', 'deepseek-v4')
    """
    if "/" in model_spec:
        provider, model_name = model_spec.split("/", 1)
        return provider.lower(), model_name
    else:
        # 无前缀默认为 OpenAI
        return "openai", model_spec


def create_model(
    model_spec: str,
    api_base: str,
    api_key: str,
    stream: bool = True,
    timeout: float = 300.0,
    max_retries: int = 0,
    preserve_thinking: bool = False,
    **kwargs: Any,
) -> Tuple[Any, Any]:
    """
    根据模型规格创建模型和对应的 formatter

    Args:
        model_spec: 模型规格，格式为 "provider/model_name" 或 "model_name"
        api_base: API 基础 URL
        api_key: API Key
        stream: 是否使用流式输出
        timeout: 超时时间（秒）
        max_retries: 最大重试次数（>0 时自动关闭 stream）
        **kwargs: 其他传递给模型的参数

    Returns:
        (model, formatter) 元组

    Raises:
        ValueError: 不支持的模型提供商
    """
    # 开启重试时强制关闭 stream
    if max_retries > 0:
        stream = False
    provider, model_name = parse_model_spec(model_spec)

    deepseek_compatible = _is_deepseek_compatible(model_spec, api_base)
    use_responses_api = False

    if provider == "gemini":
        # 创建 Gemini 模型
        # 注意：api_base 需要移除 /v1 后缀，因为 genai SDK 会自动添加 /v1beta
        gemini_base_url = _get_gemini_base_url(api_base)

        # 配置代理 - genai SDK 异步请求默认用 aiohttp，但 aiohttp 不支持构造函数传代理
        # 解决方案：传入配置好代理的 httpxAsyncClient，强制 SDK 用 httpx 做异步请求
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

        # 注意：HttpOptions.timeout 单位是毫秒，而 timeout 参数单位是秒
        timeout_ms = int(timeout * 1000)

        http_options_kwargs: dict = {
            "base_url": gemini_base_url,
            "timeout": timeout_ms,
        }

        if proxy:
            # 同步客户端通过 clientArgs 传递代理（httpx 的 timeout 单位是秒）
            http_options_kwargs["clientArgs"] = {"proxy": proxy, "timeout": timeout}
            # 异步客户端直接传入配置好代理的 httpx.AsyncClient 实例（timeout 单位是秒）
            http_options_kwargs["httpxAsyncClient"] = httpx.AsyncClient(
                proxy=proxy, timeout=timeout
            )

        model = GeminiChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=stream,
            client_kwargs={
                "http_options": genai_types.HttpOptions(**http_options_kwargs),
            },
            **kwargs,
        )
        formatter = GeminiMultiAgentFormatter()

    elif provider in {"openai", "deepseek"}:
        # 创建 OpenAI 模型
        use_responses_api = kwargs.pop("use_responses_api", False)

        if use_responses_api:
            from .openai_response_model import OpenAIResponseModel
            from .openai_response_formatter import OpenAIResponseMultiAgentFormatter

            # 提取 reasoning_effort 传给 ResponseModel
            reasoning_effort = kwargs.pop("reasoning_effort", None)

            model = OpenAIResponseModel(
                model_name=model_name,
                api_key=api_key,
                stream=stream,
                reasoning_effort=reasoning_effort,
                client_kwargs={
                    "base_url": api_base,
                    "timeout": timeout,
                },
                **kwargs,
            )
            formatter = OpenAIResponseMultiAgentFormatter()
        else:
            model = OpenAIChatModel(
                model_name=model_name,
                api_key=api_key,
                stream=stream,
                client_kwargs={
                    "base_url": api_base,
                    "timeout": timeout,
                },
                **kwargs,
            )
            if deepseek_compatible:
                formatter = DeepSeekMultiAgentFormatter()
            else:
                formatter = OpenAIMultiAgentFormatter()

    elif provider == "anthropic":
        # 创建 Anthropic 模型
        model = AnthropicChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=stream,
            client_kwargs={
                "base_url": api_base,
                "timeout": timeout,
            },
            **kwargs,
        )
        formatter = AnthropicMultiAgentFormatter()

    else:
        raise ValueError(
            f"不支持的模型提供商: {provider}。"
            f"支持的提供商: gemini, openai, deepseek, anthropic"
        )

    # 在 retry 之前记录每次真实 provider 调用的 usage
    model = UsageTrackingWrapper(model)

    # 开启重试时包装 RetryModelWrapper
    if max_retries > 0:
        from .retry import RetryModelWrapper
        model = RetryModelWrapper(model, max_retries=max_retries)

    # 保留 thinking blocks（防止 formatter 丢弃导致 agent 循环）
    if preserve_thinking:
        if deepseek_compatible and not use_responses_api:
            logger.info(
                "检测到 DeepSeek 兼容 chat.completions 端点，"
                "跳过 preserve_thinking 文本降级以保留 reasoning_content。"
            )
        else:
            model = ThinkingToTextWrapper(model)

    return model, formatter


def _get_gemini_base_url(api_base: str) -> str:
    """处理 Gemini API base URL，移除 /v1 后缀"""
    return api_base.rstrip("/v1") if api_base.endswith("/v1") else api_base


class ThinkingToTextWrapper(ChatModelBase):
    """将 thinking blocks 转为 text blocks，防止 formatter 丢弃。

    某些模型（如 Claude extended thinking）返回 thinking block，
    但 OpenAIMultiAgentFormatter 不认识该类型会直接跳过，
    导致 agent 丢失轮间推理上下文陷入循环。

    此 wrapper 在模型返回后将 thinking block 转为 text block 保留。
    """

    def __init__(self, model: Any) -> None:
        super().__init__(model_name=model.model_name, stream=model.stream)
        self._model = model

    async def __call__(
        self,
        messages: list[dict],
        **kwargs: Any,
    ) -> Any:
        response = await self._model(messages, **kwargs)
        return self._convert_thinking(response)

    @staticmethod
    def _convert_thinking(response: Any) -> Any:
        """将 response.content 中的 thinking blocks 转为 text blocks。"""
        if not hasattr(response, "content") or not response.content:
            return response

        new_content = []
        for block in response.content:
            if not isinstance(block, dict):
                new_content.append(block)
                continue
            if block.get("type") == "thinking":
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    new_content.append({
                        "type": "text",
                        "text": f"<thinking>\n{thinking_text}\n</thinking>",
                    })
            else:
                new_content.append(block)

        response.content = new_content
        return response


class PlainJsonModelWrapper(ChatModelBase):
    """将 structured output 请求转为纯文本 JSON 解析的模型 wrapper。

    某些 API 代理（如 Claude via OpenAI 兼容接口）不支持 OpenAI 的
    structured output (response_format / chat.completions.parse)。
    此 wrapper 在 prompt 中添加 JSON 格式要求，并从文本响应中解析 JSON。
    """

    def __init__(self, model: Any) -> None:
        super().__init__(model_name=model.model_name, stream=False)
        self._model = model

    async def __call__(
        self,
        messages: list[dict],
        structured_model: Any = None,
        **kwargs: Any,
    ) -> Any:
        if structured_model is None:
            return await self._model(messages, **kwargs)

        # 构建 JSON schema 说明
        import json

        schema_fields = {}
        for name, field_info in structured_model.model_fields.items():
            schema_fields[name] = field_info.description or name
        json_instruction = (
            "\n\nIMPORTANT: Respond with ONLY a valid JSON object (no markdown, "
            "no code blocks, no extra text). Required fields:\n"
            + json.dumps(schema_fields, ensure_ascii=False, indent=2)
        )

        # 附加到最后一条消息
        messages = list(messages)
        if messages and isinstance(messages[-1], dict):
            last_msg = dict(messages[-1])
            content = last_msg.get("content", "")
            if isinstance(content, str):
                last_msg["content"] = content + json_instruction
            elif isinstance(content, list):
                last_msg["content"] = list(content) + [
                    {"type": "text", "text": json_instruction}
                ]
            messages[-1] = last_msg

        # 不传 structured_model，用普通文本调用
        response = await self._model(messages, **kwargs)

        # 从响应文本中解析 JSON
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        metadata = self._extract_json(text)
        if metadata is not None:
            response.metadata = metadata
        else:
            # 兜底：用原始文本填充所有字段
            field_names = list(structured_model.model_fields.keys())
            response.metadata = {name: text[:300] for name in field_names}

        return response

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取 JSON 对象。"""
        import json
        import re

        text = text.strip()

        # 尝试从 code block 中提取
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

        # 直接解析
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 尝试找到 JSON 对象
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                data = json.loads(m.group())
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        return None
