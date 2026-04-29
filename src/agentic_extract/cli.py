"""
agentic-extract CLI 入口
"""

import logging
import sys

import click
from extract_agent_common.tiktoken_cache import ensure_tiktoken_cache

from .types import (
    PrepareSourceConfigFile,
    PrepareSourceDataDir,
    PrepareSourceExisting,
    PrepareSourcePdfDir,
    PrepareSourceSetId,
    PrepareSpec,
    ProgressEvent,
    RunResult,
    TokenUsage,
)

ensure_tiktoken_cache()

_BUDGET_PRESETS: dict[str, dict[str, int]] = {
    "fast": {
        "max_iterations": 10,
        "agent_max_iters": 10,
    },
    "full": {
        "max_iterations": 50,
        "agent_max_iters": 100,
    }
}


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
        click.echo("[run] started")
        return

    if event.type == "phase_started":
        click.echo(f"[phase] {event.step} started")
        return

    if event.type == "phase_completed":
        click.echo(
            f"[phase] {event.step} {event.status} "
            f"(duration={_format_duration(event.elapsed_step_sec)}, "
            f"{_format_token_usage(event.token_usage_total)})"
        )
        return

    if event.type == "iteration_started":
        click.echo(f"{prefix_text}started")
        return

    if event.type == "supervisor_decided":
        action = event.data.get("action", "?")
        suffix = f" | {event.message}" if event.message else ""
        click.echo(f"{prefix_text}decision={action}{suffix}")
        return

    if event.type == "step_started":
        suffix = f" | {event.message}" if event.message else ""
        click.echo(f"{prefix_text}started{suffix}")
        return

    if event.type == "step_completed":
        click.echo(
            f"{prefix_text}{event.status} "
            f"(step={_format_duration(event.elapsed_step_sec)}, "
            f"{_format_token_usage(event.token_usage_delta)})"
        )
        return

    if event.type == "heartbeat":
        click.echo(
            f"{prefix_text}heartbeat "
            f"(step={_format_duration(event.elapsed_step_sec)}, "
            f"run={_format_duration(event.elapsed_total_run_sec)}, "
            f"{_format_token_usage(event.token_usage_total)})"
        )
        return

    if event.type == "iteration_completed":
        action = event.data.get("action", "?")
        click.echo(
            f"{prefix_text}{event.status} action={action} "
            f"(duration={_format_duration(event.elapsed_iteration_sec)}, "
            f"{_format_token_usage(event.token_usage_delta)})"
        )
        return

    if event.type in {"run_completed", "run_failed"}:
        click.echo(
            f"[run] {event.status} "
            f"(iterations={event.data.get('iteration_count', '?')}, "
            f"total={_format_duration(event.elapsed_total_run_sec)}, "
            f"{_format_token_usage(event.token_usage_total)})"
        )
        return

    click.echo(f"[event] {event.type}")


def _print_run_summary(result: RunResult) -> None:
    click.echo(
        "[summary] "
        f"status={result.status}, "
        f"iterations={result.iteration_count}, "
        f"iteration_duration={result.total_iteration_duration_sec:.1f}s, "
        f"run_duration={result.total_run_duration_sec:.1f}s, "
        f"{_format_token_usage(result.token_usage)}"
    )
    if result.error:
        click.echo(f"[summary] error={result.error}")


def _format_budget_value(value) -> str:
    if value is None:
        return "disabled"
    if isinstance(value, float):
        return f"{value:.0f}s" if value.is_integer() else f"{value:g}s"
    return str(value)


def _print_budget_summary(settings) -> None:
    budget = settings.execution_budget()
    click.echo("[budget]")
    budget_profile = getattr(settings, "_budget_profile", None)
    if budget_profile:
        click.echo(f"profile={budget_profile}")
    click.echo(f"workflow_max_iterations={budget['workflow_max_iterations']}")
    click.echo(f"agent_max_iters={budget['agent_max_iters']}")
    click.echo(f"supervisor_max_iters={budget['supervisor_max_iters']}")
    click.echo(f"business_max_iters={budget['business_max_iters']}")
    click.echo(f"dev_max_iters={budget['dev_max_iters']}")
    click.echo(f"run_timeout={_format_budget_value(budget['run_timeout'])}")


def _apply_options(options):
    def decorator(func):
        for option in reversed(options):
            func = option(func)
        return func

    return decorator


def _abort_with_error(message: str) -> None:
    click.echo(f"错误：{message}", err=True)
    raise click.Abort()


