from typing import Any, Dict, List, Union


from ...core.models import RecordDetailType, FieldDetailType
from ...core.schema import Schema
from ...core.evaluation_models import EvaluationStandard, EvaluationExtraction, FullStandard, FullExtractedResult
from .models import FieldDetail, RecordDetail, ObjectEvaluationResult

from ...utils import _compare_values
from ...core.base import Evaluator



class ObjectEvaluator(Evaluator):
    """
    评估提取结果与标准结果的准确率 - 合并了 ExtendedObjectEvaluator 的功能
    
    schema格式示例: {'字段1': 'str', '字段2': 'int', ...}
    """
    def __init__(self, schema: Union[Dict[str, str], Schema]):
        """
        初始化评估器
        
        Args:
            schema: 数据模式，可以是字典格式 {'字段1': '类型1', '字段2': '类型2', ...} 或 Schema 对象
        """
        if isinstance(schema, dict):
            self.schema = Schema.from_dict(schema)
        elif isinstance(schema, Schema):
            self.schema = schema
        else:
            raise TypeError("schema必须是字典或Schema对象")
        
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
            
        record_related_details = []  # 当前记录的详细信息
        record_correct = True  # 假设当前记录完全正确
        
        # 直接使用 labels 进行比较，处理 None 的情况
        extracted_data = extracted.labels if isinstance(extracted.labels, dict) else {}
        standard_data = standard.labels or {}
        
        # 检查每个字段
        for field in self.schema.fields:
            # 如果字段在两个结果中都存在，则进行比对
            if field in extracted_data and field in standard_data:
                # 比较字段值是否相等
                if _compare_values(extracted_data.get(field), standard_data.get(field), self.schema.fields[field]):
                    # 添加正确详情
                    detail = FieldDetail(
                        name=field,
                        extracted_value=extracted_data[field],
                        standard_value=standard_data[field],
                        type=FieldDetailType.CORRECT
                    )
                    record_related_details.append(detail)
                else:
                    # 添加错误详情
                    detail = FieldDetail(
                        name=field,
                        extracted_value=extracted_data[field],
                        standard_value=standard_data[field],
                        type=FieldDetailType.INCORRECT
                    )
                    record_related_details.append(detail)
                    record_correct = False  # 有字段不匹配，记录不完全正确
            # 如果字段在标准结果中存在但在提取结果中不存在，则为漏提
            elif field in standard_data and field not in extracted_data:
                # 添加漏提详情
                detail = FieldDetail(
                    name=field,
                    extracted_value=None,
                    standard_value=standard_data[field],
                    type=FieldDetailType.MISSING
                )
                record_related_details.append(detail)
                record_correct = False
            # 如果字段在提取结果中存在但在标准结果中不存在，则认为extracted_value为任意空值时都正确，否则错误
            elif field in extracted_data and field not in standard_data:
                extracted_value = extracted_data[field]
                if not extracted_value:
                    detail = FieldDetail(
                        name=field,
                        extracted_value=extracted_value,
                        standard_value=None,
                        type=FieldDetailType.CORRECT
                    )
                else:
                    detail = FieldDetail(
                        name=field,
                        extracted_value=extracted_value,
                        standard_value=None,
                        type=FieldDetailType.INCORRECT
                    )
                    record_correct = False
                record_related_details.append(detail)
            # 如果字段在两个结果中都不存在，视为正确（双方都没有该字段）
            else:
                detail = FieldDetail(
                    name=field,
                    extracted_value=None,
                    standard_value=None,
                    type=FieldDetailType.CORRECT
                )
                record_related_details.append(detail)
        
        record_detail = RecordDetail(
            type=RecordDetailType.CORRECT if record_correct else RecordDetailType.INCORRECT,
            related_field_details=record_related_details,
            extra_info=extra_info,
            extracted_info=extracted,  # 直接使用完整的 FullExtractedResult
            standared_info=standard   # 直接使用完整的 FullStandard
        )
        return record_detail
    
    def evaluate(self, 
                extracted_results: List[FullExtractedResult],
                standard_results: List[FullStandard],
                extra_infos: List[Dict[str, Any]]|None = None) -> ObjectEvaluationResult:
        """
        执行评估 - 直接接受 FullStandard 和 FullExtractedResult
        
        Args:
            extracted_results: 完整提取结果列表
            standard_results: 完整标准结果列表
            extra_infos: 可选的额外信息
            
        Returns:
            ObjectEvaluationResult: 评估结果
        """
        if len(extracted_results) != len(standard_results):
            raise ValueError("提取结果列表和标准结果列表长度不一致")
        
        if extra_infos is None:
            extra_infos = [{}] * len(extracted_results)
        elif len(extra_infos) != len(extracted_results):
            raise ValueError("额外信息列表长度与结果列表不一致")
        
        # 逐条比对数据
        record_details = []
        
        for extracted, standard, extra_info in zip(extracted_results, standard_results, extra_infos):
            record_detail = self.evaluate_one(
                extracted, standard, extra_info
            )
            # 添加记录详细信息（只有 CORRECT 和 INCORRECT）
            record_details.append(record_detail)

        return ObjectEvaluationResult(
            schema_=self.schema,
            details=record_details,
        )
    