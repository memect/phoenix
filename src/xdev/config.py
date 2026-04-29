"""
xdev 配置管理
"""

import json
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class XdevCodeExtractorConfig(BaseModel):
    """xdev -> code-extractor 工具配置透传"""

    # 对应 code_executor.tools.tool_setup.settings.Settings.tool_setup
    tool_setup: dict[str, Any] | None = None
    # 对应 code_executor.tools.tool_setup.settings.Settings.enabled_tools
    enabled_tools: list[str] | None = None


class XdevConfig(BaseModel):
    """xdev 配置"""

    data_dir: str = ".xdev"
    base_url: str = "http://localhost:8008"
    concurrent: int = 16
    eval_concurrent: int = 4
    pdf_parse_concurrent: int = Field(default=1, ge=1)
    memect_api_base: str = "http://localhost:6111/api"
    code_extractor: XdevCodeExtractorConfig | None = None


def _load_json_config(path: Path) -> dict[str, Any]:
    """加载 JSON 配置文件"""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_config() -> XdevConfig:
    """加载配置（优先级：环境变量 > 项目配置 > 全局配置 > 默认值）"""
    # 1. 默认值
    config_dict = XdevConfig().model_dump()

    # 2. 全局配置文件
    global_config_path = Path.home() / ".config" / "xdev" / "config.json"
    global_config = _load_json_config(global_config_path)
    config_dict.update(global_config)

    # 3. 项目配置文件
    project_config_path = Path.cwd() / ".xdev" / "config.json"
    project_config = _load_json_config(project_config_path)
    config_dict.update(project_config)

    # 4. 环境变量（XDEV_ 前缀）
    env_mapping = {
        "XDEV_DATA_DIR": "data_dir",
        "XDEV_BASE_URL": "base_url",
        "XDEV_CONCURRENT": "concurrent",
        "XDEV_EVAL_CONCURRENT": "eval_concurrent",
        "XDEV_PDF_PARSE_CONCURRENT": "pdf_parse_concurrent",
        "XDEV_MEMECT_API_BASE": "memect_api_base",
    }
    for env_key, config_key in env_mapping.items():
        if env_key in os.environ:
            value = os.environ[env_key]
            if config_key in ("concurrent", "eval_concurrent", "pdf_parse_concurrent"):
                value = int(value)
            config_dict[config_key] = value

    return XdevConfig(**config_dict)


def get_data_dir(data_dir: Path | str | None = None) -> Path:
    """获取数据目录路径

    Args:
        data_dir: 指定的数据目录，None 则使用配置值

    Returns:
        数据目录的绝对路径
    """
    if data_dir is None:
        config = load_config()
        data_dir = config.data_dir

    path = Path(data_dir)
    if not path.is_absolute():
        path = Path.cwd() / path

    return path


def ensure_data_dir(data_dir: Path | str | None = None) -> Path:
    """确保数据目录存在

    Args:
        data_dir: 指定的数据目录

    Returns:
        数据目录的绝对路径
    """
    path = get_data_dir(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "data").mkdir(exist_ok=True)
    (path / "data" / "docjson").mkdir(exist_ok=True)
    (path / "data" / "pdf").mkdir(exist_ok=True)
    (path / "labels").mkdir(exist_ok=True)
    return path