def _ensure_runtime_flags_are_valid(*, dry_run: bool, reset: bool) -> None:
    if dry_run and reset:
        _abort_with_error("--dry-run 与 --reset 不能同时使用")


def _build_settings_overrides(
    *,
    budget=None,
    model=None,
    api_base=None,
    api_key=None,
    supervisor_model=None,
    business_model=None,
    dev_model=None,
    workspace=None,
    max_iterations=None,
    agent_max_iters=None,
    supervisor_max_iters=None,
    business_max_iters=None,
    dev_max_iters=None,
    target_accuracy=None,
    run_timeout=None,
    api_timeout=None,
    max_retries=None,
    studio_url=None,
    max_context_length=None,
    compression_keep_recent=None,
    initial_message=None,
    readonly_labels=False,
    reasoning_effort=None,
    preserve_thinking=False,
    supervisor_mode=None,
):
    overrides = dict(_BUDGET_PRESETS.get(budget, {})) if budget else {}
    for key, value in {
        "model": model,
        "api_base": api_base,
        "api_key": api_key,
        "supervisor_model": supervisor_model,
        "business_model": business_model,
        "dev_model": dev_model,
        "workspace": workspace,
        "max_iterations": max_iterations,
        "agent_max_iters": agent_max_iters,
        "supervisor_max_iters": supervisor_max_iters,
        "business_max_iters": business_max_iters,
        "dev_max_iters": dev_max_iters,
        "target_accuracy": target_accuracy,
        "run_timeout": run_timeout,
        "api_timeout": api_timeout,
        "max_retries": max_retries,
        "studio_url": studio_url,
        "max_context_length": max_context_length,
        "compression_keep_recent": compression_keep_recent,
        "initial_message": initial_message,
        "reasoning_effort": reasoning_effort,
        "supervisor_mode": supervisor_mode,
    }.items():
        if value is not None:
            overrides[key] = value

    if readonly_labels:
        overrides["readonly_labels"] = True
    if preserve_thinking:
        overrides["preserve_thinking"] = True
    return overrides


def _build_prepare_spec(
    *,
    set_id=None,
    std_ids=None,
    std_ids_file=None,
    limit=None,
    base_url=None,
    pdfs_dir=None,
    data_dir=None,
    source_file=None,
) -> PrepareSpec:
    if (std_ids or std_ids_file) and not set_id:
        _abort_with_error("--std-ids / --std-ids-file 只能与 --set-id 一起使用")
    if limit is not None and not set_id:
        _abort_with_error("--limit 只能与 --set-id 一起使用")
    if base_url is not None and not set_id:
        _abort_with_error("--base-url 只能与 --set-id 一起使用")

    sources = [set_id, pdfs_dir, data_dir, source_file]
    if sum(bool(source) for source in sources) > 1:
        _abort_with_error("数据源互斥，只能指定一个")

    from xdev.import_data import resolve_std_ids

    resolved_std_ids = resolve_std_ids(std_ids, std_ids_file)

    if set_id is not None:
        source_kwargs = {"set_id": set_id}
        if base_url is not None:
            source_kwargs["base_url"] = base_url
        if resolved_std_ids is not None:
            source_kwargs["std_ids"] = resolved_std_ids
        if limit is not None:
            source_kwargs["limit"] = limit
        return PrepareSpec(source=PrepareSourceSetId(**source_kwargs))
    if pdfs_dir is not None:
        return PrepareSpec(source=PrepareSourcePdfDir(pdfs_dir=pdfs_dir))
    if data_dir is not None:
        return PrepareSpec(source=PrepareSourceDataDir(data_dir=data_dir))
    if source_file is not None:
        return PrepareSpec(source=PrepareSourceConfigFile(source_file=source_file))
    return PrepareSpec(source=PrepareSourceExisting())


def _collect_deprecated_run_prepare_options(
    *,
    set_id=None,
    std_ids=None,
    std_ids_file=None,
    limit=None,
    base_url=None,
    pdfs_dir=None,
    data_dir=None,
    source_file=None,
    add_pdf=None,
    add_pdf_force=False,
    sync_pdfs=False,
) -> list[str]:
    used = []
    if set_id is not None:
        used.append("--set-id")
    if std_ids is not None:
        used.append("--std-ids")
    if std_ids_file is not None:
        used.append("--std-ids-file")
    if limit is not None:
        used.append("--limit")
    if base_url is not None:
        used.append("--base-url")
    if pdfs_dir is not None:
        used.append("--pdfs-dir/--pdfs")
    if data_dir is not None:
        used.append("--data-dir")
    if source_file is not None:
        used.append("--source-file/--source")
    if add_pdf is not None:
        used.append("--add-pdf")
    if add_pdf_force:
        used.append("--force")
    if sync_pdfs:
        used.append("--sync-pdfs")
    return used


