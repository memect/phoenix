"""
xdev 提取执行入口
"""

from pathlib import Path
from typing import Any


async def extract_from_docjson(
    docjson: dict,
    *,
    program: str | None = None,
    workspace: str | Path | None = None,
    config: dict | None = None,
    pdf_bytes: bytes | None = None,
) -> Any:
    """从 docjson 执行提取

    三种输入方式互斥：
    - program: 程序代码字符串
    - workspace: workspace 目录路径
    - config: 旧格式配置字典

    Raises:
        ValueError: 当输入参数不合法时
    """
    from code_executor.executor import execute

    provided = sum(x is not None for x in [program, workspace, config])
    if provided == 0:
        raise ValueError("必须提供 program、workspace 或 config 之一")
    if provided > 1:
        raise ValueError("program、workspace、config 互斥，不能同时提供")

    from .setup import prepare_extraction_runtime

    runtime = prepare_extraction_runtime()

    if config is not None:
        raise ValueError(
            "config/flat 旧格式已不再支持。请改用 workspace/program，并让 "
            "`extract(document: Document)` 或 "
            "`extract(document: Document, tool_hub: ToolHub)` 返回完整结果。"
        )

    if workspace is not None:
        return await execute(
            workspace=workspace,
            docjson=docjson,
            pdf_bytes=pdf_bytes,
            tool_hub=runtime.tool_hub,
        )
    if program is not None:
        return await execute(
            program=program,
            docjson=docjson,
            pdf_bytes=pdf_bytes,
            tool_hub=runtime.tool_hub,
        )
    raise ValueError("必须提供 program、workspace 或 config 之一")
