"""核心数据模型"""

import abc
import traceback
from typing import Optional, Dict, Any, List, Sequence, Generic, TypeVar, TYPE_CHECKING
from enum import Enum
from pydantic import BaseModel, Field, SkipValidation

from evaluator.core.evaluation_models import (
    EvaluationExtraction, EvaluationStandard, RuntimeInfo, ExceptionInfo,
    Document, Info
)
from .schema import Schema

D = TypeVar('D')
S = TypeVar('S')




# Standard 已移至 evaluation_models.py 中的 EvaluationStandard 和 FullStandard


class BaseFieldStat(abc.ABC):
    @property
    @abc.abstractmethod
    def accuracy(self) -> float:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def recall(self) -> float:
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def precision(self) -> float:
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def f1(self) -> float:
        raise NotImplementedError


class FieldDetailType(str, Enum):
    """字段详细类型枚举"""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    MISSING = "missing"
    EXTRA = "extra"


class RecordDetailType(str, Enum):
    """记录详细类型枚举"""
    CORRECT = "correct"
    INCORRECT = "incorrect"


# ExtractedResult 已移至 evaluation_models.py 中的 EvaluationExtraction 和 FullExtractedResult


class RecordDetailBase(BaseModel, Generic[D]):
    """记录详细信息基类 - 现在使用精简的评估数据"""
    
    type: RecordDetailType = Field(..., description="类型: correct(正确), incorrect(值不匹配)")
    extra_info: Dict[str, Any] = Field(default_factory=dict, description="额外信息")
    extracted_info: SkipValidation[EvaluationExtraction] = Field(..., description="提取结果") # 将在扩展层具体化
    standared_info: SkipValidation[EvaluationStandard] = Field(..., description="标准结果") # 将在扩展层具体化

    @property
    def extracted_value(self) -> Any:
        # 适配不同的数据结构
        if hasattr(self.extracted_info, 'labels'):
            return self.extracted_info.labels
        elif hasattr(self.extracted_info, 'data'):
            return self.extracted_info.data
        return self.extracted_info

    @property
    def standard_value(self) -> Any:
        # 适配不同的数据结构
        if hasattr(self.standared_info, 'labels'):
            return self.standared_info.labels
        return self.standared_info


class EvaluationResult[D](BaseModel):
    """评估结果基类"""
    schema_: Schema = Field(..., description="评估结果的schema")
    details: Sequence[RecordDetailBase[D]] = Field(..., description="详细信息列表")


    @property
    def field_stats(self) -> Dict[str, BaseFieldStat]:
        raise NotImplementedError

    @property
    def overall_accuracy(self) -> float:
        """总体准确率"""
        return self.total_correct / self.total_records if self.total_records > 0 else 0.0
    
    @property
    def total_correct(self) -> int:
        """完全正确的记录数"""
        return sum(1 for d in self.details if d.type == RecordDetailType.CORRECT)
    
    @property
    def total_records(self) -> int:
        """总记录数"""
        return len(self.details)

    def has_error(self) -> bool:
        """是否有错误"""
        raise NotImplementedError

    def generate_report(self, extra_keys=None):
        """生成报告"""
        raise NotImplementedError

    def get_details_by_type(self, types: List[RecordDetailType]) -> List[RecordDetailBase[D]]:
        """根据类型获取详细信息"""
        types_set = set(types)
        return [d for d in self.details if d.type in types_set]


    def get_incorrect_details(self) -> List[RecordDetailBase[D]]:
        """获取错误详细信息"""
        return [d for d in self.details if d.type == RecordDetailType.INCORRECT]

    def get_details_by_ids(self, ids: List[str]) -> List[RecordDetailBase[D]]:
        """根据ID获取详细信息"""
        return [detail for detail in self.details if detail.standared_info.id in ids]

    def llm_overall_report(self) -> str:
        raise NotImplementedError

    def get_t2f_details(self, prev_eval: 'EvaluationResult') -> list[RecordDetailBase]:
        return get_t2f_f2t_details(prev_eval, self)[0]

    def get_f2t_details(self, prev_eval: 'EvaluationResult') -> list[RecordDetailBase]:
        return get_t2f_f2t_details(prev_eval, self)[1]

    def get_t2f_report(self, prev_eval: 'EvaluationResult') -> str:
        return get_t2f_report(prev_eval, self, t2f_limit=10, f2t_limit=10)

    def get_f2t_report(self, prev_eval: 'EvaluationResult') -> str:
        return get_f2t_report(prev_eval, self, t2f_limit=10, f2t_limit=10)

