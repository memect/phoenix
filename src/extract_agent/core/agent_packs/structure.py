"""
extract_agent.core.agent_packs.structure 兼容模块

此模块已废弃，请使用 code_executor.structure 代替。
"""

import warnings

warnings.warn(
    "'extract_agent.core.agent_packs.structure' is deprecated, "
    "use 'code_executor.structure' instead",
    DeprecationWarning,
    stacklevel=2
)

from code_executor.structure import Table, Cell

__all__ = ["Table", "Cell"]
