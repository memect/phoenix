"""
重构验证测试

验证 evaluator 模块重构后的功能正确性。

测试内容：
- 9.1 验证 simple_workflow 导入
- 9.2 验证 evaluation_engine 集成
- 9.3 验证 API 和 CLI

Requirements: 6.1, 6.2, 6.4, 6.5, 6.6, 7.1, 7.3
"""

import pytest
from typing import Dict, Any, List


class TestSimpleWorkflowImports:
    """9.1 验证 simple_workflow 导入 - Requirements: 6.4, 6.5, 6.6"""
    
    def test_evaluation_result_import_from_core_models(self):
        """测试 EvaluationResult 从 evaluator.core.models 导入"""
        from evaluator.core.models import EvaluationResult
        assert EvaluationResult is not None
        # 验证 EvaluationResult 有必要的属性
        assert hasattr(EvaluationResult, 'overall_accuracy')
        assert hasattr(EvaluationResult, 'total_correct')
        assert hasattr(EvaluationResult, 'total_records')
    
    def test_full_standard_import_from_evaluation_models(self):
        """测试 FullStandard 从 evaluator.core.evaluation_models 导入"""
        from evaluator.core.evaluation_models import FullStandard
        assert FullStandard is not None
        # 验证 FullStandard 可以实例化
        std = FullStandard(id="test_id", labels={"name": "test"})
        assert std.id == "test_id"
        assert std.labels == {"name": "test"}
    
    def test_full_extracted_result_import_from_evaluation_models(self):
        """测试 FullExtractedResult 从 evaluator.core.evaluation_models 导入"""
        from evaluator.core.evaluation_models import FullExtractedResult
        assert FullExtractedResult is not None
        # 验证 FullExtractedResult 可以实例化
        result = FullExtractedResult(id="test_id", labels={"name": "test"})
        assert result.id == "test_id"
        assert result.labels == {"name": "test"}
        assert result.success == True  # 默认值
    
    def test_schema_type_import_from_standards(self):
        """测试 SchemaType 从 evaluator.standards 导入"""
        from evaluator.standards import SchemaType
        assert SchemaType is not None
        # 验证 SchemaType 有必要的枚举值
        assert hasattr(SchemaType, 'OBJECT')
        assert hasattr(SchemaType, 'LIST_OF_OBJECTS')
    
    def test_all_imports_together(self):
        """测试所有导入一起工作"""
        from evaluator.core.models import EvaluationResult
        from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
        from evaluator.standards import SchemaType
        
        # 验证类型可以一起使用
        std = FullStandard(id="test", labels={"field": "value"})
        ext = FullExtractedResult(id="test", labels={"field": "value"})
        
        assert std.id == ext.id
        assert std.labels == ext.labels


