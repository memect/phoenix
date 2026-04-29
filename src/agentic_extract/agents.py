"""
Agent 创建工厂

创建 supervisor、business_agent、dev_agent 三个 Agent 类实例。
每个 agent 的 system prompt 由 prompts/ 模块中的常量组装而成。
"""

import copy
import logging

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, execute_shell_command, view_text_file
from agentscope.token import OpenAITokenCounter


class SafeTokenCounter(OpenAITokenCounter):
    """OpenAITokenCounter 的安全包装。

    AgentScope 的 OpenAITokenCounter 不支持 tool_use / tool_result
    等 Anthropic content block 类型。此子类将其转换为 OpenAI 格式。
    """

    def _convert_message(self, msg: dict) -> dict | list[dict]:
        """将 Anthropic 格式的消息转换为 OpenAI 格式。

        Returns:
            单条消息 dict 或多条消息 list（tool_result 会拆分为独立消息）
        """
        content = msg.get("content")
        if not isinstance(content, list):
            return msg

        # 分离不同类型的 content blocks
        text_blocks = []
        tool_use_blocks = []
        tool_result_blocks = []
        other_blocks = []

        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use":
                tool_use_blocks.append(block)
            elif block_type == "tool_result":
                tool_result_blocks.append(block)
            elif block_type in ("text", "image_url"):
                other_blocks.append(block)
            else:
                # 未知类型，保留原样
                other_blocks.append(block)

        # 构建结果消息列表
        result_msgs = []

        # 1. 处理 tool_result → 转为独立的 role: tool 消息
        for block in tool_result_blocks:
            tool_msg = {
                "role": "tool",
                "tool_call_id": block.get("tool_use_id", "unknown"),
                "content": block.get("content", ""),
            }
            result_msgs.append(tool_msg)

        # 2. 处理原消息（可能包含 text/image_url/tool_use）
        if text_blocks or other_blocks or tool_use_blocks:
            new_msg = {"role": msg.get("role", "assistant")}

            # 合并 text 和其他 blocks
            combined_content = other_blocks + text_blocks
            if combined_content:
                if len(combined_content) == 1 and combined_content[0].get("type") == "text":
                    # 单个 text block → 字符串
                    new_msg["content"] = combined_content[0].get("text", "")
                else:
                    # 多个 blocks → list
                    new_msg["content"] = combined_content

            # tool_use → tool_calls
            if tool_use_blocks:
                import json as _json
                new_msg["tool_calls"] = [
                    {
                        "id": block.get("id", "unknown"),
                        "type": "function",
                        "function": {
                            "name": block.get("name", "unknown"),
                            "arguments": _json.dumps(block.get("input", {})),
                        },
                    }
                    for block in tool_use_blocks
                ]
                if not new_msg.get("content"):
                    new_msg["content"] = None

            result_msgs.insert(0, new_msg)

        return result_msgs if len(result_msgs) > 1 else (result_msgs[0] if result_msgs else msg)

    async def count(self, messages, tools=None, **kwargs):
        """转换消息格式后调用父类 count"""
        converted = []
        for msg in messages:
            result = self._convert_message(msg)
            if isinstance(result, list):
                converted.extend(result)
            else:
                converted.append(result)
        return await super().count(converted, tools=tools, **kwargs)

from .model_factory import create_model
from .tools import register_file_tools
from .hooks import register_ruff_check_hook, register_agent_logging, register_loop_detection_hook
from .prompts.assembly import (
    assemble_supervisor_prompt,
    assemble_business_prompt,
    assemble_dev_prompt,
)
from .agent_classes import Supervisor, BusinessAgent, DevAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schema 兼容性修复
# ---------------------------------------------------------------------------

