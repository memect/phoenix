"""
Code Executor API 模块

提供批量执行等高级 API 功能。
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, List, Dict
from .executor import execute


async def batch_execute(
    program: str, 
    inputs: List[Any], 
    concurrent: int = 5,
    tool_hub: Any | None = None,
) -> List[Dict[str, Any]]:
    """批量执行提取程序
    
    Args:
        program: Python 程序代码字符串
        inputs: 输入数据列表（通常是 Article 格式的列表）
        concurrent: 并发数，默认为 5
        tool_hub: 显式注入给 extract(document, tool_hub) 的工具中心
        
    Returns:
        提取结果列表，每个元素包含:
        - success: 是否成功
        - data: 提取结果（成功时）
        - error: 错误信息（失败时）
    """
    semaphore = asyncio.Semaphore(concurrent)
    
    async def execute_with_semaphore(input_data: Any, index: int) -> Dict[str, Any]:
        async with semaphore:
            try:
                result = await execute(
                    program=program,
                    data=input_data,
                    tool_hub=tool_hub,
                )
                return {
                    'index': index,
                    'success': True,
                    'data': result,
                    'error': None
                }
            except Exception as e:
                return {
                    'index': index,
                    'success': False,
                    'data': None,
                    'error': str(e)
                }
    
    tasks = [
        execute_with_semaphore(input_data, i) 
        for i, input_data in enumerate(inputs)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # 按原始顺序排序
    results = sorted(results, key=lambda x: x['index'])
    
    return results


async def execute_on_docjson(
    docjson: dict,
    *,
    program: str | None = None,
    workspace: str | Path | None = None,
    config: dict | None = None,
    pdf_bytes: bytes | None = None,
    tool_hub: Any | None = None,
) -> Any:
    """在 DocJSON 上执行提取程序
    
    三种输入方式互斥：
    - program: 程序代码字符串
    - workspace: workspace 目录路径
    - config: 配置字典
    
    Args:
        docjson: DocJSON 格式的文档数据
        program: 程序代码字符串
        workspace: workspace 目录路径
        config: 配置字典
        pdf_bytes: 可选的 PDF 原始二进制数据
        tool_hub: 显式注入给 extract(document, tool_hub) 的工具中心
        
    Returns:
        提取结果
        
    Raises:
        ValueError: 当输入参数错误时
    """
    # 互斥检查
    provided = sum(x is not None for x in [program, workspace, config])
    if provided == 0:
        raise ValueError("必须提供 program、workspace 或 config")
    if provided > 1:
        raise ValueError("program、workspace、config 互斥，不能同时提供")
    
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
            tool_hub=tool_hub,
        )
    
    if program is not None:
        return await execute(
            program=program,
            docjson=docjson,
            pdf_bytes=pdf_bytes,
            tool_hub=tool_hub,
        )

    raise ValueError("必须提供 program、workspace 或 config")


async def batch_execute_on_docjsons(
    program: str, 
    docjsons: List[dict], 
    concurrent: int = 5,
    pdf_bytes_list: List[bytes | None] | None = None,
    doc_ids: List[str] | None = None,
    progress_callback: Callable | None = None,
    tool_hub: Any | None = None,
) -> List[Dict[str, Any]]:
    """在多个 DocJSON 上批量执行提取程序
    
    自动检测输入模式。
    
    Args:
        program: Python 程序代码字符串
        docjsons: DocJSON 格式的文档数据列表
        concurrent: 并发数，默认为 5
        pdf_bytes_list: 可选的 PDF 原始二进制数据列表，与 docjsons 一一对应
        doc_ids: 可选的文档 ID 列表，用于进度回调显示
        progress_callback: 可选的进度回调函数，签名:
            callback({'event': 'start', 'doc_id': str, 'total': int})
            callback({'event': 'done', 'doc_id': str, 'completed': int,
                      'total': int, 'success': bool, 'elapsed': float})
        tool_hub: 显式注入给 extract(document, tool_hub) 的工具中心
        
    Returns:
        提取结果列表
    """
    import time as time_module

    if pdf_bytes_list is None:
        pdf_bytes_list = [None] * len(docjsons)
    if doc_ids is None:
        doc_ids = [str(i) for i in range(len(docjsons))]
    
    total = len(docjsons)
    completed_count = 0
    semaphore = asyncio.Semaphore(concurrent)
    
    async def execute_with_semaphore(docjson: dict, pdf_bytes: bytes | None, index: int) -> Dict[str, Any]:
        nonlocal completed_count
        doc_id = doc_ids[index]

        if progress_callback:
            progress_callback({
                'event': 'start',
                'doc_id': doc_id,
                'total': total,
            })

        async with semaphore:
            start_time = time_module.time()
            try:
                result = await execute(
                    program=program,
                    docjson=docjson,
                    pdf_bytes=pdf_bytes,
                    tool_hub=tool_hub,
                )
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
            elapsed = time_module.time() - start_time
        completed_count += 1

        if progress_callback:
            progress_callback({
                'event': 'done',
                'doc_id': doc_id,
                'completed': completed_count,
                'total': total,
                'success': success,
                'elapsed': elapsed,
            })

        return {
            'index': index,
            'success': success,
            'data': result,
            'error': error,
        }
    
    tasks = [
        execute_with_semaphore(docjson, pdf_bytes, i) 
        for i, (docjson, pdf_bytes) in enumerate(zip(docjsons, pdf_bytes_list))
    ]
    
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda x: x['index'])


async def execute_workspace_on_docjson(
    workspace: str | Path, 
    docjson: dict,
    pdf_bytes: bytes | None = None,
    tool_hub: Any | None = None,
) -> Any:
    """从 workspace 在 DocJSON 上执行提取程序
    
    .. deprecated::
        请使用 execute_on_docjson(docjson, workspace=workspace) 替代
    
    自动加载 workspace/program.py 并执行。
    自动根据 extract() 函数的签名检测输入模式。
    
    Args:
        workspace: workspace 目录路径
        docjson: DocJSON 格式的文档数据
        pdf_bytes: 可选的 PDF 原始二进制数据
        
    Returns:
        提取结果
    """
    import warnings
    warnings.warn(
        "execute_workspace_on_docjson 已废弃，请使用 execute_on_docjson(docjson, workspace=workspace)",
        DeprecationWarning,
        stacklevel=2
    )
    return await execute(
        workspace=workspace,
        docjson=docjson,
        pdf_bytes=pdf_bytes,
        tool_hub=tool_hub,
    )


async def batch_execute_workspace_on_docjsons(
    workspace: str | Path,
    docjsons: List[dict],
    concurrent: int = 5,
    pdf_bytes_list: List[bytes | None] | None = None,
    tool_hub: Any | None = None,
) -> List[Dict[str, Any]]:
    """从 workspace 在多个 DocJSON 上批量执行提取程序
    
    自动加载 workspace/program.py 并执行。
    自动根据 extract() 函数的签名检测输入模式。
    
    Args:
        workspace: workspace 目录路径
        docjsons: DocJSON 格式的文档数据列表
        concurrent: 并发数，默认为 5
        pdf_bytes_list: 可选的 PDF 原始二进制数据列表，与 docjsons 一一对应
        
    Returns:
        提取结果列表，每个元素包含:
        - success: 是否成功
        - data: 提取结果（成功时）
        - error: 错误信息（失败时）
    """
    if pdf_bytes_list is None:
        pdf_bytes_list = [None] * len(docjsons)
    
    semaphore = asyncio.Semaphore(concurrent)
    
    async def execute_with_semaphore(docjson: dict, pdf_bytes: bytes | None, index: int) -> Dict[str, Any]:
        async with semaphore:
            try:
                result = await execute(
                    workspace=workspace,
                    docjson=docjson,
                    pdf_bytes=pdf_bytes,
                    tool_hub=tool_hub,
                )
                return {
                    'index': index,
                    'success': True,
                    'data': result,
                    'error': None
                }
            except Exception as e:
                return {
                    'index': index,
                    'success': False,
                    'data': None,
                    'error': str(e)
                }
    
    tasks = [
        execute_with_semaphore(docjson, pdf_bytes, i) 
        for i, (docjson, pdf_bytes) in enumerate(zip(docjsons, pdf_bytes_list))
    ]
    
    results = await asyncio.gather(*tasks)
    
    # 按原始顺序排序
    results = sorted(results, key=lambda x: x['index'])
    
    return results
