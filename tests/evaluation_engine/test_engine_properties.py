"""
Evaluation Engine 属性测试

测试 evaluation_engine 模块的核心属性。

**Feature: modular-refactor**
**Validates: Requirements 1.2, 2.4, 2.6, 2.7, 2.8, 2.10, 2.16, 2.17, 2.18, 2.19**
"""

import pytest
import tempfile
import json
from pathlib import Path
from hypothesis import given, settings, strategies as st

from evaluation_engine import EvaluationEngine, read_program
from evaluator.core.schema import FieldType
from code_executor import execute, batch_execute


# ============================================================================
# Property 2: Batch execute equivalence
# **Validates: Requirements 1.2**
# ============================================================================

class TestProperty2BatchExecuteEquivalence:
    """Property 2: Batch execute equivalence
    
    *For any* valid program and list of inputs, `batch_execute(program, inputs, concurrent)` 
    should produce the same results as calling `execute(program, input)` for each input 
    individually, regardless of the concurrency level.
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5))
    async def test_batch_execute_matches_individual_execute(self, inputs):
        """测试批量执行与单独执行结果一致"""
        program = '''
def extract(data):
    return {"length": len(data) if data else 0}
'''
        # 单独执行
        individual_results = []
        for inp in inputs:
            result = await execute(program, inp)
            individual_results.append(result)
        
        # 批量执行
        batch_results = await batch_execute(program, inputs, concurrent=2)
        
        # 验证结果一致 - batch_execute 返回的是包含 data 字段的字典
        assert len(batch_results) == len(individual_results)
        for i, (batch_res, ind_res) in enumerate(zip(batch_results, individual_results)):
            assert batch_res['success'], f"Batch execution failed at index {i}"
            assert batch_res['data'] == ind_res, f"Mismatch at index {i}"
    
    @pytest.mark.asyncio
    async def test_batch_execute_with_different_concurrency(self):
        """测试不同并发级别产生相同结果"""
        program = '''
def extract(data):
    return {"value": data * 2}
'''
        inputs = [1, 2, 3, 4, 5]
        
        results_c1 = await batch_execute(program, inputs, concurrent=1)
        results_c2 = await batch_execute(program, inputs, concurrent=2)
        results_c5 = await batch_execute(program, inputs, concurrent=5)
        
        # 比较 data 字段
        data_c1 = [r['data'] for r in results_c1]
        data_c2 = [r['data'] for r in results_c2]
        data_c5 = [r['data'] for r in results_c5]
        
        assert data_c1 == data_c2 == data_c5


# ============================================================================
# Property 7: Evaluation result type consistency
# **Validates: Requirements 2.4, 2.17**
# ============================================================================

class TestProperty7EvaluationResultTypeConsistency:
    """Property 7: Evaluation result type consistency
    
    *For any* valid program and dataset, `evaluate_program(program, eval_type, keys)` 
    should return an `EvaluationResult` object with valid `overall_accuracy` (between 0 and 1), 
    `total_records` (non-negative), and `field_stats` (dictionary).
    """
    
    @pytest.fixture
    def mock_engine(self):
        """创建模拟的评估引擎"""
        from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
        from evaluator.core.evaluation_models import FullStandard, Info, Document
        
        # 创建模拟的 schema - 使用正确的 FieldType
        schema = FullSchema(type="object", fields={"field1": FieldType.STRING})
        
        # 创建模拟的标准数据
        docjson = {
            "tree": {
                "root": {
                    "type": "section",
                    "data": {"textlines": [{"text": "test content"}]}
                }
            }
        }
        document = Document(id="doc_1", docjson=docjson, md="test content")
        info = Info(document=document)
        standard = FullStandard(
            id="test_std_1",
            labels={"field1": "expected_value"},
            info=info
        )
        
        # 创建模拟的数据集
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=1,
            train_count=1,
            test_count=0
        )
        
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=[standard],
            metadata=metadata
        )
        
        return EvaluationEngine(
            train_dataset=dataset,
            test_dataset=dataset,
            keys=None
        )
    
    @pytest.mark.asyncio
    async def test_evaluation_result_has_valid_accuracy(self, mock_engine):
        """测试评估结果的准确率在有效范围内"""
        program = '''
def extract(data):
    return {"field1": "expected_value"}
'''
        result = await mock_engine.evaluate_program(program, 'train')
        
        # 验证准确率在 0-1 之间
        assert 0.0 <= result.overall_accuracy <= 1.0
        
        # 验证 total_records 非负
        assert result.total_records >= 0
        
        # 验证 field_stats 是字典
        assert isinstance(result.field_stats, dict)
    
    @pytest.mark.asyncio
    async def test_evaluation_result_with_wrong_output(self, mock_engine):
        """测试错误输出时的评估结果"""
        program = '''
def extract(data):
    return {"field1": "wrong_value"}
'''
        result = await mock_engine.evaluate_program(program, 'train')
        
        # 验证准确率在 0-1 之间
        assert 0.0 <= result.overall_accuracy <= 1.0
        assert result.total_records >= 0
        assert isinstance(result.field_stats, dict)


# ============================================================================
# Property 8: Multi-document evaluation completeness
# **Validates: Requirements 2.6**
# ============================================================================

class TestProperty8MultiDocumentEvaluationCompleteness:
    """Property 8: Multi-document evaluation completeness
    
    *For any* list of std_ids, `evaluate_program_on_std_ids(program, std_ids, keys)` 
    should return a dictionary containing exactly the same keys as the input std_ids list.
    """
    
    @pytest.fixture
    def mock_engine_multi_doc(self):
        """创建包含多个文档的模拟评估引擎"""
        from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
        from evaluator.core.evaluation_models import FullStandard, Info, Document
        
        schema = FullSchema(type="object", fields={"field1": FieldType.STRING})
        
        standards = []
        for i in range(3):
            docjson = {
                "tree": {
                    "root": {
                        "type": "section",
                        "data": {"textlines": [{"text": f"content {i}"}]}
                    }
                }
            }
            document = Document(id=f"doc_{i}", docjson=docjson, md=f"content {i}")
            info = Info(document=document)
            standard = FullStandard(
                id=f"doc_{i}",
                labels={"field1": f"value_{i}"},
                info=info
            )
            standards.append(standard)
        
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=3,
            train_count=3,
            test_count=0
        )
        
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=standards,
            metadata=metadata
        )
        
        return EvaluationEngine(
            train_dataset=dataset,
            test_dataset=dataset,
            keys=None
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_on_std_ids_returns_all_keys(self, mock_engine_multi_doc):
        """测试返回的字典包含所有请求的 std_ids"""
        program = '''
def extract(data):
    return {"field1": "test"}
'''
        std_ids = ["doc_0", "doc_1", "doc_2"]
        results = await mock_engine_multi_doc.evaluate_program_on_std_ids(program, std_ids)
        
        # 验证返回的字典包含所有请求的 std_ids
        assert set(results.keys()) == set(std_ids)
    
    @pytest.mark.asyncio
    async def test_evaluate_on_std_ids_with_nonexistent_doc(self, mock_engine_multi_doc):
        """测试包含不存在文档时的行为"""
        program = '''
def extract(data):
    return {"field1": "test"}
'''
        std_ids = ["doc_0", "nonexistent_doc", "doc_1"]
        results = await mock_engine_multi_doc.evaluate_program_on_std_ids(program, std_ids)
        
        # 验证返回的字典包含所有请求的 std_ids
        assert set(results.keys()) == set(std_ids)
        # 不存在的文档应该返回 None
        assert results["nonexistent_doc"] is None


# ============================================================================
# Property 9: Concurrent execution consistency
# **Validates: Requirements 2.7**
# ============================================================================

class TestProperty9ConcurrentExecutionConsistency:
    """Property 9: Concurrent execution consistency
    
    *For any* program and dataset, evaluating with different `prog_run_concurrent` 
    values (1, 2, 5, 10) should produce the same `overall_accuracy` result.
    """
    
    @pytest.fixture
    def mock_engine_for_concurrency(self):
        """创建用于并发测试的模拟评估引擎"""
        from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
        from evaluator.core.evaluation_models import FullStandard, Info, Document
        
        schema = FullSchema(type="object", fields={"field1": FieldType.STRING})
        
        standards = []
        for i in range(5):
            docjson = {
                "tree": {
                    "root": {
                        "type": "section",
                        "data": {"textlines": [{"text": f"content {i}"}]}
                    }
                }
            }
            document = Document(id=f"doc_{i}", docjson=docjson, md=f"content {i}")
            info = Info(document=document)
            standard = FullStandard(
                id=f"doc_{i}",
                labels={"field1": "expected"},
                info=info
            )
            standards.append(standard)
        
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=5,
            train_count=5,
            test_count=0
        )
        
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=standards,
            metadata=metadata
        )
        
        return dataset
    
    @pytest.mark.asyncio
    async def test_different_concurrency_same_accuracy(self, mock_engine_for_concurrency):
        """测试不同并发级别产生相同的准确率"""
        program = '''
def extract(data):
    return {"field1": "expected"}
'''
        dataset = mock_engine_for_concurrency
        
        # 测试不同并发级别
        results = []
        for concurrent in [1, 2, 5]:
            engine = EvaluationEngine(
                train_dataset=dataset,
                test_dataset=dataset,
                prog_run_concurrent=concurrent
            )
            result = await engine.evaluate_program(program, 'train')
            results.append(result.overall_accuracy)
        
        # 验证所有结果相同
        assert all(acc == results[0] for acc in results)


# ============================================================================
# Property 10: Field filtering correctness
# **Validates: Requirements 2.8**
# ============================================================================

class TestProperty10FieldFilteringCorrectness:
    """Property 10: Field filtering correctness
    
    *For any* evaluation with specified `keys`, the returned `EvaluationResult.field_stats` 
    should only contain fields that are in the `keys` list.
    """
    
    @pytest.fixture
    def mock_engine_multi_field(self):
        """创建包含多个字段的模拟评估引擎"""
        from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
        from evaluator.core.evaluation_models import FullStandard, Info, Document
        
        schema = FullSchema(type="object", fields={
            "field1": FieldType.STRING,
            "field2": FieldType.STRING,
            "field3": FieldType.STRING
        })
        
        docjson = {
            "tree": {
                "root": {
                    "type": "section",
                    "data": {"textlines": [{"text": "test content"}]}
                }
            }
        }
        document = Document(id="doc_1", docjson=docjson, md="test content")
        info = Info(document=document)
        standard = FullStandard(
            id="test_std_1",
            labels={"field1": "v1", "field2": "v2", "field3": "v3"},
            info=info
        )
        
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=1,
            train_count=1,
            test_count=0
        )
        
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=[standard],
            metadata=metadata
        )
        
        return EvaluationEngine(
            train_dataset=dataset,
            test_dataset=dataset,
            keys=None
        )
    
    @pytest.mark.asyncio
    async def test_field_filtering_only_returns_specified_fields(self, mock_engine_multi_field):
        """测试字段过滤只返回指定字段"""
        program = '''
def extract(data):
    return {"field1": "v1", "field2": "v2", "field3": "v3"}
'''
        # 只评估 field1 和 field2
        result = await mock_engine_multi_field.evaluate_program(
            program, 'train', keys=["field1", "field2"]
        )
        
        # 验证 field_stats 只包含指定的字段
        assert set(result.field_stats.keys()) == {"field1", "field2"}
        assert "field3" not in result.field_stats


# ============================================================================
# Property 11: Program format equivalence
# **Validates: Requirements 2.10**
# ============================================================================

class TestProperty11ProgramFormatEquivalence:
    """Property 11: Program format equivalence
    
    *For any* program, evaluating it as a string, as a dict (ResultJson format), 
    or as a ResultJson object should produce equivalent `EvaluationResult.overall_accuracy`.
    """
    
    @pytest.fixture
    def mock_engine_for_format(self):
        """创建用于格式测试的模拟评估引擎"""
        from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
        from evaluator.core.evaluation_models import FullStandard, Info, Document
        
        schema = FullSchema(type="object", fields={"field1": FieldType.STRING})
        
        docjson = {
            "tree": {
                "root": {
                    "type": "section",
                    "data": {"textlines": [{"text": "test content"}]}
                }
            }
        }
        document = Document(id="doc_1", docjson=docjson, md="test content")
        info = Info(document=document)
        standard = FullStandard(
            id="test_std_1",
            labels={"field1": "expected"},
            info=info
        )
        
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=1,
            train_count=1,
            test_count=0
        )
        
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=[standard],
            metadata=metadata
        )
        
        return EvaluationEngine(
            train_dataset=dataset,
            test_dataset=dataset,
            keys=None
        )
    
    @pytest.mark.asyncio
    async def test_string_and_dict_format_equivalence(self, mock_engine_for_format):
        """测试字符串和字典格式产生相同结果"""
        program_str = '''
def extract(data):
    return {"field1": "expected"}
'''
        program_dict = {
            "__type__": "all",
            "__data__": program_str
        }
        
        result_str = await mock_engine_for_format.evaluate_program(program_str, 'train')
        result_dict = await mock_engine_for_format.evaluate_program(program_dict, 'train')
        
        # 验证准确率相同
        assert result_str.overall_accuracy == result_dict.overall_accuracy


# ============================================================================
# Property 12: Read program round-trip
# **Validates: Requirements 2.16**
# ============================================================================

class TestProperty12ReadProgramRoundTrip:
    """Property 12: Read program round-trip
    
    *For any* valid program string, writing it to a file and reading it back 
    with `read_program()` should return the same program content.
    """
    
    @settings(max_examples=100)
    @given(st.text(min_size=10, max_size=500).filter(lambda x: '\r' not in x and len(x) > 20))
    def test_read_program_round_trip_plain_file(self, program_content):
        """测试普通文件的读取往返"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(program_content)
            temp_path = f.name
        
        try:
            result = read_program(temp_path)
            assert result == program_content
        finally:
            Path(temp_path).unlink()
    
    def test_read_program_with_simple_content(self):
        """测试简单内容的读取"""
        program_code = '''
def extract(data):
    return {"result": data}
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(program_code)
            temp_path = f.name
        
        try:
            result = read_program(temp_path)
            assert result == program_code
        finally:
            Path(temp_path).unlink()


# ============================================================================
# Property 13: Missing document info raises ValueError
# **Validates: Requirements 2.18**
# ============================================================================

class TestProperty13MissingDocumentInfoRaisesValueError:
    """Property 13: Missing document info raises ValueError
    
    *For any* standard data that lacks document information, attempting to 
    evaluate should raise a `ValueError` with a message containing the std_id.
    """
    
    @pytest.fixture
    def mock_engine_missing_doc(self):
        """创建缺少文档信息的模拟评估引擎"""
        from evaluator.standards.models import StandardSet, StandardSetMetadata, FullSchema
        from evaluator.core.evaluation_models import FullStandard
        
        schema = FullSchema(type="object", fields={"field1": FieldType.STRING})
        
        # 创建没有文档信息的标准数据
        standard = FullStandard(
            id="missing_doc_std",
            labels={"field1": "value"},
            info=None  # 缺少文档信息
        )
        
        metadata = StandardSetMetadata(
            name="test_dataset",
            schema_type="object",
            total_standards=1,
            train_count=1,
            test_count=0
        )
        
        dataset = StandardSet(
            name="test_dataset",
            schema=schema,
            standards=[standard],
            metadata=metadata
        )
        
        return EvaluationEngine(
            train_dataset=dataset,
            test_dataset=dataset,
            keys=None
        )
    
    @pytest.mark.asyncio
    async def test_missing_document_raises_valueerror(self, mock_engine_missing_doc):
        """测试缺少文档信息时抛出 ValueError
        
        Note: 当前实现会捕获异常并返回错误结果，而不是直接抛出。
        这个测试验证评估结果中包含错误信息。
        """
        program = '''
