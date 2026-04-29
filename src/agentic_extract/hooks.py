"""
Agent hooks: ruff check, loop detection, logging.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any
from uuid import uuid4

from agentscope.message import Msg

from .events import (
    emit_agent_call_completed,
    emit_agent_call_started,
    emit_agent_message,
)

logger = logging.getLogger(__name__)
agent_print_logger = logging.getLogger("agentic_extract.agent_print")

_CALL_ID_ATTR = "_agentic_extract_current_call_id"


def run_ruff_check_sync(file_path: str) -> list[dict]:
    """
    同步运行 ruff check 检查文件

    Returns:
        issues 列表，如果没有问题或出错则返回空列表
    """
    if not shutil.which("ruff"):
        return []  # ruff 未安装

    try:
        result = subprocess.run(
            ["ruff", "check", file_path, "--output-format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.stdout:
            return json.loads(result.stdout)
        return []
    except Exception:
        return []


def format_ruff_issues(issues: list[dict], file_path: str) -> str:
    """格式化 ruff check 的问题为友好的输出"""
    if not issues:
        return ""

    lines = []
    for issue in issues:
        line = issue.get("location", {}).get("row", "?")
        code = issue.get("code", "?")
        message = issue.get("message", "?")
        fix_available = issue.get("fix") is not None
        fix_marker = " [可自动修复]" if fix_available else ""
        lines.append(f"  - line {line}: {code} {message}{fix_marker}")

    result = f"[自动代码检查] 发现 {len(issues)} 个问题：\n"
    result += "\n".join(lines)

    # 检查是否有可自动修复的问题
    fixable_count = sum(1 for i in issues if i.get("fix") is not None)
    if fixable_count > 0:
        result += f"\n提示：运行 `ruff check --fix {file_path}` 可自动修复 {fixable_count} 个问题"

    return result


def create_ruff_check_hook():
    """
    创建 post_acting hook，用于在文件写入后自动运行 ruff check

    Returns:
        async hook 函数
    """
    async def ruff_check_hook(self, kwargs: dict, output: Any) -> Any:
        """
        post_acting hook: 检测文件写入工具，对 .py 文件运行 ruff check

        Args:
            self: Agent 实例
            kwargs: 包含 tool_call (ToolUseBlock)
            output: _acting 的返回值 (dict | None)
        """
        # 从 kwargs 获取 tool_call
        tool_call = kwargs.get("tool_call")
        if not tool_call:
            return output

        tool_name = tool_call.get("name", "")
        tool_input = tool_call.get("input", {})

        # 检查是否是文件写入工具
        if tool_name not in ("write_text_file", "insert_text_file",
                             "write_text_file_limited", "insert_text_file_limited"):
            return output

        file_path = tool_input.get("file_path", "")

        # 检查是否是 .py 文件
        if not file_path.endswith(".py"):
            return output

        # 同步运行 ruff check
        issues = run_ruff_check_sync(file_path)

        if not issues:
            return output

        # 格式化问题
        issues_text = format_ruff_issues(issues, file_path)

        # 创建 system 消息并添加到 memory
        system_msg = Msg(
            name="system",
            content=issues_text,
            role="system",
        )

        # 添加到 agent 的 memory
        if hasattr(self, "memory") and self.memory:
            await self.memory.add(system_msg)
        emit_agent_message(
            agent=self.name,
            source="internal",
            message=system_msg,
            call_id=getattr(self, _CALL_ID_ATTR, None),
        )

        return output

    return ruff_check_hook


def register_ruff_check_hook(agent) -> None:
    """
    为 agent 注册 ruff check hook

    Args:
        agent: ReActAgent 实例
    """
    hook = create_ruff_check_hook()
    agent.register_instance_hook(
        hook_type="post_acting",
        hook_name="ruff_check",
        hook=hook,
    )


def create_loop_detection_hook(threshold: int = 3):
    """创建 post_acting hook，检测 agent 是否在循环调用同一个命令。

    追踪 execute_shell_command 的调用。如果同一命令（取前 60 字符归一化）
    连续调用超过 threshold 次，向 memory 注入纠正消息。

    Args:
        threshold: 触发警告的重复次数阈值
    """
    # 闭包状态：追踪最近的命令调用
    call_history: list[str] = []

    def _normalize_cmd(cmd: str) -> str:
        """归一化命令用于比较（取前 60 字符，去除空白）"""
        return cmd.strip()[:60]

    async def loop_detection_hook(self, kwargs: dict, output: Any) -> Any:
        tool_call = kwargs.get("tool_call")
        if not tool_call:
            return output

        tool_name = tool_call.get("name", "")
        if tool_name != "execute_shell_command":
            # 非 shell 命令，重置历史
            call_history.clear()
            return output

        tool_input = tool_call.get("input", {})
        cmd = tool_input.get("command", "")
        normalized = _normalize_cmd(cmd)

        if call_history and call_history[-1] == normalized:
            call_history.append(normalized)
        else:
            call_history.clear()
            call_history.append(normalized)

        repeat_count = len(call_history)

        if repeat_count >= threshold:
            warning_msg = Msg(
                name="system",
                content=(
                    f"⚠️ 检测到你已连续 {repeat_count} 次执行相同命令 `{cmd[:80]}`。"
                    f"这是一个严重错误——你在循环中卡住了。\n"
                    f"请立即停止重复，回顾之前的输出结果，推进到下一步骤。"
                    f"如果之前的命令已有输出，直接使用该输出。"
                ),
                role="system",
            )
            if hasattr(self, "memory") and self.memory:
                await self.memory.add(warning_msg)
            emit_agent_message(
                agent=self.name,
                source="internal",
                message=warning_msg,
                call_id=getattr(self, _CALL_ID_ATTR, None),
            )

            # 超过 2 倍阈值时，更强烈的警告
            if repeat_count >= threshold * 2:
                strong_msg = Msg(
                    name="system",
                    content=(
                        f"🚨 严重循环：已重复 {repeat_count} 次。"
                        f"你必须执行一个不同的命令来打破循环。"
                        f"建议：执行 `xdev doc <id>` 查看具体文档内容。"
                    ),
                    role="system",
                )
                if hasattr(self, "memory") and self.memory:
                    await self.memory.add(strong_msg)
                emit_agent_message(
                    agent=self.name,
                    source="internal",
                    message=strong_msg,
                    call_id=getattr(self, _CALL_ID_ATTR, None),
                )

        return output

    return loop_detection_hook


def register_loop_detection_hook(agent, threshold: int = 3) -> None:
    """为 agent 注册循环检测 hook"""
    hook = create_loop_detection_hook(threshold)
    agent.register_instance_hook(
        hook_type="post_acting",
        hook_name="loop_detection",
        hook=hook,
    )


def register_agent_logging(agent) -> None:
    """Register post_print hook to log agent messages to agentic_extract.agent_print logger."""
    async def _pre_reply_hook(self, kwargs: dict) -> dict:
        call_id = uuid4().hex
        setattr(self, _CALL_ID_ATTR, call_id)
        structured_model = kwargs.get("structured_model")
        emit_agent_call_started(
            agent=self.name,
            call_id=call_id,
            input_messages=kwargs.get("msg"),
            structured_output_model=getattr(structured_model, "__name__", None),
        )
        return kwargs

    async def _post_print_hook(self, kwargs: dict, output) -> None:
        msg = kwargs.get("msg")
        last = kwargs.get("last", True)
        if not last or msg is None:
            return output
        emit_agent_message(
            agent=self.name,
            source="print",
            message=msg,
            call_id=getattr(self, _CALL_ID_ATTR, None),
            last_chunk=bool(last),
        )
        parts = []
        for block in msg.get_content_blocks():
            if block.get("type") == "text":
                parts.append(f"{msg.name}: {block['text']}")
            elif block.get("type") == "thinking":
                parts.append(f"{msg.name}(thinking): {block['thinking']}")
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        if parts:
            agent_print_logger.info("\n".join(parts))
        return output

    async def _post_reply_hook(self, kwargs: dict, output) -> Any:
        _ = kwargs
        metadata = getattr(output, "metadata", None)
        max_iters_reached = isinstance(metadata, dict) and bool(metadata.get("_max_iters_reached"))
        emit_agent_call_completed(
            agent=self.name,
            call_id=getattr(self, _CALL_ID_ATTR, None),
            reply_message=output,
            max_iters_reached=max_iters_reached,
        )
        if hasattr(self, _CALL_ID_ATTR):
            delattr(self, _CALL_ID_ATTR)
        return output

    async def _post_observe_hook(self, kwargs: dict, output) -> Any:
        _ = output
        observed = kwargs.get("msg")
        if observed is None:
            return output
        messages = observed if isinstance(observed, list) else [observed]
        for msg in messages:
            emit_agent_message(
                agent=self.name,
                source="observe",
                message=msg,
            )
        return output

    agent.register_instance_hook(
        hook_type="pre_reply",
        hook_name="agent_event_call_start",
        hook=_pre_reply_hook,
    )
    agent.register_instance_hook(
        hook_type="post_print",
        hook_name="agent_logging",
        hook=_post_print_hook,
    )
    agent.register_instance_hook(
        hook_type="post_reply",
        hook_name="agent_event_call_end",
        hook=_post_reply_hook,
    )
    agent.register_instance_hook(
        hook_type="post_observe",
        hook_name="agent_event_observe",
        hook=_post_observe_hook,
    )
