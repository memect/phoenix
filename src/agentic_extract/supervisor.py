"""Supervisor decision helpers extracted from the legacy loop module."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

from agentscope.message import Msg

from .model_factory import parse_model_spec
from .state import SupervisorDecision, VALID_ACTIONS
from .usage import normalize_usage

logger = logging.getLogger(__name__)

RETRY_PROMPT = (
    "你的上一条回复中未找到有效的 JSON 决策。"
    "请在回复中包含如下格式的一行 JSON（独占一行）：\n"
    '{"action": "call_dev|call_business|evaluate|done", '
    '"reasoning": "决策理由", "task": "给 agent 的具体指令"}'
)

STRUCTURED_RETRY_PROMPT = (
    "你的上一条回复未能生成有效的结构化决策。"
    "请确保 action 字段为 call_business、call_dev、evaluate、done 之一，"
    "并填写 reasoning（决策理由）和 task（给 agent 的具体指令）。"
)

MAX_DECISION_RETRIES = 2
MAX_NETWORK_RETRIES = 3
STRUCTURED_OUTPUT_TOOL_NAME = "generate_response"
_MODEL_SPEC_FALLBACK_ERROR_HINTS = (
    "provider list",
    "llm provider",
    "provider not provided",
    "unsupported provider",
    "unknown provider",
    "not mapped yet",
)


@dataclass
class ConnectivityCheckResult:
    ok: bool
    model: str
    latency_s: float
    error: str | None = None
    usage: object | None = None


@dataclass
class StructuredOutputProbeResult:
    supported: bool
    usage: object | None = None
    error: str | None = None


def _probe_model_candidates(model: str) -> list[str]:
    candidates = [model]
    if "/" not in model:
        provider, model_name = parse_model_spec(model)
        candidates.append(f"{provider}/{model_name}")
    return list(dict.fromkeys(candidates))


def _should_retry_with_probe_fallback(model: str, error: Exception) -> bool:
    if "/" in model:
        return False
    error_text = str(error).lower()
    return any(hint in error_text for hint in _MODEL_SPEC_FALLBACK_ERROR_HINTS)


def _format_probe_error_history(errors: list[tuple[str, str]]) -> str | None:
    if not errors:
        return None
    if len(errors) == 1:
        return errors[0][1]
    return "; ".join(f"{attempt_model}: {message}" for attempt_model, message in errors)


def validate_api_connectivity(
    model: str,
    api_base: str,
    api_key: str,
    timeout: float = 30.0,
) -> ConnectivityCheckResult:
    """Run a minimal sync API check via LiteLLM."""
    import litellm

    start = time.time()
    errors: list[tuple[str, str]] = []
    attempt_models = _probe_model_candidates(model)

    for index, attempt_model in enumerate(attempt_models):
        try:
            response = litellm.completion(
                model=attempt_model,
                messages=[{"role": "user", "content": "ping"}],
                api_base=api_base,
                api_key=api_key,
                max_tokens=1,
                timeout=timeout,
            )
            if attempt_model != model:
                logger.info(
                    "API 连通性探测从裸模型名 %s 回退到 %s 成功",
                    model,
                    attempt_model,
                )
            return ConnectivityCheckResult(
                ok=True,
                model=model,
                latency_s=round(time.time() - start, 2),
                usage=normalize_usage(response),
            )
        except Exception as exc:
            errors.append((attempt_model, str(exc)))
            has_fallback = index + 1 < len(attempt_models)
            if has_fallback and _should_retry_with_probe_fallback(model, exc):
                logger.info(
                    "API 连通性探测遇到模型规格兼容问题，尝试从 %s 回退到 %s: %s",
                    attempt_model,
                    attempt_models[index + 1],
                    exc,
                )
                continue
            break

    return ConnectivityCheckResult(
        ok=False,
        model=model,
        latency_s=round(time.time() - start, 2),
        error=_format_probe_error_history(errors),
    )


def try_parse_decision(text: str) -> SupervisorDecision | None:
    """Try to parse a decision payload from plain JSON text."""
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or "action" not in data:
            return None
        action = data["action"]
        if action not in VALID_ACTIONS:
            for valid in VALID_ACTIONS:
                if str(action).lower() == valid.lower():
                    action = valid
                    break
        if action not in VALID_ACTIONS:
            return None
        return SupervisorDecision(
            action=action,
            reasoning=data.get("reasoning", ""),
            task=data.get("task", ""),
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def parse_supervisor_decision(response_text: str | None) -> SupervisorDecision | None:
    """Parse decision JSON from the supervisor text response."""
    if not response_text:
        return None

    text = response_text.strip()

    for line in reversed(text.split("\n")):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            result = try_parse_decision(line)
            if result:
                return result

    for match in re.finditer(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL):
        result = try_parse_decision(match.group(1).strip())
        if result:
            return result

    for match in reversed(list(re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL))):
        result = try_parse_decision(match.group(0))
        if result:
            return result

    return None


def decision_from_structured(response_msg) -> SupervisorDecision | None:
    """Extract a decision from structured output metadata."""
    metadata = getattr(response_msg, "metadata", None)
    if not metadata or not isinstance(metadata, dict):
        return None
    action = metadata.get("action")
    if not action or action not in VALID_ACTIONS:
        return None
    try:
        return SupervisorDecision(
            action=action,
            reasoning=metadata.get("reasoning", ""),
            task=metadata.get("task", ""),
        )
    except (ValueError, TypeError):
        return None


def _structured_output_tool_schema() -> dict:
    return {
        "type": "function",
        "function": {
            "name": STRUCTURED_OUTPUT_TOOL_NAME,
            "description": "Generate the supervisor structured decision.",
            "parameters": SupervisorDecision.model_json_schema(),
        },
    }


def _get_response_field(value, field: str, default=None):
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def _response_has_structured_tool_call(response) -> bool:
    choices = _get_response_field(response, "choices", []) or []
    if not choices:
        return False

    message = _get_response_field(choices[0], "message")
    tool_calls = _get_response_field(message, "tool_calls", []) or []
    for tool_call in tool_calls:
        function = _get_response_field(tool_call, "function", {}) or {}
        if _get_response_field(function, "name") == STRUCTURED_OUTPUT_TOOL_NAME:
            return True
    return False


async def probe_structured_output(model: str, api_base: str, api_key: str) -> StructuredOutputProbeResult:
    """Probe whether the model supports AgentScope structured output.

    AgentScope implements ``structured_model`` by registering a temporary
    ``generate_response`` tool and forcing ``tool_choice="required"``. Testing
    only JSON response_format can produce false positives for models such as
    deepseek-reasoner, which accept JSON mode but reject tool_choice.
    """
    import litellm

    errors: list[tuple[str, str]] = []
    attempt_models = _probe_model_candidates(model)
    probe_messages = [
        {
            "role": "user",
            "content": (
                "Return a valid JSON object. "
                "The response must be json and contain an `ok` field."
            ),
        }
    ]

    for index, attempt_model in enumerate(attempt_models):
        try:
            response = await litellm.acompletion(
                model=attempt_model,
                messages=probe_messages,
                api_base=api_base,
                api_key=api_key,
                max_tokens=128,
                timeout=10.0,
                tools=[_structured_output_tool_schema()],
                tool_choice="required",
            )
            if not _response_has_structured_tool_call(response):
                raise RuntimeError(
                    "tool_choice probe completed, but response did not include "
                    f"a {STRUCTURED_OUTPUT_TOOL_NAME} tool call"
                )
            if attempt_model != model:
                logger.info(
                    "structured output 探测从裸模型名 %s 回退到 %s 成功",
                    model,
                    attempt_model,
                )
            return StructuredOutputProbeResult(
                supported=True,
                usage=normalize_usage(response),
            )
        except Exception as exc:
            errors.append((attempt_model, str(exc)))
            has_fallback = index + 1 < len(attempt_models)
            if has_fallback and _should_retry_with_probe_fallback(model, exc):
                logger.info(
                    "structured output 探测遇到模型规格兼容问题，尝试从 %s 回退到 %s: %s",
                    attempt_model,
                    attempt_models[index + 1],
                    exc,
                )
                continue
            break

    error_text = _format_probe_error_history(errors)
    logger.info("structured output 探测失败: %s", error_text)
    return StructuredOutputProbeResult(
        supported=False,
        error=error_text,
    )


async def get_supervisor_decision_inner(
    supervisor,
    msg: Msg,
    use_structured: bool,
) -> SupervisorDecision:
    """Get a supervisor decision, including structured/text retries."""
    if use_structured:
        response = await supervisor(msg, structured_model=SupervisorDecision)
        decision = decision_from_structured(response)
        if decision:
            return decision

        text = response.get_text_content() or ""
        decision = parse_supervisor_decision(text)
        if decision:
            logger.info("structured output metadata 无效，文本解析成功")
            return decision

        for attempt in range(1, MAX_DECISION_RETRIES + 1):
            logger.warning("structured 决策解析失败，重试 %d/%d", attempt, MAX_DECISION_RETRIES)
            retry_msg = Msg(name="user", content=STRUCTURED_RETRY_PROMPT, role="user")
            response = await supervisor(retry_msg, structured_model=SupervisorDecision)
            decision = decision_from_structured(response)
            if decision:
                return decision
            text = response.get_text_content() or ""
            decision = parse_supervisor_decision(text)
            if decision:
                return decision

        raise RuntimeError(
            f"structured output 决策解析重试 {MAX_DECISION_RETRIES} 次后仍失败"
        )

    response = await supervisor(msg)
    text = response.get_text_content() or ""
    decision = parse_supervisor_decision(text)
    if decision:
        return decision

    for attempt in range(1, MAX_DECISION_RETRIES + 1):
        logger.warning("supervisor 决策解析失败，重试 %d/%d", attempt, MAX_DECISION_RETRIES)
        retry_msg = Msg(name="user", content=RETRY_PROMPT, role="user")
        response = await supervisor(retry_msg)
        text = response.get_text_content() or ""
        decision = parse_supervisor_decision(text)
        if decision:
            return decision

    logger.warning("supervisor 决策解析重试 %d 次后仍失败，回退为 call_dev", MAX_DECISION_RETRIES)
    return SupervisorDecision(
        action="call_dev",
        reasoning="supervisor 回复无法解析（重试后仍失败）",
        task=text[:200] if text else "",
    )


async def get_supervisor_decision(
    supervisor,
    msg: Msg,
    use_structured: bool,
) -> SupervisorDecision:
    """Get a supervisor decision with network retry handling."""
    last_error: Exception | None = None

    for attempt in range(MAX_NETWORK_RETRIES):
        try:
            if attempt == 0:
                current_msg = msg
            else:
                error_text = f"上次调用异常: {last_error}"
                await supervisor.observe(Msg(name="system", content=error_text, role="system"))
                current_msg = Msg(
                    name="user",
                    content="上次调用因异常中断，请基于当前上下文重新做出决策。",
                    role="user",
                )
            return await get_supervisor_decision_inner(
                supervisor,
                current_msg,
                use_structured,
            )
        except Exception as exc:
            last_error = exc
            if attempt < MAX_NETWORK_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(
                    "supervisor 调用失败 (%d/%d): %s，%ds 后重试",
                    attempt + 1,
                    MAX_NETWORK_RETRIES,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("supervisor 调用失败 %d 次，放弃: %s", MAX_NETWORK_RETRIES, exc)
                raise
