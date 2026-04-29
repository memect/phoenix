# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches, too-many-nested-blocks
"""OpenAI Response API formatter (从 AgentScope fork 移植)"""
import json
from typing import Any

from agentscope.formatter._openai_formatter import (
    _to_openai_image_url,
    _to_openai_audio_data,
)
from agentscope.formatter._truncated_formatter_base import TruncatedFormatterBase
from agentscope._logging import logger
from agentscope.message import (
    Msg,
    TextBlock,
    ImageBlock,
    AudioBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from agentscope.token import TokenCounterBase


def _format_openai_response_image_block(
    image_block: ImageBlock,
) -> dict[str, Any]:
    source = image_block["source"]
    if source["type"] == "url":
        url = _to_openai_image_url(source["url"])
    elif source["type"] == "base64":
        data = source["data"]
        media_type = source["media_type"]
        url = f"data:{media_type};base64,{data}"
    else:
        raise ValueError(
            f"Unsupported image source type: {source['type']}",
        )
    return {
        "type": "input_image",
        "image_url": url,
    }


class OpenAIResponseChatFormatter(TruncatedFormatterBase):
    """OpenAI Response API formatter for chat scenario."""

    support_tools_api: bool = True
    support_multiagent: bool = True
    support_vision: bool = True
    supported_blocks: list[type] = [
        TextBlock, ImageBlock, AudioBlock, ToolUseBlock, ToolResultBlock,
    ]

    def __init__(
        self,
        promote_tool_result_images: bool = False,
        token_counter: TokenCounterBase | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(token_counter=token_counter, max_tokens=max_tokens)
        self.promote_tool_result_images = promote_tool_result_images

    async def _format(
        self,
        msgs: list[Msg],
    ) -> list[dict[str, Any]]:
        self.assert_list_of_msgs(msgs)

        messages: list[dict] = []
        i = 0
        while i < len(msgs):
            msg = msgs[i]
            content_blocks = []
            tool_calls = []

            for block in msg.get_content_blocks():
                typ = block.get("type")
                if typ == "text":
                    content_blocks.append(
                        {"type": "input_text", "text": block.get("text")},
                    )
                elif typ == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id"),
                            "type": "function",
                            "function": {
                                "name": block.get("name"),
                                "arguments": json.dumps(
                                    block.get("input", {}),
                                    ensure_ascii=False,
                                ),
                            },
                        },
                    )
                elif typ == "tool_result":
                    (
                        textual_output,
                        multimodal_data,
                    ) = self.convert_tool_result_to_string(block["output"])
                    messages.append(
                        {
                            "role": "assistant",
                            "tool_call_id": block.get("id"),
                            "content": textual_output,
                            "name": block.get("name"),
                        },
                    )
                    promoted_content: list = []
                    for url, multimodal_block in multimodal_data:
                        if (
                            multimodal_block["type"] == "image"
                            and self.promote_tool_result_images
                        ):
                            promoted_content.extend(
                                [
                                    {
                                        "type": "input_text",
                                        "text": f"\n- The image from '{url}': ",
                                    },
                                    {
                                        "type": "input_image",
                                        "image_url": _to_openai_image_url(url),
                                    },
                                ],
                            )
                    if promoted_content:
                        messages.append(
                            {
                                "role": "user",
                                "name": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": (
                                            "<system-info>The following"
                                            " are the image contents "
                                            "from the tool result of "
                                            f"'{block['name']}':"
                                        ),
                                    },
                                    *promoted_content,
                                    {"type": "input_text", "text": "</system-info>"},
                                ],
                            },
                        )
                elif typ == "image":
                    content_blocks.append(
                        _format_openai_response_image_block(block),
                    )
                elif typ == "audio":
                    if msg.role == "assistant":
                        continue
                    input_audio = _to_openai_audio_data(block["source"])
                    content_blocks.append(
                        {"type": "input_audio", "input_audio": input_audio},
                    )
                else:
                    logger.warning(
                        "Unsupported block type %s in the message, skipped.",
                        typ,
                    )

            msg_openai_response = {
                "role": msg.role,
                "name": msg.name,
                "content": content_blocks,
            }
            if tool_calls:
                msg_openai_response["tool_calls"] = tool_calls
            if msg_openai_response["content"] or msg_openai_response.get("tool_calls"):
                messages.append(msg_openai_response)
            i += 1

        return messages


class OpenAIResponseMultiAgentFormatter(TruncatedFormatterBase):
    """OpenAI Response API formatter for multi-agent conversations."""

    support_tools_api: bool = True
    support_multiagent: bool = True
    support_vision: bool = True
    supported_blocks: list[type] = [
        TextBlock, ImageBlock, AudioBlock, ToolUseBlock, ToolResultBlock,
    ]

    def __init__(
        self,
        conversation_history_prompt: str = (
            "# Conversation History\n"
            "The content between <history></history> tags contains "
            "your conversation history\n"
        ),
        promote_tool_result_images: bool = False,
        token_counter: TokenCounterBase | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(token_counter=token_counter, max_tokens=max_tokens)
        self.conversation_history_prompt = conversation_history_prompt
        self.promote_tool_result_images = promote_tool_result_images

    async def _format_system_message(self, msg: Msg) -> dict[str, Any]:
        return {
            "role": "system",
            "content": [
                {"type": "input_text", "text": block["text"]}
                for block in msg.get_content_blocks("text")
            ],
        }

    async def _format_tool_sequence(
        self, msgs: list[Msg],
    ) -> list[dict[str, Any]]:
        return await OpenAIResponseChatFormatter(
            promote_tool_result_images=self.promote_tool_result_images,
        ).format(msgs)

    async def _format_agent_message(
        self,
        msgs: list[Msg],
        is_first: bool = True,
    ) -> list[dict[str, Any]]:
        if is_first:
            conversation_history_prompt = self.conversation_history_prompt
        else:
            conversation_history_prompt = ""

        formatted_msgs: list[dict] = []
        conversation_blocks: list = []
        accumulated_text = []
        images = []
        audios = []

        for msg in msgs:
            for block in msg.get_content_blocks():
                if block["type"] == "text":
                    accumulated_text.append(f"{msg.name}: {block['text']}")
                elif block["type"] == "image":
                    images.append(_format_openai_response_image_block(block))
                elif block["type"] == "audio":
                    if msg.role == "assistant":
                        continue
                    input_audio = _to_openai_audio_data(block["source"])
                    audios.append(
                        {"type": "input_audio", "input_audio": input_audio},
                    )

        if accumulated_text:
            conversation_blocks.append(
                {"text": "\n".join(accumulated_text)},
            )

        if conversation_blocks:
            if conversation_blocks[0].get("text"):
                conversation_blocks[0]["text"] = (
                    conversation_history_prompt
                    + "<history>\n"
                    + conversation_blocks[0]["text"]
                )
            else:
                conversation_blocks.insert(
                    0,
                    {"text": conversation_history_prompt + "<history>\n"},
                )
            if conversation_blocks[-1].get("text"):
                conversation_blocks[-1]["text"] += "\n</history>"
            else:
                conversation_blocks.append({"text": "</history>"})

        conversation_blocks_text = "\n".join(
            conversation_block.get("text", "")
            for conversation_block in conversation_blocks
        )

        content_list: list[dict[str, Any]] = []
        if conversation_blocks_text:
            content_list.append(
                {"type": "input_text", "text": conversation_blocks_text},
            )
        if images:
            content_list.extend(images)
        if audios:
            content_list.extend(audios)

        if content_list:
            formatted_msgs.append({"role": "user", "content": content_list})

        return formatted_msgs
