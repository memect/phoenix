"""基础抽象类"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict, TypeVar
from .models import EvaluationResult

D = TypeVar('D')


class Evaluator(ABC):
    """评估器基类 - 使用精简的评估数据结构"""
    
    @abstractmethod
    def evaluate(
        self, 
        extracted_results: List[Any],
        standard_results: List[Any],
        extra_infos: List[Dict[str, Any]] | None = None
    ) -> EvaluationResult[Any]:
        """
        执行评估 - 纯粹的数据比较
        
        Args:
            extracted_results: 提取结果列表，只包含 id 和 labels
            standard_results: 标准结果列表，只包含 id 和 labels
            extra_infos: 可选的额外信息
            
        Returns:
            评估结果
        """
        pass