class TestEvaluationEngineIntegration:
    """9.2 验证 evaluation_engine 集成 - Requirements: 6.1, 6.2"""
    
    def test_standard_set_manager_import(self):
        """测试 StandardSetManager 可正常导入"""
        from evaluator.standards import StandardSetManager
        assert StandardSetManager is not None
    
    def test_standard_set_manager_instantiation(self):
        """测试 StandardSetManager 可正常实例化"""
        from evaluator.standards import StandardSetManager
        manager = StandardSetManager()
        assert manager is not None
        assert hasattr(manager, 'load_from_directory')
        assert hasattr(manager, 'load_from_url')
    
    def test_dataset_evaluator_import(self):
        """测试 DatasetEvaluator 可正常导入"""
        from evaluator.standards import DatasetEvaluator
        assert DatasetEvaluator is not None
        assert hasattr(DatasetEvaluator, 'from_dataset')
    
    def test_standard_set_manager_has_document_methods(self):
        """测试 StandardSetManager 有文档管理方法（内联实现）"""
        from evaluator.standards import StandardSetManager
        manager = StandardSetManager()
        # 验证内联的文档管理方法存在
        assert hasattr(manager, 'get_document')
        assert hasattr(manager, 'get_documents')
        assert hasattr(manager, 'has_document')
    
    def test_dataset_evaluator_from_dataset_object_type(self):
        """测试 DatasetEvaluator.from_dataset() 返回工作的评估器 - OBJECT 类型"""
        from evaluator.standards import DatasetEvaluator, StandardSet, SchemaType
        from evaluator.standards.models import FullSchema, StandardSetMetadata
        from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
        
        # 创建测试数据集
        schema = FullSchema(
            type=SchemaType.OBJECT,
            fields={"name": "str", "age": "int"}
        )
        standards = [
            FullStandard(id="std_1", labels={"name": "张三", "age": 30}),
            FullStandard(id="std_2", labels={"name": "李四", "age": 25}),
        ]
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=2
        )
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=standards,
            metadata=metadata
        )
        
        # 创建评估器
        evaluator = DatasetEvaluator.from_dataset(dataset)
        
        # 验证评估器可以工作
        assert evaluator is not None
        assert hasattr(evaluator, 'evaluate')
        
        # 测试评估功能
        extracted_results = [
            FullExtractedResult(id="std_1", labels={"name": "张三", "age": 30}),
            FullExtractedResult(id="std_2", labels={"name": "李四", "age": 25}),
        ]
        result = evaluator.evaluate(extracted_results)
        
        assert result is not None
        assert result.total_records == 2
        assert result.total_correct == 2
        assert result.overall_accuracy == 1.0
    
    def test_dataset_evaluator_from_dataset_list_type(self):
        """测试 DatasetEvaluator.from_dataset() - LIST_OF_OBJECTS 类型"""
        from evaluator.standards import DatasetEvaluator, StandardSet, SchemaType
        from evaluator.standards.models import FullSchema, StandardSetMetadata
        from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
        
        # 创建 LIST_OF_OBJECTS 类型的数据集
        schema = FullSchema(
            type=SchemaType.LIST_OF_OBJECTS,
            fields={"name": "str"}
        )
        standards = [
            FullStandard(id="std_1", labels=[{"name": "张三"}, {"name": "李四"}]),
        ]
        metadata = StandardSetMetadata(
            name="test_list_dataset",
            schema_type="list_of_objects",
            total_standards=1
        )
        dataset = StandardSet(
            name="test_list_dataset",
            schema=schema,
            standards=standards,
            metadata=metadata
        )
        
        # 创建评估器
        evaluator = DatasetEvaluator.from_dataset(dataset)
        
        # 验证评估器可以工作
        assert evaluator is not None
        
        # 测试评估功能
        extracted_results = [
            FullExtractedResult(id="std_1", labels=[{"name": "张三"}, {"name": "李四"}]),
        ]
        result = evaluator.evaluate(extracted_results)
        
        assert result is not None
        assert result.total_records == 1
        assert result.overall_accuracy == 1.0


