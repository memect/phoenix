"""Main runner for the public agentic_extract Python API."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

from agentscope.message import Msg

from extract_agent_common.workspace import create_workspace, setup_environment

from .agents import create_business_agent, create_dev_agent, create_supervisor
from .config import AgenticExtractSettings
from .evaluate import format_eval_for_supervisor, run_xdev_eval
from .runtime import RunRecorder, run_in_thread_with_heartbeat, run_with_heartbeat, runtime_scope
from .state import StateManager
from .supervisor import get_supervisor_decision, probe_structured_output, validate_api_connectivity
from .types import EvaluationSummary, RunRequest, RunResult
from .workspace import ensure_workspace_ready, get_workspace_status, init_workspace

logger = logging.getLogger(__name__)


def request_to_settings(request: RunRequest) -> AgenticExtractSettings:
    """Convert the public request model to the internal settings model."""
    payload = request.model_dump()
    payload.pop("heartbeat_interval_sec", None)
    payload.pop("dry_run", None)
    return AgenticExtractSettings(**payload)


def _evaluation_to_summary(evaluation) -> EvaluationSummary | None:
    if evaluation is None:
        return None
    return EvaluationSummary(
        accuracy=evaluation.accuracy,
        field_average=evaluation.field_average,
        doc_count=evaluation.doc_count,
        error_count=evaluation.error_count,
    )


def _create_agents(settings: AgenticExtractSettings):
    assert settings.model is not None
    assert settings.api_base is not None
    assert settings.api_key is not None

    model = settings.model
    supervisor_model = settings.supervisor_model or model
    business_model = settings.business_model or model
    dev_model = settings.dev_model or model
    supervisor_max_iters = settings.get_agent_max_iters("supervisor")
    business_max_iters = settings.get_agent_max_iters("business")
    dev_max_iters = settings.get_agent_max_iters("dev")

    supervisor = create_supervisor(
        model=supervisor_model,
        api_base=settings.api_base,
        api_key=settings.api_key,
        target_accuracy=settings.target_accuracy,
        timeout=settings.api_timeout,
        max_retries=settings.max_retries,
        max_context_length=settings.max_context_length,
        compression_keep_recent=settings.compression_keep_recent,
        readonly_labels=settings.readonly_labels,
        reasoning_effort=settings.reasoning_effort,
        preserve_thinking=settings.preserve_thinking,
        simple_mode=(settings.supervisor_mode == "simple"),
        use_responses_api=settings.use_responses_api,
        max_iters=supervisor_max_iters,
    )
    business_agent = create_business_agent(
        model=business_model,
        api_base=settings.api_base,
        api_key=settings.api_key,
        timeout=settings.api_timeout,
        max_retries=settings.max_retries,
        max_context_length=settings.max_context_length,
        compression_keep_recent=settings.compression_keep_recent,
        readonly_labels=settings.readonly_labels,
        reasoning_effort=settings.reasoning_effort,
        preserve_thinking=settings.preserve_thinking,
        labeling_model=settings.labeling_model,
        labeling_api_base=settings.labeling_api_base,
        labeling_api_key=settings.labeling_api_key,
        use_responses_api=settings.use_responses_api,
        max_iters=business_max_iters,
    )
    dev_agent = create_dev_agent(
        model=dev_model,
        api_base=settings.api_base,
        api_key=settings.api_key,
        timeout=settings.api_timeout,
        max_retries=settings.max_retries,
        max_context_length=settings.max_context_length,
        compression_keep_recent=settings.compression_keep_recent,
        reasoning_effort=settings.reasoning_effort,
        preserve_thinking=settings.preserve_thinking,
        business_agent=business_agent,
        use_responses_api=settings.use_responses_api,
        max_iters=dev_max_iters,
    )
    return {
        "supervisor": supervisor,
        "business_agent": business_agent,
        "dev_agent": dev_agent,
    }


async def _run_dry_run(
    settings: AgenticExtractSettings,
    recorder: RunRecorder,
    *,
    original_request: RunRequest | None = None,
) -> RunResult:
    models_to_check = {"default": settings.model}
    if settings.supervisor_model and settings.supervisor_model != settings.model:
        models_to_check["supervisor"] = settings.supervisor_model
    if settings.business_model and settings.business_model != settings.model:
        models_to_check["business"] = settings.business_model
    if settings.dev_model and settings.dev_model != settings.model:
        models_to_check["dev"] = settings.dev_model

    with runtime_scope(recorder=recorder, phase="probe"):
        await recorder.start_run(
            message="agentic_extract dry-run started",
            data={
                "max_iterations": settings.max_iterations,
                "target_accuracy": settings.target_accuracy,
                **settings.execution_budget(),
            },
        )
        await recorder.start_phase("probe", message="dry-run connectivity checks")

        all_ok = True
        for label, model in models_to_check.items():
            result = validate_api_connectivity(
                model=model,
                api_base=settings.api_base,
                api_key=settings.api_key,
                timeout=min(settings.api_timeout, 30.0),
            )
            if result.usage is not None:
                recorder.record_usage(result.usage)
            all_ok = all_ok and result.ok

        await recorder.finish_phase(
            "probe",
            message="dry-run completed",
            data={"all_ok": all_ok},
        )
        if not all_ok:
            raise ValueError("dry-run API 连通性验证失败")
        return await recorder.finish_run(status="completed", message="dry-run completed")


async def run_settings_async(
    settings: AgenticExtractSettings,
    *,
    dry_run: bool = False,
    on_event=None,
    heartbeat_interval_sec: float = 10.0,
) -> RunResult:
    """Run agentic_extract using resolved settings and runtime controls."""
    settings.validate_required()

    recorder = RunRecorder(
        on_event=on_event,
        heartbeat_interval_sec=heartbeat_interval_sec,
    )

    if dry_run:
        return await _run_dry_run(settings, recorder)

    completed = False
    exit_reason = "运行中断"

    with runtime_scope(recorder=recorder):
        await recorder.start_run(
            message="agentic_extract run started",
            data={
                "max_iterations": settings.max_iterations,
                "target_accuracy": settings.target_accuracy,
                **settings.execution_budget(),
            },
        )

        if settings.studio_url:
            import agentscope

            agentscope.init(studio_url=settings.studio_url)

        await recorder.start_phase("setup", message="initializing workspace and agents")
        workspace_path = create_workspace(settings.workspace)
        setup_environment(workspace_path)
        init_workspace(workspace_path)
        ensure_workspace_ready(workspace_path)

        state = StateManager(workspace_path)
        state.init()

        agents = _create_agents(settings)
        state.load_all_agents(agents)
        supervisor = agents["supervisor"]
        business_agent = agents["business_agent"]
        dev_agent = agents["dev_agent"]
        await recorder.finish_phase("setup", message="setup completed")

        use_structured = False
        await recorder.start_phase("probe", message="probing supervisor structured output support")
        with runtime_scope(phase="probe"):
            probe_result = await probe_structured_output(
                settings.supervisor_model or settings.model,
                settings.api_base,
                settings.api_key,
            )
            if probe_result.usage is not None:
                recorder.record_usage(probe_result.usage)
            use_structured = probe_result.supported
        await recorder.finish_phase(
            "probe",
            message="probe completed",
            data={"use_structured": use_structured},
        )

        if settings.initial_message:
            await supervisor(
                Msg(name="user", content=settings.initial_message, role="user")
            )

        start_timeout_monotonic = __import__("time").monotonic()
        business_max_iters = settings.get_agent_max_iters("business")
        dev_max_iters = settings.get_agent_max_iters("dev")
        consecutive_dev_calls = 0
        warn_threshold = 3
        hard_threshold = 6

        try:
            for _ in range(settings.max_iterations):
                iteration_num = state.get_iteration_number() + 1
                await recorder.start_iteration(iteration_num, message=f"iteration {iteration_num} started")
                git_before = state.get_git_head()

                recent = state.get_recent_summary()
                msg_parts = [f"当前迭代: {iteration_num}\n\n最近迭代:\n{recent}"]
                msg_parts.append(f"\nWorkspace 状态:\n{get_workspace_status(workspace_path)}")
                if consecutive_dev_calls >= hard_threshold:
                    msg_parts.append(
                        f"\n⚠️ 已连续 {consecutive_dev_calls} 轮 call_dev 未评估。"
                        " 必须先 evaluate 确认当前准确率，再决定下一步。"
                    )
                elif consecutive_dev_calls >= warn_threshold:
                    msg_parts.append(
                        f"\n⚠️ 已连续 {consecutive_dev_calls} 轮 call_dev 未评估，"
                        "建议下一步 evaluate 确认效果。"
                    )
                msg_parts.append("\n请根据以上状态，按决策规则做出决策。")

                decision = None
                iteration_summary = None
                iteration_error = None
                evaluation_snapshot = None

                await recorder.start_step("supervisor", message="waiting for supervisor decision")
                try:
                    with runtime_scope(iteration=iteration_num, step="supervisor"):
                        decision = await run_with_heartbeat(
                            get_supervisor_decision(
                                supervisor,
                                Msg(name="user", content="\n".join(msg_parts), role="user"),
                                use_structured,
                            ),
                            recorder=recorder,
                            message="supervisor 仍在运行",
                        )
                        await recorder.emit_supervisor_decided(
                            action=decision.action,
                            message=decision.task[:120] if decision.task else None,
                        )
                    await recorder.finish_step("supervisor", message="supervisor decision ready")
                except Exception as exc:
                    await recorder.finish_step("supervisor", status="failed", message=str(exc))
                    raise

                assert decision is not None

                agent_output = ""
                if decision.action == "done":
                    completed = True
                    exit_reason = f"supervisor 判断完成: {decision.reasoning}"
                    git_after = state.git_commit(
                        f"iter-{iteration_num}: done - {decision.reasoning[:50]}"
                    )
                    state.save_all_agents(agents)
                    iteration_summary = decision.reasoning or "done"
                    iteration_result = await recorder.finish_iteration(
                        action=decision.action,
                        summary=iteration_summary,
                    )
                    state.record_iteration(
                        decision=decision,
                        git_commit_before=git_before,
                        git_commit_after=git_after,
                        started_at=iteration_result.started_at,
                        finished_at=iteration_result.finished_at,
                        duration_sec=iteration_result.duration_sec,
                        token_usage=iteration_result.token_usage,
                        summary=iteration_result.summary,
                        error=iteration_result.error,
                    )
                    break

                if decision.action == "call_business":
                    await recorder.start_step("business_agent", message=decision.task)
                    result_msg = None
                    try:
                        with runtime_scope(iteration=iteration_num, step="business_agent"):
                            result_msg = await run_with_heartbeat(
                                business_agent(
                                    Msg(name="Supervisor", content=decision.task, role="user")
                                ),
                                recorder=recorder,
                                message="business_agent 仍在运行",
                            )
                        agent_output = result_msg.get_text_content() or ""
                        if (
                            result_msg
                            and isinstance(getattr(result_msg, "metadata", None), dict)
                            and result_msg.metadata.get("_max_iters_reached")
                        ):
                            await supervisor.observe(
                                Msg(
                                    name="system",
                                    content=(
                                        f"BusinessAgent 到达 max_iters={business_max_iters} 限制，"
                                        "任务可能未完成。请考虑拆分任务或调整策略。"
                                    ),
                                    role="system",
                                )
                            )
                        await supervisor.observe(
                            Msg(name="BusinessAgent", content=agent_output, role="user")
                        )
                        consecutive_dev_calls = 0
                        iteration_summary = "call_business completed"
                        await recorder.finish_step("business_agent", message="business_agent completed")
                    except Exception as exc:
                        logger.exception("BusinessAgent 执行异常")
                        agent_output = f"BusinessAgent 执行异常: {exc}"
                        iteration_error = str(exc)
                        iteration_summary = "call_business failed"
                        await recorder.finish_step(
                            "business_agent",
                            status="failed",
                            message=str(exc),
                        )

                elif decision.action == "evaluate":
                    await recorder.start_step("evaluate", message="running xdev eval")
                    try:
                        with runtime_scope(iteration=iteration_num, step="evaluate"):
                            evaluation_snapshot = await run_in_thread_with_heartbeat(
                                run_xdev_eval,
                                workspace_path,
                                recorder=recorder,
                                message="evaluate 仍在运行",
                            )
                        if evaluation_snapshot:
                            agent_output = format_eval_for_supervisor(evaluation_snapshot)
                            iteration_summary = f"evaluate accuracy={evaluation_snapshot.accuracy:.1%}"
                        else:
                            agent_output = "评估失败或无结果"
                            iteration_summary = agent_output
                        await supervisor.observe(
                            Msg(name="Evaluator", content=agent_output, role="user")
                        )
                        consecutive_dev_calls = 0
                        await recorder.finish_step("evaluate", message=iteration_summary)
                    except Exception as exc:
                        logger.exception("evaluate 执行异常")
                        agent_output = f"评估执行异常: {exc}"
                        iteration_error = str(exc)
                        iteration_summary = "evaluate failed"
                        await recorder.finish_step("evaluate", status="failed", message=str(exc))

                elif decision.action == "call_dev":
                    await recorder.start_step("dev_agent", message=decision.task)
                    schema_path = workspace_path / ".xdev" / "schema.json"
                    dev_task = decision.task
                    if schema_path.exists():
                        try:
                            schema_data = __import__("json").loads(schema_path.read_text(encoding="utf-8"))
                            cur_schema = list(schema_data.get("data", {}).keys())
                        except Exception:
                            cur_schema = []
                        if cur_schema:
                            dev_task = (
                                "[当前 Schema 字段] extract() 返回的 key 必须与以下字段名逐字匹配"
                                "（schema 可能被 BusinessAgent 更新，以最新为准）:\n"
                                f"{', '.join(cur_schema)}\n\n{decision.task}"
                            )
                    result_msg = None
                    try:
                        with runtime_scope(iteration=iteration_num, step="dev_agent"):
                            result_msg = await run_with_heartbeat(
                                dev_agent(Msg(name="Supervisor", content=dev_task, role="user")),
                                recorder=recorder,
                                message="dev_agent 仍在运行",
                            )
                        agent_output = result_msg.get_text_content() or ""
                        if (
                            result_msg
                            and isinstance(getattr(result_msg, "metadata", None), dict)
                            and result_msg.metadata.get("_max_iters_reached")
                        ):
                            await supervisor.observe(
                                Msg(
                                    name="system",
                                    content=(
                                        f"DevAgent 到达 max_iters={dev_max_iters} 限制，"
                                        "任务可能未完成。请考虑拆分任务或调整策略。"
                                    ),
                                    role="system",
                                )
                            )
                        await supervisor.observe(
                            Msg(name="DevAgent", content=agent_output, role="user")
                        )
                        consecutive_dev_calls += 1
                        iteration_summary = "call_dev completed"
                        await recorder.finish_step("dev_agent", message="dev_agent completed")
                    except Exception as exc:
                        logger.exception("DevAgent 执行异常")
                        agent_output = f"DevAgent 执行异常: {exc}"
                        iteration_error = str(exc)
                        iteration_summary = "call_dev failed"
                        await recorder.finish_step("dev_agent", status="failed", message=str(exc))

                else:
                    iteration_error = f"未知 action: {decision.action}"
                    iteration_summary = iteration_error

                git_after = state.git_commit(
                    f"iter-{iteration_num}: {decision.action} - {decision.task[:50]}"
                )
                state.save_all_agents(agents)
                iteration_result = await recorder.finish_iteration(
                    action=decision.action,
                    evaluation=_evaluation_to_summary(evaluation_snapshot),
                    summary=iteration_summary or decision.action,
                    error=iteration_error,
                )
                state.record_iteration(
                    decision=decision,
                    agent_output=agent_output[:2000],
                    evaluation=evaluation_snapshot,
                    git_commit_before=git_before,
                    git_commit_after=git_after,
                    started_at=iteration_result.started_at,
                    finished_at=iteration_result.finished_at,
                    duration_sec=iteration_result.duration_sec,
                    token_usage=iteration_result.token_usage,
                    summary=iteration_result.summary,
                    error=iteration_result.error,
                )

                if settings.run_timeout:
                    elapsed = __import__("time").monotonic() - start_timeout_monotonic
                    if elapsed > settings.run_timeout:
                        exit_reason = f"运行超时 ({settings.run_timeout:.0f}s)"
                        break
            else:
                exit_reason = f"达到最大迭代次数 ({settings.max_iterations})"
        except KeyboardInterrupt:
            exit_reason = "用户中断"
        except Exception as exc:
            exit_reason = f"异常: {exc}"
            logger.exception("主循环异常")
        finally:
            await recorder.start_phase("finalize", message="finalizing run")
            state.save_all_agents(agents)
            state.git_commit(f"final: {exit_reason[:50]}")
            if completed:
                state.mark_completed()
            else:
                state.mark_failed(exit_reason)
            await recorder.finish_phase("finalize", message="finalize completed")

        status = "completed" if completed else "failed"
        return await recorder.finish_run(
            status=status,
            error=None if completed else exit_reason,
            message=exit_reason,
            data={"workspace": str(Path(settings.workspace))},
        )


async def run_request_async(request: RunRequest) -> RunResult:
    """Compatibility wrapper for legacy RunRequest execution."""
    warnings.warn(
        "RunRequest-based execution is deprecated; pass resolved AgenticExtractSettings "
        "to run_agentic_extract()/run_agentic_extract_async() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    settings = request_to_settings(request)
    return await run_settings_async(
        settings,
        dry_run=request.dry_run,
        on_event=request.on_event,
        heartbeat_interval_sec=request.heartbeat_interval_sec,
    )
