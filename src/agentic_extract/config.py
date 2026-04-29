"""agentic-extract 配置管理。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class AgenticExtractConfig(BaseModel):
    """agentic-extract 配置"""

    # LLM 配置
    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    api_timeout: float = 300.0

    # 各 agent 模型（默认同 model）
    supervisor_model: str | None = None
    business_model: str | None = None
    dev_model: str | None = None

    # 工作目录
    workspace: str = "workspace"

    # 迭代控制
    max_iterations: int = 10
    target_accuracy: float = 0.99
    run_timeout: float | None = None

    # Agent 并发
    max_retries: int = 0

    # 代码工具
    enabled_tools: list[str] | None = None

    # 上下文压缩
    max_context_length: int = 128000
    compression_keep_recent: int = 10

    # AgentScope Studio
    studio_url: str | None = None

    # 初始消息
    initial_message: str | None = None

    # 标注只读
    readonly_labels: bool = False

    # Reasoning effort (for o1/o3 models)
    reasoning_effort: str | None = None

    # 标注 agent 配置（默认使用 business agent 的配置）
    labeling_model: str | None = None
    labeling_api_base: str | None = None
    labeling_api_key: str | None = None

    # 保留 thinking blocks（防止 formatter 丢弃导致 agent 丢失推理上下文）
    preserve_thinking: bool = False

    # Supervisor 模式：simple=无工具纯决策，默认使用 simple
    supervisor_mode: str = "simple"

    # 使用 OpenAI Responses API（替代 Chat Completions API）
    use_responses_api: bool = False

    # Agent 单次调用最大迭代次数（reasoning-acting 循环）
    agent_max_iters: int = 25
    supervisor_max_iters: int | None = None
    business_max_iters: int | None = None
    dev_max_iters: int | None = None

    def get_agent_max_iters(self, agent: Literal["supervisor", "business", "dev"]) -> int:
        """Return the effective max_iters budget for a specific agent."""
        specific_budget = {
            "supervisor": self.supervisor_max_iters,
            "business": self.business_max_iters,
            "dev": self.dev_max_iters,
        }[agent]
        return specific_budget if specific_budget is not None else self.agent_max_iters

    def execution_budget(self) -> dict[str, int | float | None]:
        """Return a display-friendly execution budget snapshot."""
        return {
            "workflow_max_iterations": self.max_iterations,
            "agent_max_iters": self.agent_max_iters,
            "supervisor_max_iters": self.get_agent_max_iters("supervisor"),
            "business_max_iters": self.get_agent_max_iters("business"),
            "dev_max_iters": self.get_agent_max_iters("dev"),
            "run_timeout": self.run_timeout,
        }


CONFIG_FILENAME = ".agentic-extract.json"
GLOBAL_CONFIG_PATH = Path.home() / ".config" / "agentic-extract" / "config.json"
_SECRET_FIELDS = {"api_key", "labeling_api_key"}


def _load_json_config(path: Path) -> dict[str, Any]:
    """加载 JSON 配置文件"""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _mask_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def mask_config_dict(config: AgenticExtractConfig | dict[str, Any]) -> dict[str, Any]:
    """Return a safe-to-print config dict with secrets masked."""
    payload = config.model_dump() if isinstance(config, BaseModel) else dict(config)
    for key in _SECRET_FIELDS:
        if key in payload:
            payload[key] = _mask_secret(payload.get(key))
    return payload


def _normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _find_repo_root(start: Path) -> Path:
    current = start
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return current.parents[-1] if current.parents else current


def _workspace_config_paths(workspace: str | Path | None) -> list[Path]:
    if not workspace:
        return []

    workspace_path = _normalize_path(workspace)
    repo_root = _find_repo_root(workspace_path)

    search_dirs: list[Path] = []
    current = workspace_path
    while True:
        search_dirs.append(current)
        if current == repo_root or current.parent == current:
            break
        current = current.parent

    return [directory / CONFIG_FILENAME for directory in reversed(search_dirs)]


def _apply_env_overrides(config_dict: dict[str, Any]) -> list[str]:
    env_mapping = {
        "AE_MODEL": "model",
        "AE_API_BASE": "api_base",
        "AE_API_KEY": "api_key",
        "AE_API_TIMEOUT": "api_timeout",
        "AE_SUPERVISOR_MODEL": "supervisor_model",
        "AE_BUSINESS_MODEL": "business_model",
        "AE_DEV_MODEL": "dev_model",
        "AE_WORKSPACE": "workspace",
        "AE_MAX_ITERATIONS": "max_iterations",
        "AE_TARGET_ACCURACY": "target_accuracy",
        "AE_RUN_TIMEOUT": "run_timeout",
        "AE_MAX_RETRIES": "max_retries",
        "AE_MAX_CONTEXT_LENGTH": "max_context_length",
        "AE_COMPRESSION_KEEP_RECENT": "compression_keep_recent",
        "AE_STUDIO_URL": "studio_url",
        "AE_INITIAL_MESSAGE": "initial_message",
        "AE_REASONING_EFFORT": "reasoning_effort",
        "AE_LABELING_MODEL": "labeling_model",
        "AE_LABELING_API_BASE": "labeling_api_base",
        "AE_LABELING_API_KEY": "labeling_api_key",
        "AE_AGENT_MAX_ITERS": "agent_max_iters",
        "AE_SUPERVISOR_MAX_ITERS": "supervisor_max_iters",
        "AE_BUSINESS_MAX_ITERS": "business_max_iters",
        "AE_DEV_MAX_ITERS": "dev_max_iters",
    }

    applied_env_keys: list[str] = []
    for env_key, config_key in env_mapping.items():
        if env_key not in os.environ:
            continue

        value = os.environ[env_key]
        if config_key in ["api_timeout", "target_accuracy", "run_timeout"]:
            value = float(value) if value else None
        elif config_key in [
            "max_iterations",
            "max_retries",
            "max_context_length",
            "compression_keep_recent",
            "agent_max_iters",
            "supervisor_max_iters",
            "business_max_iters",
            "dev_max_iters",
        ]:
            value = int(value)

        config_dict[config_key] = value
        applied_env_keys.append(env_key)

    return applied_env_keys


def _resolve_config_dict(
    workspace: str | None = None,
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    include_env: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config_dict = AgenticExtractConfig().model_dump()
    trace: dict[str, Any] = {
        "global_config_path": str(GLOBAL_CONFIG_PATH),
        "cwd_config_path": str(Path.cwd() / CONFIG_FILENAME),
        "workspace_config_paths": [str(path) for path in _workspace_config_paths(workspace)],
        "explicit_config_path": str(_normalize_path(config_path)) if config_path else None,
        "applied_files": [],
        "applied_env": [],
        "applied_override_keys": [],
    }

    file_paths: list[Path] = [GLOBAL_CONFIG_PATH, Path.cwd() / CONFIG_FILENAME]
    file_paths.extend(_workspace_config_paths(workspace))
    if config_path is not None:
        file_paths.append(_normalize_path(config_path))

    seen_paths: set[Path] = set()
    for path in file_paths:
        normalized = path.resolve()
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        payload = _load_json_config(normalized)
        if not payload:
            continue
        config_dict.update(payload)
        trace["applied_files"].append(str(normalized))

    if include_env:
        trace["applied_env"] = _apply_env_overrides(config_dict)

    if overrides:
        config_dict.update(overrides)
        trace["applied_override_keys"] = sorted(overrides.keys())

    return config_dict, trace


def resolve_config(
    workspace: str | None = None,
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    include_env: bool = True,
) -> AgenticExtractConfig:
    """Resolve config from defaults, files, env, and explicit overrides."""
    config_dict, _trace = _resolve_config_dict(
        workspace,
        config_path=config_path,
        overrides=overrides,
        include_env=include_env,
    )
    return AgenticExtractConfig(**config_dict)


def resolve_settings(
    workspace: str | None = None,
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    include_env: bool = True,
) -> "AgenticExtractSettings":
    """Resolve and validate settings-compatible config."""
    config_dict, _trace = _resolve_config_dict(
        workspace,
        config_path=config_path,
        overrides=overrides,
        include_env=include_env,
    )
    return AgenticExtractSettings(**config_dict)


def explain_config(
    workspace: str | None = None,
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    include_env: bool = True,
) -> dict[str, Any]:
    """Explain how the final config was resolved, with secrets masked."""
    config_dict, trace = _resolve_config_dict(
        workspace,
        config_path=config_path,
        overrides=overrides,
        include_env=include_env,
    )
    trace["resolved_config"] = mask_config_dict(config_dict)
    return trace


def load_config(
    workspace: str | None = None,
    *,
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    include_env: bool = True,
) -> AgenticExtractConfig:
    """兼容入口：加载配置。"""
    return resolve_config(
        workspace,
        config_path=config_path,
        overrides=overrides,
        include_env=include_env,
    )


class AgenticExtractSettings(AgenticExtractConfig):
    """兼容旧代码的别名"""

    def validate_required(self) -> None:
        """验证必填字段"""
        if not self.model:
            raise ValueError("请提供 --model 或设置 AE_MODEL 环境变量")
        if not self.api_base:
            raise ValueError("请提供 --api-base 或设置 AE_API_BASE 环境变量")
        if not self.api_key:
            raise ValueError("请提供 --api-key 或设置 AE_API_KEY 环境变量")