def _abort_for_deprecated_run_prepare_options(option_names: list[str]) -> None:
    used = ", ".join(option_names)
    _abort_with_error(
        "agentic-extract run 已改为纯运行命令，不再负责数据准备。"
        f" 检测到旧参数：{used}。请改用 agentic-extract auto 完成 bootstrap；"
        "增量导入或同步 PDF 请使用 xdev import-data。"
    )


def _reset_runtime_state_for_cli(workspace: str) -> None:
    from .api import _reset_runtime_state

    for path in _reset_runtime_state(workspace):
        click.echo(f"已清除: {path}")


_RUN_OPTIONS = [
    click.option("--model", help="LLM 模型 (e.g. openai/gpt-4o)"),
    click.option("--api-base", help="API 地址"),
    click.option("--api-key", help="API Key"),
    click.option("--supervisor-model", help="Supervisor 模型（默认同 --model）"),
    click.option("--business-model", help="BusinessAgent 模型（默认同 --model）"),
    click.option("--dev-model", help="DevAgent 模型（默认同 --model）"),
    click.option("--workspace", default="workspace", show_default=True, help="工作目录"),
    click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), help="显式配置文件路径"),
    click.option("--budget", type=click.Choice(sorted(_BUDGET_PRESETS)), help="预算档位预设：fast=10/10，full=50/100"),
    click.option("--max-iterations", type=int, help="最大迭代次数"),
    click.option("--agent-max-iters", type=int, help="各 agent 单次调用内部最大迭代次数"),
    click.option("--supervisor-max-iters", type=int, help="Supervisor 单次调用内部最大迭代次数（默认回退到 --agent-max-iters）"),
    click.option("--business-max-iters", type=int, help="BusinessAgent 单次调用内部最大迭代次数（默认回退到 --agent-max-iters）"),
    click.option("--dev-max-iters", type=int, help="DevAgent 单次调用内部最大迭代次数（默认回退到 --agent-max-iters）"),
    click.option("--target-accuracy", type=float, help="目标准确率 (0-1)"),
    click.option("--run-timeout", type=float, help="运行总时长限制（秒，当前为轮间检查的兜底超时）"),
    click.option("--api-timeout", type=float, help="API 超时（秒）"),
    click.option("--max-retries", type=int, help="请求最大重试次数"),
    click.option("--studio-url", help="AgentScope Studio URL (e.g. http://localhost:3000)"),
    click.option("--max-context-length", type=int, help="最大上下文长度（token）"),
    click.option("--compression-keep-recent", type=int, help="压缩时保留的最近消息数"),
    click.option("--message", "initial_message", help="初始消息（传给 Supervisor）"),
    click.option("--readonly-labels", is_flag=True, help="标注只读模式，禁止 Agent 修改标注数据"),
    click.option("--reasoning-effort", type=click.Choice(["low", "medium", "high"]), help="Reasoning effort (for o1/o3 models)"),
    click.option("--preserve-thinking", is_flag=True, help="保留 thinking blocks（解决 extended thinking 模型循环读取问题）"),
    click.option("--supervisor", "supervisor_mode", type=click.Choice(["default", "simple"]), help="Supervisor 模式：simple=无工具纯决策，default=带工具"),
    click.option("--heartbeat-interval-sec", type=float, default=10.0, show_default=True, help="heartbeat 间隔（秒）"),
    click.option("--dry-run", is_flag=True, help="只验证配置、workspace readiness 和 API 连通性，不运行 agent 循环"),
    click.option("--reset", is_flag=True, help="清除 logs/ 与 .agent_state/ 后重新开始"),
]

_AUTO_PREPARE_OPTIONS = [
    click.option("--set-id", help="远程标准集 ID"),
    click.option("--std-ids", help="文档 ID 白名单（逗号分隔），配合 --set-id 使用"),
    click.option("--std-ids-file", type=click.Path(exists=True, dir_okay=False), help="文档 ID 白名单文件（一行一个 ID），配合 --set-id 使用"),
    click.option("--limit", type=int, help="限制导入文档数量，配合 --set-id 使用"),
    click.option("--base-url", help="标准集 API 地址（配合 --set-id 使用）"),
    click.option("--pdfs-dir", type=click.Path(exists=True, file_okay=False), help="本地 PDF 目录"),
    click.option("--data-dir", type=click.Path(exists=True, file_okay=False), help="从另一个 .xdev 导入"),
    click.option("--source-file", type=click.Path(exists=True, dir_okay=False), help="数据源配置文件"),
]

