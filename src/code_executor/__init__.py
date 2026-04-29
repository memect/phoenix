"""
Code Executor Module

提供代码执行功能，包括：
- execute(): 统一的提取执行接口
- batch_execute(): 批量执行提取
- to_plain_article(): DocJSON 转换
- Table, Cell: 结构化数据类
- NER 子模块: 命名实体识别
- Tools 子模块: 工具集
"""

# 核心接口
from .executor import (
    execute,  # 统一执行接口
    create_input, 
    get_input_mode, 
    detect_input_mode,
)

# 向后兼容接口（已废弃）
from .executor import (
    do_extract,  # deprecated: use execute(program=..., data=...)
    do_extract_with_output,  # deprecated: use execute(..., capture_output=True)
    execute_from_file,  # deprecated: use execute(program_path=..., data=...)
    execute_from_workspace,  # deprecated: use execute(workspace=..., data=...)
    execute_from_file_on_docjson,  # deprecated: use execute(program_path=..., docjson=...)
    execute_from_workspace_on_docjson,  # deprecated: use execute(workspace=..., docjson=...)
)

from .api import (
    batch_execute, 
    execute_on_docjson, 
    batch_execute_on_docjsons,
    execute_workspace_on_docjson,  # deprecated: use execute_on_docjson(docjson, workspace=...)
    batch_execute_workspace_on_docjsons,
)
from .loader import to_plain_article
from .structure import Table, Cell
from .get_tools import create_default_tool_hub
from .utils import get_structure_code, get_llm_context
from .run_config import eval_config, EvalResult

# NER 子模块导出
from .ner import NERPattern, Match, StringWithNER, NerApi

# Tools 子模块导出
from .tools import (
    setup_code_tools,
    LLMSelectTool,
    ExtractTool,
    NerTool,
    NerRegexTool,
    create_default_llm_guide,
    has_default_tool,
    ToolHub,
    ToolRegistry,
    tool,
)

__all__ = [
    # 核心执行函数
    'execute',
    'create_input',
    'get_input_mode',
    'detect_input_mode',
    'batch_execute',
    'execute_on_docjson',
    'batch_execute_on_docjsons',
    'to_plain_article',
    'eval_config',
    'EvalResult',
    
    # 已废弃接口（向后兼容）
    'do_extract',  # deprecated
    'do_extract_with_output',  # deprecated
    'execute_from_file',  # deprecated
    'execute_from_workspace',  # deprecated
    'execute_from_file_on_docjson',  # deprecated
    'execute_from_workspace_on_docjson',  # deprecated
    'execute_workspace_on_docjson',  # deprecated
    'batch_execute_workspace_on_docjsons',
    
    # 结构化数据类
    'Table',
    'Cell',
    
    # 工具相关
    'create_default_tool_hub',
    'create_default_llm_guide',
    'has_default_tool',
    'get_structure_code',
    'get_llm_context',
    'setup_code_tools',
    'ToolHub',
    'ToolRegistry',
    'tool',
    
    # 工具类
    'LLMSelectTool',
    'ExtractTool',
    'NerTool',
    'NerRegexTool',
    
    # NER 相关
    'NERPattern',
    'Match',
    'StringWithNER',
    'NerApi',
]
