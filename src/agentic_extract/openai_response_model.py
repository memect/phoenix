# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches
"""OpenAI Response API Chat model (从 AgentScope fork 移植)"""
import json
from datetime import datetime
from typing import (
    Any,
    List,
    AsyncGenerator,
    Literal,
    Type,
)

from pydantic import BaseModel

from agentscope.model import ChatResponse
from agentscope.model._model_base import ChatModelBase
from agentscope.model._model_usage import ChatUsage
from agentscope._logging import logger
from agentscope._utils._common import _json_loads_with_repair
from agentscope.message import (
    ToolUseBlock,
    TextBlock,
    ThinkingBlock,
)
from agentscope.tracing import trace_llm
from agentscope.types import JSONSerializableObject


class OpenAIResponseModel(ChatModelBase):
    """Chat model using the OpenAI Responses API
    (``client.responses.create``).
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        stream: bool = True,
        reasoning_effort: Literal["minimal", "low", "medium", "high"]
        | None = None,
        reasoning_summary: Literal["auto", "concise", "detailed"]
        | None = None,
        organization: str | None = None,
        stream_tool_parsing: bool = True,
        client_kwargs: dict[str, JSONSerializableObject] | None = None,
        generate_kwargs: dict[str, JSONSerializableObject] | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            logger.warning(
                "Unknown keyword arguments: %s. These will be ignored.",
                list(kwargs.keys()),
            )

        super().__init__(model_name, stream)

        import openai

        self.client = openai.AsyncClient(
            api_key=api_key,
            organization=organization,
            **(client_kwargs or {}),
        )

        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self.stream_tool_parsing = stream_tool_parsing
        self.generate_kwargs = generate_kwargs or {}

    @trace_llm
    async def __call__(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | None = None,
        structured_model: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        if not isinstance(messages, list):
            raise ValueError(
                "OpenAI Response API `messages` field expected type `list`, "
                f"got `{type(messages)}` instead.",
            )

        api_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "input": messages,
            "stream": self.stream,
            **self.generate_kwargs,
            **kwargs,
        }

        if self.reasoning_effort and "reasoning" not in api_kwargs:
            reasoning_cfg: dict[str, str | None] = {
                "effort": self.reasoning_effort,
            }
            if self.reasoning_summary:
                reasoning_cfg["summary"] = self.reasoning_summary
            api_kwargs["reasoning"] = reasoning_cfg

        if structured_model:
            if tools or tool_choice:
                logger.warning(
                    "structured_model is provided. Both 'tools' and "
                    "'tool_choice' parameters will be overridden and "
                    "ignored.",
                )
            api_kwargs.pop("tools", None)
            api_kwargs.pop("tool_choice", None)
            api_kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": structured_model.__name__,
                    "schema": structured_model.model_json_schema(),
                    "strict": True,
                },
            }
        else:
            if tools:
                api_kwargs["tools"] = self._format_tools(tools)
            if tool_choice:
                self._validate_tool_choice(tool_choice, tools)
                api_kwargs["tool_choice"] = self._format_tool_choice(
                    tool_choice,
                )

        start_datetime = datetime.now()
        response = await self.client.responses.create(**api_kwargs)

        if self.stream:
            return self._parse_stream_response(
                start_datetime, response, structured_model,
            )

        return self._parse_response(
            start_datetime, response, structured_model,
        )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def _parse_stream_response(
        self,
        start_datetime: datetime,
        response: Any,
        structured_model: Type[BaseModel] | None = None,
    ) -> AsyncGenerator[ChatResponse, None]:
        usage: ChatUsage | None = None
        response_id: str | None = None
        text = ""
        thinking = ""
        tool_calls: dict[str, dict[str, Any]] = {}
        last_input_objs: dict[str, Any] = {}
        metadata: dict | None = None
        last_contents = None

        async for event in response:
            event_type = event.type

            if response_id is None:
                resp_obj = getattr(event, "response", None)
                if resp_obj is not None:
                    response_id = getattr(resp_obj, "id", None)

            if event_type == "response.reasoning_summary_text.delta":
                thinking += event.delta
            elif event_type == "response.output_text.delta":
                text += event.delta
            elif event_type == "response.output_item.added":
                item = event.item
                if getattr(item, "type", None) == "function_call":
                    call_id = getattr(item, "call_id", None) or getattr(
                        item, "id", "",
                    )
                    tool_calls[item.id] = {
                        "type": "tool_use",
                        "id": call_id,
                        "name": getattr(item, "name", ""),
                        "input": "",
                    }
            elif event_type == "response.function_call_arguments.delta":
                item_id = event.item_id
                if item_id in tool_calls:
                    tool_calls[item_id]["input"] += event.delta
            elif event_type == "response.completed":
                resp = event.response
                if response_id is None:
                    response_id = getattr(resp, "id", None)
                if resp.usage:
                    usage = ChatUsage(
                        input_tokens=resp.usage.input_tokens,
                        output_tokens=resp.usage.output_tokens,
                        time=(datetime.now() - start_datetime).total_seconds(),
                        metadata=resp.usage,
                    )

            contents = self._build_content_blocks(
                thinking, text, tool_calls, last_input_objs,
            )

            if structured_model and text:
                metadata = _json_loads_with_repair(text)

            if contents:
                chat_resp_kwargs: dict[str, Any] = {
                    "content": contents,
                    "usage": usage,
                    "metadata": metadata,
                }
                if response_id:
                    chat_resp_kwargs["id"] = response_id
                yield ChatResponse(**chat_resp_kwargs)
                last_contents = [dict(b) for b in contents]

        if not self.stream_tool_parsing and tool_calls and last_contents:
            for block in last_contents:
                if block.get("type") == "tool_use":
                    block["input"] = _json_loads_with_repair(
                        str(block.get("raw_input") or "{}"),
                    )
            final_kwargs: dict[str, Any] = {
                "content": last_contents,
                "usage": usage,
                "metadata": metadata,
            }
            if response_id:
                final_kwargs["id"] = response_id
            yield ChatResponse(**final_kwargs)

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        start_datetime: datetime,
        response: Any,
        structured_model: Type[BaseModel] | None = None,
    ) -> ChatResponse:
        content_blocks: List[TextBlock | ToolUseBlock | ThinkingBlock] = []
        metadata: dict | None = None

        for item in response.output:
            item_type = getattr(item, "type", None)

            if item_type == "reasoning":
                for summary in getattr(item, "summary", []):
                    summary_text = getattr(summary, "text", "")
                    if summary_text:
                        content_blocks.append(
                            ThinkingBlock(type="thinking", thinking=summary_text),
                        )
            elif item_type == "message":
                for part in getattr(item, "content", []):
                    if getattr(part, "type", None) == "output_text":
                        content_blocks.append(
                            TextBlock(type="text", text=part.text),
                        )
                        if structured_model:
                            metadata = _json_loads_with_repair(part.text)
            elif item_type == "function_call":
                call_id = getattr(item, "call_id", None) or getattr(
                    item, "id", "",
                )
                content_blocks.append(
                    ToolUseBlock(
                        type="tool_use",
                        id=call_id,
                        name=item.name,
                        input=_json_loads_with_repair(
                            getattr(item, "arguments", "") or "{}",
                        ),
                    ),
                )

        usage = None
        if response.usage:
            usage = ChatUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                time=(datetime.now() - start_datetime).total_seconds(),
                metadata=response.usage,
            )

        resp_kwargs: dict[str, Any] = {
            "content": content_blocks,
            "usage": usage,
            "metadata": metadata,
        }
        response_id = getattr(response, "id", None)
        if response_id:
            resp_kwargs["id"] = response_id

        return ChatResponse(**resp_kwargs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_content_blocks(
        self,
        thinking: str,
        text: str,
        tool_calls: dict[str, dict[str, Any]],
        last_input_objs: dict[str, Any],
    ) -> List[TextBlock | ToolUseBlock | ThinkingBlock]:
        contents: List[TextBlock | ToolUseBlock | ThinkingBlock] = []

        if thinking:
            contents.append(ThinkingBlock(type="thinking", thinking=thinking))
        if text:
            contents.append(TextBlock(type="text", text=text))

        for tc in tool_calls.values():
            input_str = tc["input"]
            if self.stream_tool_parsing:
                repaired = _json_loads_with_repair(input_str or "{}")
                last = last_input_objs.get(tc["id"], {})
                if len(json.dumps(last)) > len(json.dumps(repaired)):
                    repaired = last
                last_input_objs[tc["id"]] = repaired
            else:
                repaired = {}

            contents.append(
                ToolUseBlock(
                    type="tool_use",
                    id=tc["id"],
                    name=tc["name"],
                    input=repaired,
                    raw_input=input_str,
                ),
            )

        return contents

    @staticmethod
    def _format_tools(
        schemas: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [{"type": "function", **tool["function"]} for tool in schemas]

    @staticmethod
    def _format_tool_choice(
        tool_choice: Literal["auto", "none", "required"] | str | None,
    ) -> str | dict | None:
        if tool_choice is None:
            return None
        if tool_choice in ("auto", "none", "required"):
            return tool_choice
        return {"type": "function", "name": tool_choice}
