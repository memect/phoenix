"""
迭代状态管理

管理 .agent_state/current.json 和 .agent_state/iterations/iter_NNN.json，
并兼容读取旧版 logs/current.json 与 logs/iterations/iter_NNN.json。
"""

import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .types import TokenUsage, utc_now

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"call_business", "call_dev", "evaluate", "done"}


class SupervisorDecision(BaseModel):
    """supervisor 的决策记录"""
    action: Literal["call_business", "call_dev", "evaluate", "done"] = Field(
        description="下一步操作: call_business/call_dev/evaluate/done",
    )
    reasoning: str = Field(
        default="",
        description="决策理由",
    )
    task: str = Field(
        default="",
        description="具体任务描述（给 agent 的指令）",
    )


class EvaluationSnapshot(BaseModel):
    """评估快照"""
    accuracy: float = 0.0
    field_average: float = 0.0
    doc_count: int = 0
    error_count: int = 0
    error_doc_ids: list[str] = Field(default_factory=list)
    field_accuracies: dict[str, float] = Field(default_factory=dict)
    report_text: str = ""


class IterationRecord(BaseModel):
    """单次迭代记录"""
    iteration: int
    timestamp: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_sec: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    summary: str | None = None
    error: str | None = None
    supervisor_decision: SupervisorDecision
    agent_output: str = ""
    evaluation: EvaluationSnapshot | None = None
    git_commit_before: str = ""
    git_commit_after: str = ""


class CurrentState(BaseModel):
    """当前运行状态（用于恢复）"""
    current_iteration: int = 0
    status: str = "running"  # running / completed / failed
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    total_run_duration_sec: float | None = None
    error: str | None = None
    last_update: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def normalize_legacy_failed_status(self):
        if self.status.startswith("failed:") and not self.error:
            self.error = self.status.split(":", 1)[-1].strip() or None
            self.status = "failed"
        return self


