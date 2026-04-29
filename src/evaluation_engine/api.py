"""
Evaluation Engine API

提供评估引擎的代码接口，方便程序化调用。
"""

import asyncio
from typing import Optional, List, Dict, Literal, TYPE_CHECKING

from evaluator.core.models import EvaluationResult, RecordDetailBase

from .engine import EvaluationEngine
from .cli import download_dataset, read_program, extract_evaluation_data, format_record_detail

if TYPE_CHECKING:
    from simple_workflow.models import ResultJson


async def evaluate_program(
    program: 'str | dict | ResultJson',
    data_path: str,
    eval_type: Literal['train', 'test'] = 'train',
    keys: Optional[List[str]] = None,
    std_ids: Optional[List[str]] = None,
    prog_run_concurrent: int = 1,
) -> EvaluationResult:
    """评估程序在数据集上的表现
    
    Args:
        program: 要评估的程序，支持三种格式：
            - str: 单个程序代码字符串
            - dict: ResultJson 格式 {'__type__': 'single'/'all', '__data__': ...}
            - ResultJson: 直接传入 ResultJson 对象
        data_path: 数据目录路径
        eval_type: 评估类型，'train' 或 'test'
        keys: 可选的字段列表，仅评估指定字段
        std_ids: 可选的文档ID列表，仅评估指定文档
        prog_run_concurrent: 并发执行数量
        
    Returns:
        EvaluationResult: 评估结果
    """
    engine = EvaluationEngine.from_data_path(data_path, keys=keys)
    engine.prog_run_concurrent = prog_run_concurrent
    return await engine.evaluate_program(program, eval_type, keys=keys, std_ids=std_ids)


async def evaluate_program_on_docs(
    program: str,
    data_path: str,
    doc_ids: List[str],
    keys: Optional[List[str]] = None,
    prog_run_concurrent: int = 1,
) -> Dict[str, RecordDetailBase | None]:
    """评估程序在指定文档上的表现
    
    Args:
        program: 程序代码字符串
        data_path: 数据目录路径
        doc_ids: 文档 ID 列表
        keys: 可选的字段列表，仅评估指定字段
        prog_run_concurrent: 并发执行数量
        
    Returns:
        {std_id: RecordDetailBase | None} 字典
    """
    engine = EvaluationEngine.from_data_path(data_path, keys=keys)
    engine.prog_run_concurrent = prog_run_concurrent
    return await engine.evaluate_program_on_std_ids(program, doc_ids, keys=keys)


def evaluate_program_sync(
    program: 'str | dict | ResultJson',
    data_path: str,
    eval_type: Literal['train', 'test'] = 'train',
    keys: Optional[List[str]] = None,
    std_ids: Optional[List[str]] = None,
    prog_run_concurrent: int = 1,
) -> EvaluationResult:
    """同步版本的评估程序函数
    
    Args:
        program: 要评估的程序
        data_path: 数据目录路径
        eval_type: 评估类型
        keys: 可选的字段列表
        std_ids: 可选的文档ID列表，仅评估指定文档
        prog_run_concurrent: 并发执行数量
        
    Returns:
        EvaluationResult: 评估结果
    """
    return asyncio.run(evaluate_program(
        program, data_path, eval_type, keys, std_ids, prog_run_concurrent
    ))


def evaluate_program_on_docs_sync(
    program: str,
    data_path: str,
    doc_ids: List[str],
    keys: Optional[List[str]] = None,
    prog_run_concurrent: int = 1,
) -> Dict[str, RecordDetailBase | None]:
    """同步版本的文档评估函数
    
    Args:
        program: 程序代码字符串
        data_path: 数据目录路径
        doc_ids: 文档 ID 列表
        keys: 可选的字段列表
        prog_run_concurrent: 并发执行数量
        
    Returns:
        {std_id: RecordDetailBase | None} 字典
    """
    return asyncio.run(evaluate_program_on_docs(
        program, data_path, doc_ids, keys, prog_run_concurrent
    ))


__all__ = [
    # 异步接口
    "evaluate_program",
    "evaluate_program_on_docs",
    # 同步接口
    "evaluate_program_sync",
    "evaluate_program_on_docs_sync",
    # 工具函数
    "download_dataset",
    "read_program",
    "extract_evaluation_data",
    "format_record_detail",
]
