"""核心模块 - 基础数据模型和抽象类"""

from .schema import Schema, FieldType, SchemaField
from .models import (
    Document, Info, RuntimeInfo, ExceptionInfo, 
    RecordDetailType, FieldDetailType, RecordDetailBase, EvaluationResult
)
from .evaluation_models import (
    EvaluationStandard, EvaluationExtraction,
    FullStandard, FullExtractedResult
)
from .base import Evaluator

__all__ = [
    # 基础模型
    "Document",
    "Info",
    "RuntimeInfo",
    "ExceptionInfo",
    "RecordDetailType",
    "FieldDetailType", 
    "RecordDetailBase",
    "EvaluationResult",
    
    # 评估模型
    "EvaluationStandard",
    "EvaluationExtraction", 
    "FullStandard",
    "FullExtractedResult",
    
    # Schema
    "Schema",
    "FieldType",
    "SchemaField",
    
    # 基础类
    "Evaluator",
]
