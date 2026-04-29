from enum import Enum
from typing import Any, Dict, List, Union, Optional, Generic, TypeVar, TypeAlias
import numpy as np
from pydantic import BaseModel, Field

from scipy.optimize import linear_sum_assignment # type: ignore

# 从现有模块导入共享组件
from ...utils import _compare_values
from ...core.models import RecordDetailType
from ...core.schema import Schema
from ...core.evaluation_models import EvaluationStandard, EvaluationExtraction, FullStandard, FullExtractedResult
from .models import RecordDetail, MatchedObjectDetail, ListOfObjectsEvaluationResult
from ...core.base import Evaluator

# 常量定义
HIGH_COST_THRESHOLD = 1e6  # 不合格匹配对的高成本
QUALIFIED_MATCH_THRESHOLD = 1e5  # 合格匹配的成本阈值


class ListOfObjectsEvaluator(Evaluator):
    """列表对象评估器 - 合并了 ExtendedListOfObjectsEvaluator 的功能"""
    
    def __init__(self, schema: Union[Dict[str, str], Schema], similarity_threshold: float = 0.5):
        if isinstance(schema, dict):
            self.schema = Schema.from_dict(schema)
        else:
            self.schema = schema
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        self.similarity_threshold = similarity_threshold

    def _calculate_similarity(self, obj1: Dict[str, Any], obj2: Dict[str, Any]) -> float:
        """计算两个对象之间的相似度"""
        matched_fields = 0
        total_fields = len(self.schema.fields)
        if total_fields == 0: 
            return 1.0

        for field_name, field_type in self.schema.fields.items():
            val1 = obj1.get(field_name)
            val2 = obj2.get(field_name)
            if _compare_values(val1, val2, field_type):
                matched_fields += 1
        return matched_fields / total_fields

# 旧的 _evaluate_single_case 方法已删除，现在使用精简的评估逻辑

    def evaluate(
        self,
        extracted_results: List[FullExtractedResult],
        standard_results: List[FullStandard],
        extra_infos: Optional[List[Dict[str, Any]]] = None
    ) -> ListOfObjectsEvaluationResult:
        """
        批量评估对象列表的提取结果 - 直接接受 FullStandard 和 FullExtractedResult
        
        Args:
            extracted_results: 完整提取结果列表
            standard_results: 完整标准结果列表
            extra_infos: 可选的额外信息列表
            
        Returns:
            ListOfObjectsEvaluationResult: 包含统计信息和详细对比结果的评估结果
        """
        if len(extracted_results) != len(standard_results):
            raise ValueError("提取结果列表和标准结果列表长度不一致")
            
        if extra_infos is None:
            extra_infos = [{} for _ in range(len(extracted_results))]
        elif len(extra_infos) != len(extracted_results):
            raise ValueError("额外信息列表长度与结果列表不一致")
            
        details = []

        # 遍历每一个独立的评估案例
        for extracted, standard, extra_info in zip(extracted_results, standard_results, extra_infos):
            case_detail = self._evaluate_single_case(extracted, standard, extra_info)
            details.append(case_detail)

        return ListOfObjectsEvaluationResult(details=details, schema_=self.schema)
    
    def evaluate_one(
        self, 
        extracted: FullExtractedResult, 
        standard: FullStandard,
        extra_info: Dict[str, Any] | None = None
    ) -> RecordDetail:
        """
        评估单条记录 - 直接接受 FullStandard 和 FullExtractedResult
        
        Args:
            extracted: 完整提取结果
            standard: 完整标准结果
            extra_info: 可选的额外信息
            
        Returns:
            RecordDetail: 记录详细信息
        """
        if extra_info is None:
            extra_info = {}
        return self._evaluate_single_case(extracted, standard, extra_info)
        
    def _evaluate_single_case(
        self, 
        extracted: FullExtractedResult, 
        standard: FullStandard,
        extra_info: Dict[str, Any]
    ) -> RecordDetail:
        """评估单个案例 - 直接使用完整数据"""

        # 直接使用 labels 进行比较
        extracted_list = extracted.labels
        standard_list = standard.labels

        # 验证数据类型
        if not isinstance(extracted_list, list) or not isinstance(standard_list, list):
            return RecordDetail(
                type=RecordDetailType.INCORRECT,
                missing=[] if not isinstance(standard_list, list) else standard_list,
                extra=[],
                matched=[],
                extra_info=extra_info,
                extracted_info=extracted,  # 直接使用完整的 FullExtractedResult
                standared_info=standard    # 直接使用完整的 FullStandard
            )

        # 构建相似度矩阵并进行匹配
        sim_matrix = np.array([
            [self._calculate_similarity(ext_obj, std_obj) for std_obj in standard_list]
            for ext_obj in extracted_list
        ], ndmin=2)
        
        cost_matrix = 1 - sim_matrix
        cost_matrix[sim_matrix < self.similarity_threshold] = HIGH_COST_THRESHOLD

        # 使用匈牙利算法找到最优匹配
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        matched_ext_indices = set()
        matched_std_indices = set()
        matched_details = []

        # 处理匹配的对象
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < QUALIFIED_MATCH_THRESHOLD:
                ext_obj = extracted_list[r]
                std_obj = standard_list[c]
                similarity = sim_matrix[r, c]
                matched_ext_indices.add(r)
                matched_std_indices.add(c)

                # 计算错误的字段
                incorrect_fields = []
                # 计算正确的字段
                correct_fields = []
                # missing fields
                missing_fields = []
                # extra fields
                extra_fields = []
                for field_name, field_type in self.schema.fields.items():
                    if field_name not in ext_obj:
                        missing_fields.append(field_name)
                        continue
                    if not _compare_values(ext_obj.get(field_name), std_obj.get(field_name), field_type):
                        incorrect_fields.append(field_name)
                        continue
                    correct_fields.append(field_name)
                for field_name in ext_obj.keys():
                    if field_name not in self.schema.fields:
                        extra_fields.append(field_name)

                matched_detail = MatchedObjectDetail(
                    standard_value=std_obj,
                    extracted_value=ext_obj,
                    similarity_score=similarity,
                    std_list_idx=c,
                    ext_list_idx=r,
                    # mismatched_fields=mismatched_fields
                    incorrect_fields=incorrect_fields,
                    correct_fields=correct_fields,
                    missing_fields=missing_fields,
                    extra_fields=extra_fields
                )
                matched_details.append(matched_detail)

        # 收集未匹配的对象
        missing_objects = [standard_list[i] for i in range(len(standard_list)) if i not in matched_std_indices]
        extra_objects = [extracted_list[i] for i in range(len(extracted_list)) if i not in matched_ext_indices]

        # 确定整体类型（只有 CORRECT 和 INCORRECT）
        if not missing_objects and not extra_objects and all(m.similarity_score == 1.0 for m in matched_details):
            record_type = RecordDetailType.CORRECT
        else:
            record_type = RecordDetailType.INCORRECT

        detail = RecordDetail(
            type=record_type,
            missing=missing_objects,
            extra=extra_objects,
            matched=matched_details,
            extra_info=extra_info,
            extracted_info=extracted,  # 直接使用完整的 FullExtractedResult
            standared_info=standard    # 直接使用完整的 FullStandard
        )

        return detail