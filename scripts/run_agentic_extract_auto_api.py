"""通过高层 Python API 运行 agentic-extract。

这个脚本演示 one-click 高层 API：
- `run_agentic_extract_auto(...)`

默认行为：
1. 从模板 workspace 复制代码骨架到一个新的运行目录
2. 默认把模板 workspace 的 `.xdev/` 作为 `data-dir` source
3. 调用 `run_agentic_extract_auto(...)` 完成 prepare + run
4. 将 progress events 写入 `logs/auto_api_events.jsonl`
5. 将最终 `RunResult` 写入 `logs/auto_api_run_result.json`

默认路径适合验证高层 API 的 bootstrap 场景，而不是仅复用已有 workspace。

示例：
    uv run python scripts/run_agentic_extract_auto_api.py --dry-run
    uv run python scripts/run_agentic_extract_auto_api.py --max-iterations 1
    uv run python scripts/run_agentic_extract_auto_api.py --source-data-dir /path/to/other/.xdev --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from extract_agent_common.tiktoken_cache import ensure_tiktoken_cache

ensure_tiktoken_cache()

from agentic_extract.api import run_agentic_extract_auto
from agentic_extract.types import (
    PrepareSourceDataDir,
    PrepareSpec,
    ProgressEvent,
    RunResult,
    TokenUsage,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_WORKSPACE = (
    REPO_ROOT / "local" / "workspaces" / "test_workspace_templates" / "上交所-定期报告审计意见"
)
DEFAULT_RUNS_DIR = REPO_ROOT / "local" / "workspaces" / "auto_api_test_runs"


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


def _default_run_workspace(template_workspace: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_RUNS_DIR / f"{template_workspace.name}-auto-api-test-{timestamp}"


def _copy_workspace_skeleton(
    source_workspace: Path,
    run_workspace: Path,
    *,
    force: bool,
) -> Path:
    if run_workspace.exists():
        if not force:
            raise FileExistsError(f"目标 workspace 已存在: {run_workspace}；如需覆盖请加 --force")
        shutil.rmtree(run_workspace)

    run_workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_workspace,
        run_workspace,
        ignore=shutil.ignore_patterns(
            ".xdev",
            ".git",
            "logs",
            ".agent_state",
            "__pycache__",
            ".ruff_cache",
            ".cache",
        ),
    )
    return run_workspace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过高层 Python API 运行 agentic-extract")
    parser.add_argument(
        "--template-workspace",
        type=Path,
        default=DEFAULT_TEMPLATE_WORKSPACE,
        help="模板 workspace 路径（用于复制代码骨架）",
    )
    parser.add_argument(
        "--run-workspace",
        type=Path,
        help="实际运行的 workspace 路径；默认复制到 local/workspaces/auto_api_test_runs/",
    )
    parser.add_argument(
        "--source-data-dir",
        type=Path,
        help="高层 API prepare 使用的 data-dir；默认取 template workspace 的 .xdev/",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="若目标运行目录已存在则先删除",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="显式配置文件路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="只做 prepare 判定和 API 连通性验证")
    parser.add_argument("--reset", action="store_true", help="运行前清除 logs/ 与 .agent_state/")
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
    return parser.parse_args()


def _build_settings_overrides(args: argparse.Namespace) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for key in [
        "model",
        "api_base",
        "api_key",
        "max_iterations",
        "run_timeout",
        "api_timeout",
        "target_accuracy",
        "reasoning_effort",
        "initial_message",
        "supervisor_mode",
    ]:
        value = getattr(args, key)
        if value is not None:
            overrides[key] = value
    return overrides


def main() -> int:
    args = parse_args()
    template_workspace = args.template_workspace.resolve()

    if not template_workspace.exists():
        print(f"模板 workspace 不存在: {template_workspace}", file=sys.stderr)
        return 1
    if not (template_workspace / "program.py").exists():
        print(f"模板 workspace 缺少 program.py: {template_workspace}", file=sys.stderr)
        return 1

    source_data_dir = (args.source_data_dir or (template_workspace / ".xdev")).resolve()
    if not source_data_dir.exists():
        print(f"source data-dir 不存在: {source_data_dir}", file=sys.stderr)
        return 1

    run_workspace = args.run_workspace.resolve() if args.run_workspace else _default_run_workspace(template_workspace)
    try:
        run_workspace = _copy_workspace_skeleton(
            template_workspace,
            run_workspace,
            force=args.force,
        )
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    logs_dir = run_workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    event_log_path = logs_dir / "auto_api_events.jsonl"
    result_json_path = logs_dir / "auto_api_run_result.json"

    prepare = PrepareSpec(
        source=PrepareSourceDataDir(data_dir=str(source_data_dir)),
    )
    settings_overrides = _build_settings_overrides(args)

    print(f"[workspace] template={template_workspace}")
    print(f"[workspace] run={run_workspace}")
    print(f"[prepare] source_type=data-dir")
    print(f"[prepare] source_data_dir={source_data_dir}")
    print(f"[artifacts] events={event_log_path}")
    print(f"[artifacts] result={result_json_path}")

    with event_log_path.open("w", encoding="utf-8") as event_file:

        def on_event(event: ProgressEvent) -> None:
            _print_progress_event(event)
            event_file.write(event.model_dump_json() + "\n")
            event_file.flush()

        try:
            result = run_agentic_extract_auto(
                str(run_workspace),
                prepare=prepare,
                config_path=args.config,
                settings_overrides=settings_overrides,
                dry_run=args.dry_run,
                reset=args.reset,
                on_event=on_event,
                heartbeat_interval_sec=args.heartbeat_interval_sec,
            )
        except Exception as exc:
            print(f"[error] run_agentic_extract_auto 失败: {exc}", file=sys.stderr)
            return 1

    result_json_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    _print_run_summary(result)
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
