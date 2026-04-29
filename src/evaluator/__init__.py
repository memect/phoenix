"""
Evaluator Module

评估模块，负责比较提取结果和标准答案、计算准确率，提供：
- ObjectEvaluator: 对象评估器
- ListOfObjectsEvaluator: 对象列表评估器
- EvaluationResult: 评估结果
- StandardSet: 标准集管理
- compare(): 比较提取结果和标准答案
"""

# 核心模块导出
from .core import (
    Document, Info, RuntimeInfo, ExceptionInfo, 
    RecordDetailType, FieldDetailType, RecordDetailBase, EvaluationResult,
    EvaluationStandard, EvaluationExtraction, FullStandard, FullExtractedResult,
    Schema, FieldType, SchemaField,
    Evaluator
)

# 标准集管理导出
from .standards import (
    StandardSet, StandardSetMetadata, 
    StandardSetLoader, DirectoryStandardSetLoader, StandardSetManager, DatasetEvaluator
)

# 评估器导出
from .evaluators import (
    ObjectEvaluator, ObjectEvaluationResult,
    ListOfObjectsEvaluator, ListOfObjectsEvaluationResult
)

# 快捷接口导出 - 从 api.py 导出
from .api import (
    get_evaluate_parts, EvaluateParts
)

# API 接口导出
from .api import (
    compare, compare_objects, compare_list_of_objects,
    get_evaluator, evaluate_batch
)

# 向后兼容
from .utils import _compare_values

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
    
    # 标准集管理
    "StandardSet",
    "StandardSetMetadata",
    "StandardSetLoader",
    "DirectoryStandardSetLoader", 
    "StandardSetManager",
    
    # 评估器
    "ObjectEvaluator",
    "ObjectEvaluationResult",
    "ListOfObjectsEvaluator",
    "ListOfObjectsEvaluationResult",
    
    # 快捷接口
    "get_evaluate_parts",
    "EvaluateParts",
    
    # API 接口
    "compare",
    "compare_objects",
    "compare_list_of_objects",
    "get_evaluator",
    "evaluate_batch",
    
    # 数据集评估器工厂
    "DatasetEvaluator",
    
    # 工具函数
    "_compare_values"
]