class StateManager:
    """迭代状态管理器"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.agent_memory_dir = workspace / ".agent_state"
        self.iterations_dir = self.agent_memory_dir / "iterations"
        self.current_path = self.agent_memory_dir / "current.json"
        self.legacy_logs_dir = workspace / "logs"
        self.legacy_iterations_dir = self.legacy_logs_dir / "iterations"
        self.legacy_current_path = self.legacy_logs_dir / "current.json"
        self._current: CurrentState | None = None

    def init(self) -> None:
        """初始化 runtime 状态目录结构"""
        self.agent_memory_dir.mkdir(parents=True, exist_ok=True)
        self.iterations_dir.mkdir(parents=True, exist_ok=True)
        if not self.current_path.exists() and not self.legacy_current_path.exists():
            self._save_current(CurrentState())

    @property
    def current(self) -> CurrentState:
        if self._current is None:
            self._current = self._load_current()
        return self._current

    def get_iteration_number(self) -> int:
        """获取当前迭代号"""
        return self.current.current_iteration

    def get_git_head(self) -> str:
        """获取当前 HEAD commit hash"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def git_commit(self, message: str) -> str:
        """执行 git add . && git commit，返回 commit hash"""
        try:
            subprocess.run(
                ["git", "add", "."],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                check=True,
            )

            # 检查是否有变更
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                logger.info("无变更，跳过 commit")
                return self.get_git_head()

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                check=True,
            )
            return self.get_git_head()
        except subprocess.CalledProcessError as e:
            logger.warning("git commit 失败: %s", e.stderr)
            return self.get_git_head()

    def record_iteration(
        self,
        decision: SupervisorDecision,
        agent_output: str = "",
        evaluation: EvaluationSnapshot | None = None,
        git_commit_before: str = "",
        git_commit_after: str = "",
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_sec: float = 0.0,
        token_usage: TokenUsage | None = None,
        summary: str | None = None,
        error: str | None = None,
    ) -> IterationRecord:
        """记录一次迭代"""
        iteration_num = self.current.current_iteration + 1

        record = IterationRecord(
            iteration=iteration_num,
            supervisor_decision=decision,
            started_at=started_at,
            finished_at=finished_at,
            duration_sec=duration_sec,
            token_usage=token_usage or TokenUsage(),
            summary=summary,
            error=error,
            agent_output=agent_output,
            evaluation=evaluation,
            git_commit_before=git_commit_before,
            git_commit_after=git_commit_after,
        )

        # 保存 iteration 文件
        iter_path = self.iterations_dir / f"iter_{iteration_num:03d}.json"
        iter_path.write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # 更新 current.json
        self._current = CurrentState(
            current_iteration=iteration_num,
            status="running",
            started_at=self.current.started_at,
            error=None,
        )
        self._save_current(self._current)

        return record

    def mark_completed(self) -> None:
        """标记运行完成"""
        finished_at = utc_now()
        self._current = CurrentState(
            current_iteration=self.current.current_iteration,
            status="completed",
            started_at=self.current.started_at,
            finished_at=finished_at,
            total_run_duration_sec=self._duration_from_started_at(
                self.current.started_at,
                finished_at,
            ),
        )
        self._save_current(self._current)

    def mark_failed(self, reason: str = "") -> None:
        """标记运行失败"""
        finished_at = utc_now()
        self._current = CurrentState(
            current_iteration=self.current.current_iteration,
            status="failed",
            started_at=self.current.started_at,
            finished_at=finished_at,
            total_run_duration_sec=self._duration_from_started_at(
                self.current.started_at,
                finished_at,
            ),
            error=reason or None,
        )
        self._save_current(self._current)

    def get_iteration_record(self, n: int) -> IterationRecord | None:
        """读取指定迭代的记录"""
        iter_path = self._get_existing_iteration_path(n)
        if not iter_path.exists():
            return None
        data = json.loads(iter_path.read_text(encoding="utf-8"))
        return IterationRecord.model_validate(data)

    def get_recent_summary(self, n: int = 5) -> str:
        """获取最近 N 次迭代的摘要（含准确率趋势）"""
        current_iter = self.current.current_iteration
        if current_iter == 0:
            return "尚未开始迭代。"

        lines = []
        accuracies: list[tuple[int, float]] = []
        start = max(1, current_iter - n + 1)
        for i in range(start, current_iter + 1):
            record = self.get_iteration_record(i)
            if record:
                decision = record.supervisor_decision
                eval_str = ""
                if record.evaluation:
                    eval_str = f" | 准确率: {record.evaluation.accuracy:.1%}"
                    accuracies.append((i, record.evaluation.accuracy))
                lines.append(
                    f"iter {i}: {decision.action} - {decision.task[:60]}{eval_str}"
                )

        # 准确率趋势
        if len(accuracies) >= 2:
            first_iter, first_acc = accuracies[0]
            last_iter, last_acc = accuracies[-1]
            delta = last_acc - first_acc
            lines.append(
                f"\n准确率趋势: iter{first_iter} {first_acc:.1%} → "
                f"iter{last_iter} {last_acc:.1%} (Δ{delta:+.1%})"
            )

        return "\n".join(lines) if lines else "无迭代记录。"

    def _load_current(self) -> CurrentState:
        if self.current_path.exists():
            data = json.loads(self.current_path.read_text(encoding="utf-8"))
            return CurrentState.model_validate(data)
        if self.legacy_current_path.exists():
            data = json.loads(self.legacy_current_path.read_text(encoding="utf-8"))
            return CurrentState.model_validate(data)
        return CurrentState()

    def _save_current(self, state: CurrentState) -> None:
        state.last_update = utc_now()
        self.current_path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _get_existing_iteration_path(self, n: int) -> Path:
        current_path = self.iterations_dir / f"iter_{n:03d}.json"
        if current_path.exists():
            return current_path
        return self.legacy_iterations_dir / f"iter_{n:03d}.json"

    @staticmethod
    def _duration_from_started_at(
        started_at: datetime | None,
        finished_at: datetime | None,
    ) -> float | None:
        if started_at is None or finished_at is None:
            return None
        return max((finished_at - started_at).total_seconds(), 0.0)

    # ------------------------------------------------------------------
    # Agent 记忆持久化
    # ------------------------------------------------------------------

    def save_agent_memory(self, agent_name: str, agent: Any) -> None:
        """保存 agent 的 state_dict 到磁盘"""
        path = self.agent_memory_dir / f"{agent_name}.json"
        try:
            state = agent.state_dict()
            path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("保存 %s 记忆失败: %s", agent_name, e)

    def load_agent_memory(self, agent_name: str, agent: Any) -> bool:
        """从磁盘恢复 agent 的 state_dict，返回是否成功"""
        path = self.agent_memory_dir / f"{agent_name}.json"
        if not path.exists():
            return False
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            agent.load_state_dict(state, strict=False)
            logger.info("恢复 %s 记忆成功", agent_name)
            return True
        except Exception as e:
            logger.warning("恢复 %s 记忆失败: %s", agent_name, e)
            return False

    def save_all_agents(self, agents: dict[str, Any]) -> None:
        """保存所有 agent 记忆"""
        for name, agent in agents.items():
            self.save_agent_memory(name, agent)

    def load_all_agents(self, agents: dict[str, Any]) -> None:
        """恢复所有 agent 记忆"""
        for name, agent in agents.items():
            if self.load_agent_memory(name, agent):
                logger.info("恢复 %s 记忆", name)
            else:
                logger.info("%s 无历史记忆", name)