class TestAPIAndCLI:
    """9.3 验证 API 和 CLI - Requirements: 7.1, 7.3"""
    
    def test_compare_function_returns_valid_result(self):
        """测试 evaluator.api.compare() 返回有效结果"""
        from evaluator.api import compare
        
        result = compare(
            extracted={"name": "张三", "age": 30},
            standard={"name": "张三", "age": 30},
            schema={"name": "str", "age": "int"}
        )
        
        # 验证返回值结构
        assert result is not None
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.total_records == 1
        assert len(result.details) == result.total_records
    
    def test_compare_objects_function(self):
        """测试 compare_objects 函数"""
        from evaluator.api import compare_objects
        
        result = compare_objects(
            extracted={"name": "张三"},
            standard={"name": "张三"},
            schema={"name": "str"}
        )
        
        assert result is not None
        assert result.overall_accuracy == 1.0
        assert result.total_correct == 1
    
    def test_compare_list_of_objects_function(self):
        """测试 compare_list_of_objects 函数"""
        from evaluator.api import compare_list_of_objects
        
        result = compare_list_of_objects(
            extracted=[{"name": "张三"}, {"name": "李四"}],
            standard=[{"name": "张三"}, {"name": "李四"}],
            schema={"name": "str"}
        )
        
        assert result is not None
        assert result.overall_accuracy == 1.0
    
    def test_evaluate_batch_function(self):
        """测试 evaluate_batch() 批量评估功能"""
        from evaluator.api import evaluate_batch
        
        result = evaluate_batch(
            extracted_list=[
                {"name": "张三", "age": 30},
                {"name": "李四", "age": 25},
                {"name": "王五", "age": 35}
            ],
            standard_list=[
                {"name": "张三", "age": 30},
                {"name": "李四", "age": 25},
                {"name": "王五", "age": 35}
            ],
            schema={"name": "str", "age": "int"}
        )
        
        # 验证批量评估结果
        assert result is not None
        assert result.total_records == 3
        assert result.total_correct == 3
        assert result.overall_accuracy == 1.0
        assert len(result.details) == 3
    
    def test_evaluate_batch_partial_match(self):
        """测试 evaluate_batch 部分匹配情况"""
        from evaluator.api import evaluate_batch
        
        result = evaluate_batch(
            extracted_list=[
                {"name": "张三", "age": 30},
                {"name": "李四", "age": 26},  # age 不匹配
            ],
            standard_list=[
                {"name": "张三", "age": 30},
                {"name": "李四", "age": 25},
            ],
            schema={"name": "str", "age": "int"}
        )
        
        assert result is not None
        assert result.total_records == 2
        assert result.total_correct == 1
        assert result.overall_accuracy == 0.5
    
    def test_evaluate_batch_with_custom_ids(self):
        """测试 evaluate_batch 使用自定义 ID"""
        from evaluator.api import evaluate_batch
        
        result = evaluate_batch(
            extracted_list=[{"name": "张三"}],
            standard_list=[{"name": "张三"}],
            schema={"name": "str"},
            ids=["custom_id_1"]
        )
        
        assert result is not None
        assert result.total_records == 1
        # 验证使用了自定义 ID
        assert result.details[0].standared_info.id == "custom_id_1"
    
    def test_api_result_accuracy_bounds(self):
        """Property 2: API Correctness - 验证准确率在 0.0 到 1.0 之间"""
        from evaluator.api import compare, evaluate_batch
        
        # 测试完全匹配
        result1 = compare(
            extracted={"name": "test"},
            standard={"name": "test"},
            schema={"name": "str"}
        )
        assert 0.0 <= result1.overall_accuracy <= 1.0
        
        # 测试完全不匹配
        result2 = compare(
            extracted={"name": "wrong"},
            standard={"name": "test"},
            schema={"name": "str"}
        )
        assert 0.0 <= result2.overall_accuracy <= 1.0
        
        # 测试批量评估
        result3 = evaluate_batch(
            extracted_list=[{"name": "a"}, {"name": "b"}],
            standard_list=[{"name": "a"}, {"name": "c"}],
            schema={"name": "str"}
        )
        assert 0.0 <= result3.overall_accuracy <= 1.0
        assert result3.total_records == len(result3.details)


