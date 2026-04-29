"""
代码执行器模块

提供执行提取程序的核心功能。

统一接口：
    execute() - 支持所有输入源和数据格式的组合
    
向后兼容接口（内部调用 execute）：
    execute_from_file(), execute_from_workspace(),
    execute_from_file_on_docjson(), execute_from_workspace_on_docjson(),
    execute_with_output()
"""

import asyncio
import inspect
import os
import warnings
from pathlib import Path
from typing import Any, Callable, Literal, get_type_hints, overload
import tempfile
import importlib.util

from .document.docjson_adapter import normalize_docjson
from .document.models.document import Document


# =============================================================================
# 输入模式配置
# =============================================================================

INPUT_MODE_ENV = "CODE_EXECUTOR_INPUT_MODE"
DEFAULT_INPUT_MODE = "tree"
DOCUMENT_ONLY_ERROR = (
    "code_executor 现在仅支持 Document 输入。请将提取入口改为 "
    "`def extract(document: Document)` 或 "
    "`def extract(document: Document, tool_hub: ToolHub)`；"
    "article/list[str|Table]/flat 模式已不再支持。"
)
_MISSING = object()


def get_input_mode() -> Literal["tree"]:
    """获取输入模式（从环境变量 CODE_EXECUTOR_INPUT_MODE 读取，默认 tree）。"""
    mode = os.environ.get(INPUT_MODE_ENV, DEFAULT_INPUT_MODE).lower()
    if mode == "tree":
        return "tree"
    raise ValueError(
        f"{DOCUMENT_ONLY_ERROR} 环境变量 {INPUT_MODE_ENV}={mode!r} 不可用。"
    )


def detect_input_mode(extract_func: Callable) -> Literal["tree"]:
    """根据 extract 函数的签名检测输入模式
    
    检查第一个参数的类型注解：
    - Document 类型 → "tree"
    - 参数名 doc/document → "tree"
    - list/article/data/items → 明确失败
    - 否则使用环境变量配置（只允许 tree）
    """
    try:
        hints = get_type_hints(extract_func)
    except Exception:
        hints = {}
    
    sig = inspect.signature(extract_func)
    params = list(sig.parameters.keys())
    
    if not params:
        return get_input_mode()
    
    first_param = params[0]
    
    if first_param in hints:
        param_type = hints[first_param]
        if param_type is Document or (
            hasattr(param_type, "__name__") and param_type.__name__ == "Document"
        ):
            return "tree"
        origin = getattr(param_type, "__origin__", None)
        if origin is list or param_type is list:
            raise ValueError(DOCUMENT_ONLY_ERROR)
    
    if first_param in ("doc", "document"):
        return "tree"
    if first_param in ("article", "data", "items"):
        raise ValueError(DOCUMENT_ONLY_ERROR)
    
    return get_input_mode()


def create_input(
    docjson: dict, 
    pdf_bytes: bytes | None = None,
    mode: Literal["tree", "flat"] | str | None = None
) -> Any:
    """从 DocJSON 创建输入数据
    
    Args:
        docjson: DocJSON 格式的文档数据
        pdf_bytes: 可选的 PDF 原始二进制数据
        mode: 输入模式（仅支持 tree=Document），None 从环境变量读取
    """
    docjson = normalize_docjson(docjson)

    if mode is None:
        mode = get_input_mode()
    if mode != "tree":
        raise ValueError(DOCUMENT_ONLY_ERROR)
    
    doc = Document.from_dict(docjson)
    doc.raw_bytes = pdf_bytes
    return doc


# =============================================================================
# 内部辅助函数
# =============================================================================