def _sanitize_schema(schema: dict) -> dict:
    """递归清理 JSON schema 中 Anthropic API 不支持的结构。

    - 将 ``anyOf: [{type: X}, {type: null}]`` 简化为 ``{type: X}``
    - 将 ``anyOf: [{items: ..., type: array}, {type: null}]`` 简化为 ``{type: array, items: ...}``
    - 移除 ``default: null`` (Anthropic API 不接受 null 作为默认值)
    - 确保 parameters 有 ``required`` 字段（即使为空数组）
    """
    if not isinstance(schema, dict):
        return schema

    result = {}
    for key, value in schema.items():
        # 跳过 default: null
        if key == "default" and value is None:
            continue

        if key == "anyOf" and isinstance(value, list):
            non_null = [v for v in value if v.get("type") != "null"]
            if len(non_null) == 1:
                # anyOf: [{type: X}, {type: null}] → {type: X}
                merged = _sanitize_schema(non_null[0])
                result.update(merged)
                continue

        # 确保 parameters 有 required 字段
        if key == "parameters" and isinstance(value, dict):
            sanitized = _sanitize_schema(value)
            if "required" not in sanitized:
                sanitized["required"] = []
            result[key] = sanitized
            continue

        if isinstance(value, dict):
            result[key] = _sanitize_schema(value)
        elif isinstance(value, list):
            result[key] = [_sanitize_schema(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


class CleanToolkit(Toolkit):
    """Toolkit 子类，在返回 JSON schema 时自动清理 anyOf 等不兼容结构。"""

    def get_json_schemas(self) -> list[dict]:
        raw = super().get_json_schemas()
        return [_sanitize_schema(copy.deepcopy(s)) for s in raw]


# ---------------------------------------------------------------------------
# 上下文压缩
# ---------------------------------------------------------------------------

def _create_compression_config(
    max_context_length: int = 128000,
    compression_keep_recent: int = 10,
    *,
    model_spec: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    timeout: float = 300.0,
) -> ReActAgent.CompressionConfig:
    """创建统一的上下文压缩配置

    当提供模型参数时，创建独立的非流式模型专门用于压缩，
    避免流式解析在某些 API 代理上出错。
    """
    trigger_threshold = int(max_context_length * 0.9)

    compression_model = None
    if model_spec and api_base and api_key:
        from .model_factory import PlainJsonModelWrapper

        raw_model, _ = create_model(
            model_spec=model_spec,
            api_base=api_base,
            api_key=api_key,
            stream=False,
            timeout=timeout,
        )
        compression_model = PlainJsonModelWrapper(raw_model)

    return ReActAgent.CompressionConfig(
        enable=True,
        agent_token_counter=SafeTokenCounter(model_name="gpt-4o"),
        trigger_threshold=trigger_threshold,
        keep_recent=compression_keep_recent,
        compression_model=compression_model,
    )


# ---------------------------------------------------------------------------
# 工具注册
# ---------------------------------------------------------------------------

def _create_base_toolkit(
    limit_write_lines: bool = False,
    max_write_lines: int = 100,
) -> CleanToolkit:
    """创建基础工具集（shell + 文件读写）"""
    toolkit = CleanToolkit()
    toolkit.register_tool_function(execute_shell_command)
    toolkit.register_tool_function(view_text_file)
    register_file_tools(toolkit, limit_write_lines, max_write_lines)
    return toolkit


# ---------------------------------------------------------------------------
# Agent 创建
# ---------------------------------------------------------------------------

def create_supervisor(
    model: str,
    api_base: str,
    api_key: str,
    target_accuracy: float = 0.99,
    timeout: float = 300.0,
    max_retries: int = 0,
    max_context_length: int = 128000,
    compression_keep_recent: int = 10,
    readonly_labels: bool = False,
    reasoning_effort: str | None = None,
    preserve_thinking: bool = False,
    simple_mode: bool = False,
    use_responses_api: bool = False,
    max_iters: int = 1000,
) -> Supervisor:
    """创建 Supervisor agent"""
    sys_prompt, _ = assemble_supervisor_prompt(target_accuracy, readonly_labels, simple_mode)

    if simple_mode:
        toolkit = CleanToolkit()
    else:
        toolkit = _create_base_toolkit()

    model_kwargs: dict = {}
    if reasoning_effort:
        model_kwargs["reasoning_effort"] = reasoning_effort
    if use_responses_api:
        model_kwargs["use_responses_api"] = True

    llm, formatter = create_model(
        model_spec=model,
        api_base=api_base,
        api_key=api_key,
        stream=True,
        timeout=timeout,
        max_retries=max_retries,
        preserve_thinking=preserve_thinking,
        **model_kwargs,
    )

    react_agent = ReActAgent(
        name="Supervisor",
        sys_prompt=sys_prompt,
        model=llm,
        formatter=formatter,
        toolkit=toolkit,
        memory=InMemoryMemory(),
        max_iters=max_iters,
        compression_config=_create_compression_config(
            max_context_length, compression_keep_recent,
            model_spec=model, api_base=api_base, api_key=api_key,
            timeout=timeout,
        ),
    )

    register_agent_logging(react_agent)

    return Supervisor(react_agent)


def create_business_agent(
    model: str,
    api_base: str,
    api_key: str,
    timeout: float = 300.0,
    max_retries: int = 0,
    limit_write_lines: bool = False,
    max_write_lines: int = 100,
    max_context_length: int = 128000,
    compression_keep_recent: int = 10,
    readonly_labels: bool = False,
    reasoning_effort: str | None = None,
    preserve_thinking: bool = False,
    labeling_model: str | None = None,
    labeling_api_base: str | None = None,
    labeling_api_key: str | None = None,
    use_responses_api: bool = False,
    max_iters: int = 1000,
) -> BusinessAgent:
    """创建 BusinessAgent"""
    sys_prompt, _ = assemble_business_prompt(readonly_labels)

    toolkit = _create_base_toolkit(limit_write_lines, max_write_lines)

    # 注册批量标注工具（默认使用 business agent 自身的模型配置）
    from .labeling.workflow import create_label_all_documents_tool
    label_tool = create_label_all_documents_tool(
        labeling_model=labeling_model or model,
        labeling_api_base=labeling_api_base or api_base,
        labeling_api_key=labeling_api_key or api_key,
        labeling_timeout=timeout,
        labeling_max_retries=max_retries,
    )
    toolkit.register_tool_function(label_tool)

    model_kwargs: dict = {}
    if reasoning_effort:
        model_kwargs["reasoning_effort"] = reasoning_effort
    if use_responses_api:
        model_kwargs["use_responses_api"] = True

    llm, formatter = create_model(
        model_spec=model,
        api_base=api_base,
        api_key=api_key,
        stream=True,
        timeout=timeout,
        max_retries=max_retries,
        preserve_thinking=preserve_thinking,
        **model_kwargs,
    )

    react_agent = ReActAgent(
        name="BusinessAgent",
        sys_prompt=sys_prompt,
        model=llm,
        formatter=formatter,
        toolkit=toolkit,
        memory=InMemoryMemory(),
        max_iters=max_iters,
        compression_config=_create_compression_config(
            max_context_length, compression_keep_recent,
            model_spec=model, api_base=api_base, api_key=api_key,
            timeout=timeout,
        ),
    )

    register_agent_logging(react_agent)
    register_loop_detection_hook(react_agent)

    return BusinessAgent(react_agent)


def create_dev_agent(
    model: str,
    api_base: str,
    api_key: str,
    timeout: float = 300.0,
    max_retries: int = 0,
    limit_write_lines: bool = False,
    max_write_lines: int = 100,
    max_context_length: int = 128000,
    compression_keep_recent: int = 10,
    reasoning_effort: str | None = None,
    preserve_thinking: bool = False,
    business_agent: BusinessAgent | None = None,
    use_responses_api: bool = False,
    max_iters: int = 1000,
) -> DevAgent:
    """创建 DevAgent"""
    sys_prompt, _ = assemble_dev_prompt()

    toolkit = _create_base_toolkit(limit_write_lines, max_write_lines)

    model_kwargs: dict = {}
    if reasoning_effort:
        model_kwargs["reasoning_effort"] = reasoning_effort
    if use_responses_api:
        model_kwargs["use_responses_api"] = True

    llm, formatter = create_model(
        model_spec=model,
        api_base=api_base,
        api_key=api_key,
        stream=True,
        timeout=timeout,
        max_retries=max_retries,
        preserve_thinking=preserve_thinking,
        **model_kwargs,
    )

    react_agent = ReActAgent(
        name="DevAgent",
        sys_prompt=sys_prompt,
        model=llm,
        formatter=formatter,
        toolkit=toolkit,
        memory=InMemoryMemory(),
        max_iters=max_iters,
        compression_config=_create_compression_config(
            max_context_length, compression_keep_recent,
            model_spec=model, api_base=api_base, api_key=api_key,
            timeout=timeout,
        ),
    )

    register_ruff_check_hook(react_agent)
    register_agent_logging(react_agent)
    register_loop_detection_hook(react_agent)

    return DevAgent(react_agent, business_agent)