class TestAPICorrectnessProperty:
    """
    Property 2: API Correctness - 属性测试
    
    *For any* valid call to `compare()`, `compare_objects()`, `compare_list_of_objects()`, 
    or `evaluate_batch()`, the API SHALL return an `EvaluationResult` object with:
    - Non-negative `overall_accuracy` between 0.0 and 1.0
    - `total_records` equal to the number of input records
    - `details` list with length equal to `total_records`
    
    **Feature: evaluator-refactor, Property 2: API Correctness**
    **Validates: Requirements 2.8, 7.1, 7.3**
    """
    
    @pytest.mark.parametrize("num_records", [1, 2, 5, 10])
    def test_evaluate_batch_total_records_equals_input(self, num_records):
        """验证 total_records 等于输入记录数"""
        from evaluator.api import evaluate_batch
        
        extracted_list = [{"name": f"name_{i}"} for i in range(num_records)]
        standard_list = [{"name": f"name_{i}"} for i in range(num_records)]
        
        result = evaluate_batch(
            extracted_list=extracted_list,
            standard_list=standard_list,
            schema={"name": "str"}
        )
        
        assert result.total_records == num_records
        assert len(result.details) == num_records
    
    @pytest.mark.parametrize("match_count,total", [
        (0, 3),   # 0% 匹配
        (1, 3),   # 33% 匹配
        (2, 3),   # 67% 匹配
        (3, 3),   # 100% 匹配
    ])
    def test_accuracy_bounds_various_match_rates(self, match_count, total):
        """验证不同匹配率下准确率在 0.0 到 1.0 之间"""
        from evaluator.api import evaluate_batch
        
        # 创建测试数据：前 match_count 个匹配，其余不匹配
        extracted_list = []
        standard_list = []
        for i in range(total):
            if i < match_count:
                extracted_list.append({"name": f"match_{i}"})
                standard_list.append({"name": f"match_{i}"})
            else:
                extracted_list.append({"name": f"wrong_{i}"})
                standard_list.append({"name": f"correct_{i}"})
        
        result = evaluate_batch(
            extracted_list=extracted_list,
            standard_list=standard_list,
            schema={"name": "str"}
        )
        
        # 验证准确率在有效范围内
        assert 0.0 <= result.overall_accuracy <= 1.0
        # 验证准确率计算正确
        expected_accuracy = match_count / total
        assert abs(result.overall_accuracy - expected_accuracy) < 0.01
    
    def test_compare_objects_returns_valid_result(self):
        """验证 compare_objects 返回有效结果"""
        from evaluator.api import compare_objects
        
        result = compare_objects(
            extracted={"field1": "value1", "field2": "value2"},
            standard={"field1": "value1", "field2": "value2"},
            schema={"field1": "str", "field2": "str"}
        )
        
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.total_records == 1
        assert len(result.details) == 1
    
    def test_compare_list_of_objects_returns_valid_result(self):
        """验证 compare_list_of_objects 返回有效结果"""
        from evaluator.api import compare_list_of_objects
        
        result = compare_list_of_objects(
            extracted=[{"name": "a"}, {"name": "b"}, {"name": "c"}],
            standard=[{"name": "a"}, {"name": "b"}, {"name": "c"}],
            schema={"name": "str"}
        )
        
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.total_records == 1  # list_of_objects 作为一条记录
        assert len(result.details) == 1
    
    def test_compare_auto_detect_type(self):
        """验证 compare 自动检测类型"""
        from evaluator.api import compare
        
        # 测试 object 类型
        result_obj = compare(
            extracted={"name": "test"},
            standard={"name": "test"},
            schema={"name": "str"}
        )
        assert 0.0 <= result_obj.overall_accuracy <= 1.0
        assert result_obj.total_records == 1
        
        # 测试 list_of_objects 类型
        result_list = compare(
            extracted=[{"name": "a"}],
            standard=[{"name": "a"}],
            schema={"name": "str"}
        )
        assert 0.0 <= result_list.overall_accuracy <= 1.0
        assert result_list.total_records == 1


