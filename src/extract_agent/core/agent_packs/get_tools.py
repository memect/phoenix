"""
extract_agent.core.agent_packs.get_tools 兼容模块

此模块已废弃，请使用 code_executor.get_tools 代替。
"""

import warnings

warnings.warn(
    "'extract_agent.core.agent_packs.get_tools' is deprecated, "
    "use 'code_executor.get_tools' instead",
    DeprecationWarning,
    stacklevel=2
)

from code_executor.get_tools import create_default_tool_hub, create_default_llm_guide, has_default_tool

__all__ = ["create_default_tool_hub", "create_default_llm_guide", "has_default_tool"]
