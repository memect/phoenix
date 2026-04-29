"""Usage normalization and token accounting helpers."""

from __future__ import annotations

from typing import Any

from .types import TokenUsage


def _get_value(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_detail_values(usage: Any) -> tuple[int | None, int | None, bool]:
    input_details = (
        _get_value(usage, "input_tokens_details")
        or _get_value(usage, "prompt_tokens_details")
    )
    output_details = (
        _get_value(usage, "output_tokens_details")
        or _get_value(usage, "completion_tokens_details")
    )

    cached_tokens = _as_int(_get_value(input_details, "cached_tokens"))
    reasoning_tokens = _as_int(_get_value(output_details, "reasoning_tokens"))

    details_complete = bool(input_details is not None or output_details is not None)
    return cached_tokens, reasoning_tokens, details_complete


def normalize_usage(usage_or_response: Any) -> TokenUsage | None:
    """Normalize known provider usage payloads into TokenUsage.

    Supports:
    - AgentScope ChatUsage
    - OpenAI Responses usage
    - OpenAI Chat Completions usage
    - LiteLLM response/usage objects
    """
    if usage_or_response is None:
        return None

    usage = _get_value(usage_or_response, "usage") or usage_or_response

    input_tokens = _as_int(_get_value(usage, "input_tokens"))
    output_tokens = _as_int(_get_value(usage, "output_tokens"))
    total_tokens = _as_int(_get_value(usage, "total_tokens"))

    if input_tokens is None and output_tokens is None:
        prompt_tokens = _as_int(_get_value(usage, "prompt_tokens"))
        completion_tokens = _as_int(_get_value(usage, "completion_tokens"))
        input_tokens = prompt_tokens
        output_tokens = completion_tokens
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

    metadata = _get_value(usage, "metadata")
    cached_tokens, reasoning_tokens, details_complete = _extract_detail_values(usage)

    if metadata is not None:
        meta_cached, meta_reasoning, meta_complete = _extract_detail_values(metadata)
        if cached_tokens is None:
            cached_tokens = meta_cached
        if reasoning_tokens is None:
            reasoning_tokens = meta_reasoning
        details_complete = details_complete or meta_complete

    if input_tokens is None:
        return None

    if output_tokens is None:
        output_tokens = 0
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_tokens,
        reasoning_output_tokens=reasoning_tokens,
        details_complete=details_complete,
    )


def clone_usage(usage: TokenUsage) -> TokenUsage:
    """Create a detached copy safe for event payloads."""
    return usage.model_copy(deep=True)


def add_usage(left: TokenUsage, right: TokenUsage | None) -> TokenUsage:
    """Add two TokenUsage values, preserving detail completeness semantics."""
    if right is None:
        return clone_usage(left)

    contributors = [usage for usage in (left, right) if usage.total_tokens > 0]
    details_complete = all(usage.details_complete for usage in contributors) if contributors else False

    def _sum_optional(a: int | None, b: int | None) -> int | None:
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
        cached_input_tokens=_sum_optional(left.cached_input_tokens, right.cached_input_tokens),
        reasoning_output_tokens=_sum_optional(
            left.reasoning_output_tokens,
            right.reasoning_output_tokens,
        ),
        details_complete=details_complete,
    )