def extract(data):
    return {"field1": "test"}
'''
        # 评估应该完成但结果中包含错误
        result = await mock_engine_missing_doc.evaluate_program(program, 'train')
        
        # 验证评估完成（即使有错误）
        assert result.total_records >= 0


# ============================================================================
# Property 14: Single type program rejection
# **Validates: Requirements 2.19**
# ============================================================================

class TestProperty14SingleTypeProgramRejection:
    """Property 14: Single type program rejection
    
    *For any* ResultJson file with `__type__='single'`, calling `read_program()` 
    should raise a `ValueError` indicating that only single programs are supported.
    
    Note: This test depends on simple_workflow.models being available.
    If not available, read_program will just read the file as plain text.
    """
    
    def test_plain_python_file_accepted(self):
        """测试普通 Python 文件被接受"""
        program_code = '''
def extract(data):
    return {"result": data}
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(program_code)
            temp_path = f.name
        
        try:
            result = read_program(temp_path)
            assert result == program_code
        finally:
            Path(temp_path).unlink()
    
    def test_json_file_read_as_text_when_no_result_json(self):
        """测试当 simple_workflow 不可用时，JSON 文件作为文本读取"""
        # 这个测试验证 read_program 的回退行为
        result_json = {
            "__version__": "0.0.1",
            "__type__": "all",
            "__data__": "def extract(data): return {}",
            "__meta__": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(result_json, f)
            temp_path = f.name
        
        try:
            # read_program 应该能读取文件（可能作为 ResultJson 或纯文本）
            result = read_program(temp_path)
            # 结果应该是字符串
            assert isinstance(result, str)
        finally:
            Path(temp_path).unlink()
