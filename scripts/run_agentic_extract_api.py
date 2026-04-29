"""通过公共 Python API 运行 agentic-extract。

这个脚本演示低层 settings-based API：
- `resolve_settings(...)`
- `run_agentic_extract(settings, ...)`

若要在外部程序里做一键 bootstrap + run，请直接调用高层
`agentic_extract.run_agentic_extract_auto(...)`。

默认使用测试模板 workspace：
`local/workspaces/test_workspace_templates/上交所-定期报告审计意见`

默认行为：
1. 复制模板 workspace 到一个带时间戳的新目录
2. 清理复制品中的 `logs/` 和 `.agent_state/`
3. 调用 `run_agentic_extract()`
4. 将 progress events 写入 `logs/api_events.jsonl`
5. 将最终 `RunResult` 写入 `logs/api_run_result.json`

示例：
    uv run python scripts/run_agentic_extract_api.py --dry-run
    uv run python scripts/run_agentic_extract_api.py --max-iterations 3
    uv run python scripts/run_agentic_extract_api.py --in-place --dry-run
    uv run python scripts/run_agentic_extract_api.py --config .agentic-extract.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from extract_agent_common.tiktoken_cache import ensure_tiktoken_cache

ensure_tiktoken_cache()

from agentic_extract.api import run_agentic_extract
from agentic_extract.config import resolve_settings
from agentic_extract.types import ProgressEvent, RunResult, TokenUsage


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_WORKSPACE = (
    REPO_ROOT / "local" / "workspaces" / "test_workspace_templates" / "上交所-定期报告审计意见"
)
DEFAULT_RUNS_DIR = REPO_ROOT / "local" / "workspaces" / "api_test_runs"


def _format_duration(duration_sec: float | None) -> str:
    if duration_sec is None:
        return "?"
    return f"{duration_sec:.1f}s"


def _format_token_usage(token_usage: TokenUsage | None) -> str:
    usage = token_usage or TokenUsage()
    parts = [
        f"tokens={usage.total_tokens}",
        f"in={usage.input_tokens}",
        f"out={usage.output_tokens}",
    ]
    if usage.cached_input_tokens is not None:
        parts.append(f"cache={usage.cached_input_tokens}")
    if usage.reasoning_output_tokens is not None:
        parts.append(f"reasoning={usage.reasoning_output_tokens}")
    return ", ".join(parts)


def _print_progress_event(event: ProgressEvent) -> None:
    prefix = []
    if event.iteration is not None:
        prefix.append(f"iter {event.iteration}")
    if event.step is not None:
        prefix.append(event.step)
    prefix_text = f"[{' | '.join(prefix)}] " if prefix else ""

    if event.type == "run_started":
        print("[run] started")
        return

    if event.type == "phase_started":
        print(f"[phase] {event.step} started")
        return

    if event.type == "phase_completed":
        print(
            f"[phase] {event.step} {event.status} "
            f"(duration={_format_duration(event.elapsed_step_sec)}, "
            f"{_format_token_usage(event.token_usage_total)})"
        )
        return

    if event.type == "iteration_started":
        print(f"{prefix_text}started")
        return

    if event.type == "supervisor_decided":
        action = event.data.get("action", "?")
        suffix = f" | {event.message}" if event.message else ""
        print(f"{prefix_text}decision={action}{suffix}")
        return

    if event.type == "step_started":
        suffix = f" | {event.message}" if event.message else ""
        print(f"{prefix_text}started{suffix}")
        return

    if event.type == "step_completed":
        print(
            f"{prefix_text}{event.status} "
            f"(step={_format_duration(event.elapsed_step_sec)}, "
            f"{_format_token_usage(event.token_usage_delta)})"
        )
        return

    if event.type == "heartbeat":
        print(
            f"{prefix_text}heartbeat "
            f"(step={_format_duration(event.elapsed_step_sec)}, "
            f"run={_format_duration(event.elapsed_total_run_sec)}, "
            f"{_format_token_usage(event.token_usage_total)})"
        )
        return

    if event.type == "iteration_completed":
        action = event.data.get("action", "?")
        print(
            f"{prefix_text}{event.status} action={action} "
            f"(duration={_format_duration(event.elapsed_iteration_sec)}, "
            f"{_format_token_usage(event.token_usage_delta)})"
        )
        return

    if event.type in {"run_completed", "run_failed"}:
        print(
            f"[run] {event.status} "
            f"(iterations={event.data.get('iteration_count', '?')}, "
            f"total={_format_duration(event.elapsed_total_run_sec)}, "
            f"{_format_token_usage(event.token_usage_total)})"
        )
        return

    print(f"[event] {event.type}")


def _print_run_summary(result: RunResult) -> None:
    print(
        "[summary] "
        f"status={result.status}, "
        f"iterations={result.iteration_count}, "
        f"iteration_duration={result.total_iteration_duration_sec:.1f}s, "
        f"run_duration={result.total_run_duration_sec:.1f}s, "
        f"{_format_token_usage(result.token_usage)}"
    )
    if result.error:
        print(f"[summary] error={result.error}")


def _copy_workspace(
    source_workspace: Path,
    run_workspace: Path,
    *,
    force: bool,
    reset_state: bool,
) -> Path:
    if run_workspace.exists():
        if not force:
            raise FileExistsError(
                f"目标 workspace 已存在: {run_workspace}；如需覆盖请加 --force"
            )
        shutil.rmtree(run_workspace)

    run_workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_workspace,
        run_workspace,
        ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache"),
    )

    if reset_state:
        for path in [run_workspace / "logs", run_workspace / ".agent_state"]:
            if path.exists():
                shutil.rmtree(path)

    return run_workspace


def _default_run_workspace(template_workspace: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_RUNS_DIR / f"{template_workspace.name}-api-test-{timestamp}"


def _build_request_payload(
    args: argparse.Namespace,
    run_workspace: Path,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "workspace": str(run_workspace),
    }

    if args.model is not None:
        payload["model"] = args.model
    if args.api_base is not None:
        payload["api_base"] = args.api_base
    if args.api_key is not None:
        payload["api_key"] = args.api_key
    if args.max_iterations is not None:
        payload["max_iterations"] = args.max_iterations
    if args.run_timeout is not None:
        payload["run_timeout"] = args.run_timeout
    if args.api_timeout is not None:
        payload["api_timeout"] = args.api_timeout
    if args.target_accuracy is not None:
        payload["target_accuracy"] = args.target_accuracy
    if args.reasoning_effort is not None:
        payload["reasoning_effort"] = args.reasoning_effort
    if args.initial_message is not None:
        payload["initial_message"] = args.initial_message
    if args.supervisor_mode is not None:
        payload["supervisor_mode"] = args.supervisor_mode

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过公共 Python API 运行 agentic-extract")
    parser.add_argument(
        "--template-workspace",
        type=Path,
        default=DEFAULT_TEMPLATE_WORKSPACE,
        help="模板 workspace 路径",
    )
    parser.add_argument(
        "--run-workspace",
        type=Path,
        help="实际运行的 workspace 路径；默认复制到 local/workspaces/api_test_runs/",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="直接在模板 workspace 上运行，不复制",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="若目标运行目录已存在则先删除",
    )
    parser.add_argument(
        "--keep-state",
        action="store_true",
        help="复制模板后保留 logs/ 与 .agent_state/，默认会清理后从干净状态开始",
    )
    parser.add_argument("--dry-run", action="store_true", help="只做 API 连通性验证")
    parser.add_argument("--max-iterations", type=int, help="最大迭代次数")
    parser.add_argument("--run-timeout", type=float, help="总运行超时（秒）")
    parser.add_argument("--api-timeout", type=float, help="单次 API 超时（秒）")
    parser.add_argument("--target-accuracy", type=float, help="目标准确率")
    parser.add_argument(
        "--heartbeat-interval-sec",
        type=float,
        default=10.0,
        help="heartbeat 间隔（秒）",
    )
    parser.add_argument(
        "--supervisor-mode",
        choices=["default", "simple"],
        help="Supervisor 模式",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        help="Reasoning effort",
    )
    parser.add_argument("--initial-message", help="初始消息（传给 Supervisor）")
    parser.add_argument("--model", help="覆盖模型配置")
    parser.add_argument("--api-base", help="覆盖 API Base")
    parser.add_argument("--api-key", help="覆盖 API Key")
    parser.add_argument("--config", type=Path, help="显式配置文件路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template_workspace = args.template_workspace.resolve()

    if not template_workspace.exists():
        print(f"模板 workspace 不存在: {template_workspace}", file=sys.stderr)
        return 1
    if not (template_workspace / "program.py").exists():
        print(f"模板 workspace 缺少 program.py: {template_workspace}", file=sys.stderr)
        return 1

    if args.in_place:
        run_workspace = template_workspace
    else:
        target_workspace = args.run_workspace.resolve() if args.run_workspace else _default_run_workspace(template_workspace)
        run_workspace = _copy_workspace(
            template_workspace,
            target_workspace,
            force=args.force,
            reset_state=not args.keep_state,
        )

    logs_dir = run_workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    event_log_path = logs_dir / "api_events.jsonl"
    result_json_path = logs_dir / "api_run_result.json"

    print(f"[workspace] template={template_workspace}")
    print(f"[workspace] run={run_workspace}")
    print(f"[artifacts] events={event_log_path}")
    print(f"[artifacts] result={result_json_path}")

    payload = _build_request_payload(args, run_workspace)

    try:
        settings = resolve_settings(
            str(run_workspace),
            config_path=args.config,
            overrides=payload,
        )
    except Exception as exc:
        print(f"构造 AgenticExtractSettings 失败: {exc}", file=sys.stderr)
        return 1

    with event_log_path.open("w", encoding="utf-8") as event_file:
        def on_event(event: ProgressEvent) -> None:
            _print_progress_event(event)
            event_file.write(event.model_dump_json() + "\n")
            event_file.flush()

        try:
            result = run_agentic_extract(
                settings,
                dry_run=args.dry_run,
                on_event=on_event,
                heartbeat_interval_sec=args.heartbeat_interval_sec,
            )
        except Exception as exc:
            print(f"[error] run_agentic_extract 失败: {exc}", file=sys.stderr)
            return 1

    result_json_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    _print_run_summary(result)
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