def _load_module(program_path: str):
    """加载程序模块，验证 extract() 函数存在"""
    spec = importlib.util.spec_from_file_location("program", program_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    if not hasattr(module, "extract"):
        raise ValueError("FunctionNotFound: extract() not exist.")
    
    return module


def _resolve_program_path(
    program: str | None,
    program_path: str | Path | None,
    workspace: str | Path | None,
) -> str:
    """解析输入源，返回程序文件的绝对路径
    
    Args:
        program: 程序代码字符串
        program_path: 程序文件路径
        workspace: workspace 目录路径
        
    Returns:
        程序文件的绝对路径
        
    Raises:
        ValueError: 输入源参数不合法（必须且仅有一个）
        FileNotFoundError: 文件或目录不存在
    """
    # 验证输入源参数：必须且仅有一个
    sources = [program, program_path, workspace]
    provided = sum(1 for s in sources if s is not None)
    
    if provided == 0:
        raise ValueError("必须提供 program、program_path 或 workspace 之一")
    if provided > 1:
        raise ValueError("program、program_path、workspace 只能提供一个")
    
    # 解析得到程序文件路径
    if program is not None:
        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(program.encode("utf-8"))
            return f.name
    
    if program_path is not None:
        path = Path(program_path)
        if not path.exists():
            raise FileNotFoundError(f"程序文件不存在: {path}")
        return str(path.absolute())
    
    # workspace
    ws_path = Path(workspace)
    if not ws_path.exists():
        raise FileNotFoundError(f"Workspace 目录不存在: {ws_path}")
    
    prog_path = ws_path / "program.py"
    if not prog_path.exists():
        raise FileNotFoundError(f"程序文件不存在: {prog_path}")
    
    return str(prog_path.absolute())


def _prepare_data(
    module,
    data: Any,
    docjson: dict | None,
    pdf_bytes: bytes | None,
) -> Any:
    """准备执行数据
    
    如果提供 docjson，自动检测输入模式并转换；否则直接使用 data。
    """
    if docjson is not None:
        mode = detect_input_mode(module.extract)
        return create_input(docjson, pdf_bytes=pdf_bytes, mode=mode)
    return data


async def _run_extract(
    module,
    data: Any,
    capture_output: bool,
    tool_hub: Any | None,
) -> Any | tuple[Any, str, str]:
    """执行 extract 函数"""
    def call_extract():
        return _call_extract(module.extract, data, tool_hub)

    if capture_output:
        from io import StringIO
        from contextlib import redirect_stdout, redirect_stderr
        
        def run_with_capture():
            stdout_io = StringIO()
            stderr_io = StringIO()
            with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
                result = call_extract()
            return result, stdout_io.getvalue(), stderr_io.getvalue()
        
        return await asyncio.to_thread(run_with_capture)
    else:
        return await asyncio.to_thread(call_extract)


def _call_extract(extract_func: Callable, data: Any, tool_hub: Any | None) -> Any:
    """Call extract(document) or extract(document, tool_hub)."""
    sig = inspect.signature(extract_func)
    params = list(sig.parameters.values())

    if "tool_hub" in sig.parameters:
        tool_param = sig.parameters["tool_hub"]
        if tool_param.kind is inspect.Parameter.POSITIONAL_ONLY:
            return extract_func(data, tool_hub)
        return extract_func(data, tool_hub=tool_hub)

    positional_params = [
        param
        for param in params
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if len(positional_params) >= 2:
        return extract_func(data, tool_hub)
    return extract_func(data)


# =============================================================================
# 统一接口
# =============================================================================

@overload
async def execute(
    program: str | None = ...,
    data: Any = ...,
    *,
    program_path: str | Path | None = ...,
    workspace: str | Path | None = ...,
    docjson: dict | None = ...,
    pdf_bytes: bytes | None = ...,
    tool_hub: Any | None = ...,
    capture_output: Literal[False] = ...,
) -> Any: ...

@overload
async def execute(
    program: str | None = ...,
    data: Any = ...,
    *,
    program_path: str | Path | None = ...,
    workspace: str | Path | None = ...,
    docjson: dict | None = ...,
    pdf_bytes: bytes | None = ...,
    tool_hub: Any | None = ...,
    capture_output: Literal[True],
) -> tuple[Any, str, str]: ...

async def execute(
    program: str | None = None,
    data: Any = _MISSING,
    *,
    program_path: str | Path | None = None,
    workspace: str | Path | None = None,
    docjson: dict | None = None,
    pdf_bytes: bytes | None = None,
    tool_hub: Any | None = None,
    capture_output: bool = False,
) -> Any | tuple[Any, str, str]:
    """执行提取程序（统一接口）
    
    支持多种输入源和数据格式的组合。
    
    Args:
        program: 程序代码字符串（与 program_path/workspace 互斥）
        program_path: 程序文件路径（与 program/workspace 互斥）
        workspace: workspace 目录路径（与 program/program_path 互斥）
        data: 已处理的输入数据（与 docjson 互斥）
        docjson: DocJSON 格式数据，自动检测模式并转换（与 data 互斥）
        pdf_bytes: PDF 原始二进制数据（仅与 docjson 配合使用）
        tool_hub: 显式注入给 extract(document, tool_hub) 的工具中心
        capture_output: 是否捕获 stdout/stderr
        
    Returns:
        capture_output=False: 提取结果
        capture_output=True: (result, stdout, stderr) 元组
        
    Raises:
        ValueError: 参数不合法
        FileNotFoundError: 文件或目录不存在
        
    Examples:
        # 从代码字符串执行
        result = await execute(program=code, data=input_data)
        
        # 从 workspace 在 docjson 上执行
        result = await execute(workspace="path/to/ws", docjson=doc)
        
        # 捕获输出
        result, stdout, stderr = await execute(
            program_path="prog.py", data=input_data, capture_output=True
        )
    """
    # 验证数据参数
    data_provided = data is not _MISSING
    if data_provided and docjson is not None:
        raise ValueError("data 和 docjson 不能同时提供")
    if not data_provided and docjson is None:
        raise ValueError("必须提供 data 或 docjson 之一")
    if pdf_bytes is not None and docjson is None:
        raise ValueError("pdf_bytes 只能与 docjson 配合使用")
    
    # 解析程序路径
    resolved_path = _resolve_program_path(program, program_path, workspace)
    
    # 加载模块
    module = _load_module(resolved_path)
    
    # 准备数据
    input_data = _prepare_data(module, data if data_provided else None, docjson, pdf_bytes)
    
    # 执行
    return await _run_extract(module, input_data, capture_output, tool_hub)


# =============================================================================
# 向后兼容接口（已废弃）
# =============================================================================

async def execute_from_file(program_path: str | Path, data: Any) -> Any:
    """从文件路径执行提取程序
    
    .. deprecated::
        使用 execute(program_path=..., data=...) 替代
    """
    warnings.warn(
        "execute_from_file 已废弃，请使用 execute(program_path=..., data=...)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(program_path=program_path, data=data)


async def execute_from_workspace(workspace: str | Path, data: Any) -> Any:
    """从 workspace 目录执行提取程序
    
    .. deprecated::
        使用 execute(workspace=..., data=...) 替代
    """
    warnings.warn(
        "execute_from_workspace 已废弃，请使用 execute(workspace=..., data=...)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(workspace=workspace, data=data)


async def execute_from_workspace_on_docjson(
    workspace: str | Path, 
    docjson: dict,
    pdf_bytes: bytes | None = None,
    tool_hub: Any | None = None,
) -> Any:
    """从 workspace 在 DocJSON 上执行
    
    .. deprecated::
        使用 execute(workspace=..., docjson=..., pdf_bytes=..., tool_hub=...) 替代
    """
    warnings.warn(
        "execute_from_workspace_on_docjson 已废弃，请使用 execute(workspace=..., docjson=...)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(
        workspace=workspace,
        docjson=docjson,
        pdf_bytes=pdf_bytes,
        tool_hub=tool_hub,
    )


async def execute_from_file_on_docjson(
    program_path: str | Path, 
    docjson: dict,
    pdf_bytes: bytes | None = None,
    tool_hub: Any | None = None,
) -> Any:
    """从文件路径在 DocJSON 上执行
    
    .. deprecated::
        使用 execute(program_path=..., docjson=..., pdf_bytes=..., tool_hub=...) 替代
    """
    warnings.warn(
        "execute_from_file_on_docjson 已废弃，请使用 execute(program_path=..., docjson=...)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(
        program_path=program_path,
        docjson=docjson,
        pdf_bytes=pdf_bytes,
        tool_hub=tool_hub,
    )


async def execute_with_output(program: str, data: Any) -> tuple[Any, str, str]:
    """执行并捕获输出
    
    .. deprecated::
        使用 execute(program=..., data=..., capture_output=True) 替代
    """
    warnings.warn(
        "execute_with_output 已废弃，请使用 execute(..., capture_output=True)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(program=program, data=data, capture_output=True)


async def do_extract(program: str, data: Any) -> Any:
    """execute 的别名
    
    .. deprecated::
        使用 execute(program=..., data=...) 替代
    """
    warnings.warn(
        "do_extract 已废弃，请使用 execute(program=..., data=...)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(program=program, data=data)


async def do_extract_with_output(program: str, data: Any) -> tuple[Any, str, str]:
    """execute_with_output 的别名
    
    .. deprecated::
        使用 execute(program=..., data=..., capture_output=True) 替代
    """
    warnings.warn(
        "do_extract_with_output 已废弃，请使用 execute(..., capture_output=True)",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute(program=program, data=data, capture_output=True)
