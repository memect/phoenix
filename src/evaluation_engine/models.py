"""
Evaluation Engine Models

评估引擎使用的数据模型，从 evaluator 模块重新导出。
"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel
from evaluator.core.evaluation_models import (
    FullStandard as Standard, 
    Info, 
    FullExtractedResult as ExtractedResult
)

__all__ = [
    "Standard",
    "Info",
    "ExtractedResult",
]