def get_t2f_f2t_details(prev_eval: EvaluationResult, current_eval: EvaluationResult):
    t2f_details: list[tuple[RecordDetailBase, RecordDetailBase]] = []
    f2t_details: list[tuple[RecordDetailBase, RecordDetailBase]] = []
    for prev_detail, curr_detail in zip(prev_eval.details, current_eval.details):
        if prev_detail.type == RecordDetailType.CORRECT and curr_detail.type == RecordDetailType.INCORRECT:
            t2f_details.append((prev_detail, curr_detail))
        elif prev_detail.type == RecordDetailType.INCORRECT and curr_detail.type == RecordDetailType.CORRECT:
            f2t_details.append((prev_detail, curr_detail))
    return t2f_details, f2t_details

def get_t2f_report(prev_eval: EvaluationResult, current_eval: EvaluationResult, t2f_limit: int = 2, f2t_limit: int = 2):
    change_parts = []

    f2t_details: list[tuple[RecordDetailBase, RecordDetailBase]] = []
    t2f_details: list[tuple[RecordDetailBase, RecordDetailBase]] = []
    for prev_detail, curr_detail in zip(prev_eval.details, current_eval.details):
        std_id = prev_detail.standared_info.id
        if prev_detail.type == RecordDetailType.CORRECT and curr_detail.type == RecordDetailType.INCORRECT:
            t2f_details.append((prev_detail, curr_detail))
        elif prev_detail.type == RecordDetailType.INCORRECT and curr_detail.type == RecordDetailType.CORRECT:
            f2t_details.append((prev_detail, curr_detail))

    change_parts.append("从正确变为错误(最多显示{}个, 总共{}个)：".format(t2f_limit, len(t2f_details)))
    for prev_detail, curr_detail in t2f_details[:t2f_limit]:
        std_id = prev_detail.standared_info.id
        change_parts.append(f"""  std_id: {std_id} 从正确变为错误
之前的正确值：{prev_detail.extracted_value}
当前错误值：{curr_detail.extracted_value}
""")
    change_parts.append("\n")
    return '\n'.join(change_parts)

def get_f2t_report(prev_eval: EvaluationResult, current_eval: EvaluationResult, t2f_limit: int = 2, f2t_limit: int = 2):
    change_parts = []

    f2t_details: list[tuple[RecordDetailBase, RecordDetailBase]] = []
    t2f_details: list[tuple[RecordDetailBase, RecordDetailBase]] = []
    for prev_detail, curr_detail in zip(prev_eval.details, current_eval.details):
        std_id = prev_detail.standared_info.id
        if prev_detail.type == RecordDetailType.CORRECT and curr_detail.type == RecordDetailType.INCORRECT:
            t2f_details.append((prev_detail, curr_detail))
        elif prev_detail.type == RecordDetailType.INCORRECT and curr_detail.type == RecordDetailType.CORRECT:
            f2t_details.append((prev_detail, curr_detail))

    # 生成从错误变为正确的信息
    change_parts.append("从错误变为正确(最多显示{}个, 总共{}个)：".format(f2t_limit, len(f2t_details)))
    for prev_detail, curr_detail in f2t_details[:f2t_limit]:
        std_id = prev_detail.standared_info.id
        change_parts.append(f"""  std_id: {std_id} 从错误变为正确
之前的错误值：{prev_detail.extracted_value}
当前正确值：{curr_detail.extracted_value}
""")

    return '\n'.join(change_parts)