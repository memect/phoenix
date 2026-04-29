"""数据集评估器工厂 - 从数据集创建对应的评估器"""

from typing import Union, List, Dict, Any, Optional

from numpy import std

from evaluator.core.models import RecordDetailBase
from .models import StandardSet, SchemaType
from ..evaluators.object import ObjectEvaluator, ObjectEvaluationResult
from ..evaluators.list_of_objects import ListOfObjectsEvaluator, ListOfObjectsEvaluationResult
from ..core.evaluation_models import FullExtractedResult, FullStandard


class DatasetBoundEvaluator:
    """绑定了标准答案的评估器 - 提供简化的评估接口"""
    
    def __init__(self, 
                 base_evaluator: Union[ObjectEvaluator, ListOfObjectsEvaluator],
                 dataset: StandardSet,
                 ):
        """
        初始化绑定了标准答案的评估器
        
        Args:
            base_evaluator: 基础评估器（合并后的 ObjectEvaluator 或 ListOfObjectsEvaluator）
            standards: 标准答案列表
        """
        self.base_evaluator = base_evaluator
        self.dataset = dataset
        standards = dataset.standards
        self.standards = standards
        # 创建ID到标准答案的映射，方便查找
        self.standards_by_id = {std.id: std for std in standards}
    
    def evaluate(self, 
                extracted_results: Union[List[Dict[str, Any]], List[FullExtractedResult]],
                extra_infos: Optional[List[Dict[str, Any]]] = None,
                match_by_index: bool = True):
        """
        简化的评估接口
        
        Args:
            extracted_results: 提取结果列表，可以是：
                - List[Dict]: 简单的字典列表，通过索引匹配
                - List[FullExtractedResult]: 完整结果列表，通过ID匹配
            extra_infos: 可选的额外信息
            match_by_index: True=按索引匹配，False=按ID匹配
            
        Returns:
            评估结果
        """
        # 转换为FullExtractedResult格式
        full_extracted_results = self._convert_to_full_results(extracted_results, match_by_index)
        
        # 匹配对应的标准答案
        matched_standards = self._match_standards(full_extracted_results, match_by_index)
        
        # 调用基础评估器
        result = self.base_evaluator.evaluate(
            extracted_results=full_extracted_results,
            standard_results=matched_standards,
            extra_infos=extra_infos
        )
        return result
    
    def evaluate_by_std_id(self, extracted_result: FullExtractedResult, std_id: str) -> RecordDetailBase|None:  # type: ignore
        standard = self.dataset.get_standard(std_id)
        if standard is None:
            raise ValueError(f"标准ID: {std_id}不存在")
        else:
            return self.base_evaluator.evaluate_one(extracted_result, standard)

    
    def _convert_to_full_results(self, 
                               extracted_results: Union[List[Dict[str, Any]], List[FullExtractedResult]], 
                               match_by_index: bool) -> List[FullExtractedResult]:
        """转换提取结果为FullExtractedResult格式"""
        
        if not extracted_results:
            return []
            
        # 如果已经是FullExtractedResult，直接返回
        if extracted_results and isinstance(extracted_results[0], FullExtractedResult):
            return extracted_results  # type: ignore
        
        # 转换字典列表为FullExtractedResult
        full_results = []
        for i, result in enumerate(extracted_results):
            if isinstance(result, dict):
                if match_by_index:
                    # 按索引匹配，使用对应标准答案的ID
                    result_id = self.standards[i].id if i < len(self.standards) else f"extracted_{i}"
                    result_data = result
                else:
                    # 按ID匹配，期望result是包含id字段的字典
                    result_id = result.get('id', f"extracted_{i}")
                    result_data = {k: v for k, v in result.items() if k != 'id'}  # 移除id字段
                
                # 创建FullExtractedResult实例
                full_result = FullExtractedResult.success_result(data=result_data)
                full_result.id = result_id  # 设置ID
                full_results.append(full_result)
            else:
                # 如果不是字典，假设是其他类型的数据，转换为字典格式
                result_id = f"extracted_{i}"
                # 将非字典数据包装为字典
                result_data = {"data": result} if not isinstance(result, dict) else result
                full_result = FullExtractedResult.success_result(data=result_data)
                full_result.id = result_id
                full_results.append(full_result)
        
        return full_results
    
    def _match_standards(self, 
                        full_extracted_results: List[FullExtractedResult], 
                        match_by_index: bool) -> List[FullStandard]:
        """匹配对应的标准答案"""
        
        matched_standards = []
        
        for i, extracted in enumerate(full_extracted_results):
            if match_by_index:
                # 按索引匹配
                if i < len(self.standards):
                    matched_standards.append(self.standards[i])
                else:
                    raise ValueError(f"提取结果索引 {i} 超出标准答案范围")
            else:
                # 按ID匹配
                if extracted.id in self.standards_by_id:
                    matched_standards.append(self.standards_by_id[extracted.id])
                else:
                    raise ValueError(f"找不到ID为 {extracted.id} 的标准答案")
        
        return matched_standards


class DatasetEvaluator:
    """数据集评估器工厂类 - 负责从数据集创建对应的评估器"""
    
    @staticmethod
    def from_dataset(dataset: StandardSet) -> DatasetBoundEvaluator:
        """
        从数据集创建绑定了标准答案的评估器
        
        Args:
            dataset: 标准数据集对象
            
        Returns:
            DatasetBoundEvaluator: 绑定了标准答案的评估器
            
        Raises:
            ValueError: 当数据集的schema_type不支持时
        """
        schema_type = dataset.schema.type
        
        if schema_type == SchemaType.OBJECT:
            base_evaluator: Union[ObjectEvaluator, ListOfObjectsEvaluator] = ObjectEvaluator(dataset.schema)
        elif schema_type == SchemaType.LIST_OF_OBJECTS:
            base_evaluator = ListOfObjectsEvaluator(dataset.schema)
        else:
            raise ValueError(f"不支持的schema类型: {schema_type}")
        
        return DatasetBoundEvaluator(base_evaluator, dataset=dataset)
    
    @staticmethod
    def evaluate_with_dataset(
        dataset: StandardSet,
        extracted_results: List[FullExtractedResult],
        extra_infos: Optional[List[Dict[str, Any]]] = None
    ):
        """
        使用数据集直接评估提取结果
        
        Args:
            dataset: 标准数据集对象
            extracted_results: 提取结果列表
            extra_infos: 可选的额外信息
            
        Returns:
            评估结果对象 (ObjectEvaluationResult 或 ListOfObjectsEvaluationResult)
        """
        # 创建对应的评估器
        evaluator = DatasetEvaluator.from_dataset(dataset)
        
        # 使用数据集中的标准进行评估 (通过DatasetBoundEvaluator)
        return evaluator.base_evaluator.evaluate(
            extracted_results=extracted_results,
            standard_results=dataset.standards,
            extra_infos=extra_infos
        )