class TestEvaluatorModuleExports:
    """验证 evaluator 模块的导出正确性"""
    
    def test_evaluator_main_exports(self):
        """测试 evaluator 主模块导出"""
        from evaluator import (
            ObjectEvaluator,
            ListOfObjectsEvaluator,
            Schema,
            EvaluationResult,
            get_evaluate_parts,
        )
        
        assert ObjectEvaluator is not None
        assert ListOfObjectsEvaluator is not None
        assert Schema is not None
        assert EvaluationResult is not None
        assert get_evaluate_parts is not None
    
    def test_evaluator_core_exports(self):
        """测试 evaluator.core 模块导出"""
        from evaluator.core import (
            Schema,
            FieldType,
            EvaluationResult,
            FullStandard,
            FullExtractedResult,
            Evaluator,
        )
        
        assert Schema is not None
        assert FieldType is not None
        assert EvaluationResult is not None
        assert FullStandard is not None
        assert FullExtractedResult is not None
        assert Evaluator is not None
    
    def test_evaluator_standards_exports(self):
        """测试 evaluator.standards 模块导出"""
        from evaluator.standards import (
            StandardSet,
            StandardSetManager,
            DatasetEvaluator,
            SchemaType,
        )
        
        assert StandardSet is not None
        assert StandardSetManager is not None
        assert DatasetEvaluator is not None
        assert SchemaType is not None
    
    def test_no_deprecated_exports(self):
        """验证已删除的类不再导出"""
        import evaluator
        
        # 验证 DataCreator 不再导出
        assert not hasattr(evaluator, 'DataCreator')
        
        # 验证 DocumentManager 不再导出
        assert not hasattr(evaluator, 'DocumentManager')



class TestAPICorrectnessPropertyBased:
    """
    Property 2: API Correctness - 基于 Hypothesis 的属性测试
    
    **Feature: evaluator-refactor, Property 2: API Correctness**
    **Validates: Requirements 2.8, 7.1, 7.3**
    """
    
    @pytest.mark.parametrize("num_records", [1, 3, 5, 10, 20])
    def test_evaluate_batch_property_total_records(self, num_records):
        """
        Property: For any batch evaluation, total_records equals input count
        
        **Feature: evaluator-refactor, Property 2: API Correctness**
        """
        from evaluator.api import evaluate_batch
        import random
        
        # 生成随机数据
        extracted_list = []
        standard_list = []
        for i in range(num_records):
            # 随机决定是否匹配
            if random.random() > 0.5:
                value = f"value_{i}"
                extracted_list.append({"name": value, "count": i})
                standard_list.append({"name": value, "count": i})
            else:
                extracted_list.append({"name": f"extracted_{i}", "count": i})
                standard_list.append({"name": f"standard_{i}", "count": i})
        
        result = evaluate_batch(
            extracted_list=extracted_list,
            standard_list=standard_list,
            schema={"name": "str", "count": "int"}
        )
        
        # Property: total_records == input count
        assert result.total_records == num_records
        # Property: details length == total_records
        assert len(result.details) == result.total_records
        # Property: accuracy in [0, 1]
        assert 0.0 <= result.overall_accuracy <= 1.0
    
    def test_evaluate_batch_property_accuracy_calculation(self):
        """
        Property: overall_accuracy = total_correct / total_records
        
        **Feature: evaluator-refactor, Property 2: API Correctness**
        """
        from evaluator.api import evaluate_batch
        from evaluator.core.models import RecordDetailType
        
        # 创建已知匹配模式的数据
        extracted_list = [
            {"name": "match1"},
            {"name": "match2"},
            {"name": "wrong"},
            {"name": "match4"},
        ]
        standard_list = [
            {"name": "match1"},
            {"name": "match2"},
            {"name": "correct"},
            {"name": "match4"},
        ]
        
        result = evaluate_batch(
            extracted_list=extracted_list,
            standard_list=standard_list,
            schema={"name": "str"}
        )
        
        # 手动计算正确数
        correct_count = sum(
            1 for d in result.details 
            if d.type == RecordDetailType.CORRECT
        )
        
        # Property: total_correct matches actual correct count
        assert result.total_correct == correct_count
        
        # Property: accuracy = correct / total
        expected_accuracy = correct_count / len(extracted_list)
        assert abs(result.overall_accuracy - expected_accuracy) < 0.001