_DEPRECATED_RUN_PREPARE_OPTIONS = [
    click.option("--set-id", hidden=True),
    click.option("--std-ids", hidden=True),
    click.option("--std-ids-file", type=click.Path(exists=True, dir_okay=False), hidden=True),
    click.option("--limit", type=int, hidden=True),
    click.option("--base-url", hidden=True),
    click.option("--pdfs-dir", "--pdfs", "deprecated_pdfs_dir", type=click.Path(exists=True, file_okay=False), hidden=True),
    click.option("--data-dir", type=click.Path(exists=True, file_okay=False), hidden=True),
    click.option("--source-file", "--source", "deprecated_source_file", type=click.Path(exists=True, dir_okay=False), hidden=True),
    click.option("--add-pdf", type=click.Path(exists=True), hidden=True),
    click.option("--force", "add_pdf_force", is_flag=True, hidden=True),
    click.option("--sync-pdfs", is_flag=True, hidden=True),
]


@click.group()
def cli():
    """agentic-extract — 无标注提取 agentic loop"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stdout)


@cli.command()
@_apply_options(_RUN_OPTIONS)
@_apply_options(_DEPRECATED_RUN_PREPARE_OPTIONS)
def run(
    model,
    api_base,
    api_key,
    supervisor_model,
    business_model,
    dev_model,
    workspace,
    config_path,
    budget,
    max_iterations,
    agent_max_iters,
    supervisor_max_iters,
    business_max_iters,
    dev_max_iters,
    target_accuracy,
    run_timeout,
    api_timeout,
    max_context_length,
    compression_keep_recent,
    max_retries,
    studio_url,
    initial_message,
    readonly_labels,
    reasoning_effort,
    preserve_thinking,
    supervisor_mode,
    heartbeat_interval_sec,
    dry_run,
    reset,
    set_id,
    std_ids,
    std_ids_file,
    limit,
    base_url,
    deprecated_pdfs_dir,
    data_dir,
    deprecated_source_file,
    add_pdf,
    add_pdf_force,
    sync_pdfs,
):
    """启动纯运行模式；要求 workspace 已具备可运行的 .xdev 数据。"""
    from .api import run_agentic_extract
    from .config import resolve_settings
    from .workspace import ensure_workspace_ready

    _ensure_runtime_flags_are_valid(dry_run=dry_run, reset=reset)

    deprecated_options = _collect_deprecated_run_prepare_options(
        set_id=set_id,
        std_ids=std_ids,
        std_ids_file=std_ids_file,
        limit=limit,
        base_url=base_url,
        pdfs_dir=deprecated_pdfs_dir,
        data_dir=data_dir,
        source_file=deprecated_source_file,
        add_pdf=add_pdf,
        add_pdf_force=add_pdf_force,
        sync_pdfs=sync_pdfs,
    )
    if deprecated_options:
        _abort_for_deprecated_run_prepare_options(deprecated_options)

    settings_overrides = _build_settings_overrides(
        model=model,
        api_base=api_base,
        api_key=api_key,
        supervisor_model=supervisor_model,
        business_model=business_model,
        dev_model=dev_model,
        workspace=workspace,
        budget=budget,
        max_iterations=max_iterations,
        agent_max_iters=agent_max_iters,
        supervisor_max_iters=supervisor_max_iters,
        business_max_iters=business_max_iters,
        dev_max_iters=dev_max_iters,
        target_accuracy=target_accuracy,
        run_timeout=run_timeout,
        api_timeout=api_timeout,
        max_retries=max_retries,
        studio_url=studio_url,
        max_context_length=max_context_length,
        compression_keep_recent=compression_keep_recent,
        initial_message=initial_message,
        readonly_labels=readonly_labels,
        reasoning_effort=reasoning_effort,
        preserve_thinking=preserve_thinking,
        supervisor_mode=supervisor_mode,
    )

    try:
        settings = resolve_settings(
            workspace,
            config_path=config_path,
            overrides=settings_overrides,
        )
    except ValueError as exc:
        _abort_with_error(str(exc))

    if budget:
        setattr(settings, "_budget_profile", budget)
    _print_budget_summary(settings)

    if reset:
        _reset_runtime_state_for_cli(settings.workspace)

    if dry_run:
        try:
            ensure_workspace_ready(settings.workspace, allow_normalize=False)
        except ValueError as exc:
            _abort_with_error(str(exc))

    try:
        result = run_agentic_extract(
            settings,
            dry_run=dry_run,
            on_event=_print_progress_event,
            heartbeat_interval_sec=heartbeat_interval_sec,
        )
    except ValueError as exc:
        _abort_with_error(str(exc))

    _print_run_summary(result)


@cli.command()
@_apply_options(_RUN_OPTIONS)
@_apply_options(_AUTO_PREPARE_OPTIONS)
def auto(
    model,
    api_base,
    api_key,
    supervisor_model,
    business_model,
    dev_model,
    workspace,
    config_path,
    budget,
    max_iterations,
    agent_max_iters,
    supervisor_max_iters,
    business_max_iters,
    dev_max_iters,
    target_accuracy,
    run_timeout,
    api_timeout,
    max_context_length,
    compression_keep_recent,
    max_retries,
    studio_url,
    initial_message,
    readonly_labels,
    reasoning_effort,
    preserve_thinking,
    supervisor_mode,
    heartbeat_interval_sec,
    dry_run,
    reset,
    set_id,
    std_ids,
    std_ids_file,
    limit,
    base_url,
    pdfs_dir,
    data_dir,
    source_file,
):
    """一键模式：按需 bootstrap workspace 数据后运行 agentic-extract。"""
    from .api import run_agentic_extract_auto
    from .config import resolve_settings

    _ensure_runtime_flags_are_valid(dry_run=dry_run, reset=reset)

    prepare = _build_prepare_spec(
        set_id=set_id,
        std_ids=std_ids,
        std_ids_file=std_ids_file,
        limit=limit,
        base_url=base_url,
        pdfs_dir=pdfs_dir,
        data_dir=data_dir,
        source_file=source_file,
    )
    settings_overrides = _build_settings_overrides(
        model=model,
        api_base=api_base,
        api_key=api_key,
        supervisor_model=supervisor_model,
        business_model=business_model,
        dev_model=dev_model,
        budget=budget,
        max_iterations=max_iterations,
        agent_max_iters=agent_max_iters,
        supervisor_max_iters=supervisor_max_iters,
        business_max_iters=business_max_iters,
        dev_max_iters=dev_max_iters,
        target_accuracy=target_accuracy,
        run_timeout=run_timeout,
        api_timeout=api_timeout,
        max_retries=max_retries,
        studio_url=studio_url,
        max_context_length=max_context_length,
        compression_keep_recent=compression_keep_recent,
        initial_message=initial_message,
        readonly_labels=readonly_labels,
        reasoning_effort=reasoning_effort,
        preserve_thinking=preserve_thinking,
        supervisor_mode=supervisor_mode,
    )

    try:
        preview_settings = resolve_settings(
            workspace,
            config_path=config_path,
            overrides={
                **settings_overrides,
                "workspace": workspace,
            },
        )
    except ValueError as exc:
        _abort_with_error(str(exc))

    if budget:
        setattr(preview_settings, "_budget_profile", budget)
    _print_budget_summary(preview_settings)

    if reset:
        _reset_runtime_state_for_cli(workspace)

    try:
        result = run_agentic_extract_auto(
            workspace,
            prepare=prepare,
            config_path=config_path,
            settings_overrides=settings_overrides,
            dry_run=dry_run,
            reset=False,
            on_event=_print_progress_event,
            heartbeat_interval_sec=heartbeat_interval_sec,
        )
    except ValueError as exc:
        _abort_with_error(str(exc))

    _print_run_summary(result)


@cli.command()
@click.option("--workspace", default="workspace", help="工作目录")
@click.option("--from-iteration", "from_iter", type=int, required=True, help="从哪个迭代恢复")
def resume(workspace, from_iter):
    """从指定迭代恢复运行（创建新分支）"""
    import subprocess
    from pathlib import Path
    from .state import StateManager

    ws = Path(workspace)
    if not ws.exists():
        click.echo(f"错误：workspace 不存在: {ws}", err=True)
        raise click.Abort()

    state = StateManager(ws)
    record = state.get_iteration_record(from_iter)
    if record is None:
        click.echo(f"错误：迭代 {from_iter} 的记录不存在", err=True)
        raise click.Abort()

    if not record.git_commit_after:
        click.echo(f"错误：迭代 {from_iter} 没有 git commit 记录", err=True)
        raise click.Abort()

    branch_name = f"resume-from-iter-{from_iter}"
    click.echo(f"从迭代 {from_iter} 恢复 (commit: {record.git_commit_after[:8]})")
    click.echo(f"创建分支: {branch_name}")

    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name, record.git_commit_after],
            cwd=str(ws),
            check=True,
            capture_output=True,
            text=True,
        )
        click.echo(f"已切换到分支 {branch_name}")
        click.echo("可以运行 agentic-extract run 继续")
    except subprocess.CalledProcessError as e:
        click.echo(f"git 操作失败: {e.stderr}", err=True)
        raise click.Abort()


@cli.command(name="export-prompts")
@click.option("--agent", type=click.Choice(["supervisor", "business", "dev", "all"]), default="all", help="导出哪个 agent 的 prompt")
@click.option("--output", default="local/prompts/", help="输出目录（使用 - 输出到 stdout）")
@click.option("--target-accuracy", default=0.99, type=float, help="目标准确率 (0-1)")
@click.option("--readonly-labels", is_flag=True, help="标注只读模式")
@click.option("--model", help="模型名称（记录到 metadata）")
@click.option("--api-base", help="API 地址（记录到 metadata）")
def export_prompts(agent, output, target_accuracy, readonly_labels, model, api_base):
    """导出 agent 系统提示词"""
    import json
    from datetime import datetime
    from pathlib import Path
    from .prompts.assembly import (
        assemble_supervisor_prompt,
        assemble_business_prompt,
        assemble_dev_prompt,
    )

    agents_to_export = ["supervisor", "business", "dev"] if agent == "all" else [agent]

    results = {}
    for agent_name in agents_to_export:
        if agent_name == "supervisor":
            prompt, parts = assemble_supervisor_prompt(target_accuracy, readonly_labels)
        elif agent_name == "business":
            prompt, parts = assemble_business_prompt(readonly_labels)
        else:  # dev
            prompt, parts = assemble_dev_prompt()

        results[agent_name] = {
            "prompt": prompt,
            "parts": parts,
            "length": len(prompt),
        }

    if output == "-":
        # 输出到 stdout（纯文本）
        if len(results) == 1:
            click.echo(list(results.values())[0]["prompt"])
        else:
            for agent_name, data in results.items():
                click.echo(f"\n\n=== {agent_name} ===\n\n")
                click.echo(data["prompt"])
    else:
        # 输出到文件
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        for agent_name, data in results.items():
            # 构建 markdown 内容
            md_lines = [
                f"# {agent_name.capitalize()}Agent System Prompt",
                "",
                "<!-- 以下为元数据，用于记录 prompt 的组装信息和参数 -->",
                "",
                "## Assembly Order",
                "",
            ]
            for i, part in enumerate(data["parts"], 1):
                md_lines.append(f"{i}. **{part.name}** ({part.length} chars) — `{part.source}`")

            md_lines.extend([
                "",
                "## Parameters",
                "",
                f"- target_accuracy: {target_accuracy} ({target_accuracy * 100:.0f}%)",
                f"- readonly_labels: {readonly_labels}",
            ])

            if model:
                md_lines.append(f"- model: {model}")
            if api_base:
                md_lines.append(f"- api_base: {api_base}")

            md_lines.extend([
                "",
                "## Statistics",
                "",
                f"- Total length: {data['length']} characters",
                f"- Generated at: {datetime.now().isoformat()}",
                "",
                "<!-- 元数据结束，以下为实际的系统提示词内容 -->",
                "",
                "---",
                "",
                data["prompt"],
            ])

            (output_dir / f"{agent_name}.md").write_text("\n".join(md_lines), encoding="utf-8")

        # 写入 metadata.json
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "parameters": {
                "target_accuracy": target_accuracy,
                "readonly_labels": readonly_labels,
                "model": model,
                "api_base": api_base,
            },
            "agents": {
                agent_name: {
                    "length": data["length"],
                    "parts": [
                        {"name": p.name, "source": p.source, "length": p.length}
                        for p in data["parts"]
                    ],
                }
                for agent_name, data in results.items()
            },
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        click.echo(f"已导出到 {output_dir}/")
        for agent_name in results:
            click.echo(f"  - {agent_name}.md")
        click.echo("  - metadata.json")


if __name__ == "__main__":
    cli()
