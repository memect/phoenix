"""
Evaluation Engine Module

评估引擎模块，组合代码执行和评估功能，提供：
- EvaluationEngine: 主要评估引擎类
- 从本地数据路径或 URL 创建评估引擎
- 评估程序在标准数据集上的表现
- CLI 和代码接口
"""

from .engine import (
    EvaluationEngine,
    ProgressCallback,
    ProgressEvent,
    ProgressStart,
    ProgressDone,
)
from .models import Info, Standard, ExtractedResult
from .api import (
    evaluate_program,
    evaluate_program_on_docs,
    evaluate_program_sync,
    evaluate_program_on_docs_sync,
    download_dataset,
    read_program,
    extract_evaluation_data,
    format_record_detail,
)
from evaluator.core.models import RecordDetailType, EvaluationResult, RecordDetailBase

__all__ = [
    # 核心类
    "EvaluationEngine",
    
    # 进度回调类型
    "ProgressCallback",
    "ProgressEvent",
    "ProgressStart",
    "ProgressDone",
    
    # 数据模型
    "Info",
    "Standard",
    "ExtractedResult",
    "RecordDetailType",
    "EvaluationResult",
    "RecordDetailBase",
    
    # 异步 API
    "evaluate_program",
    "evaluate_program_on_docs",
    
    # 同步 API
    "evaluate_program_sync",
    "evaluate_program_on_docs_sync",
    
    # 工具函数
    "download_dataset",
    "read_program",
    "extract_evaluation_data",
    "format_record_detail",
]
