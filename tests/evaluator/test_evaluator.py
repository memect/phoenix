from evaluator import get_evaluate_parts, Schema, FieldType
from evaluator.evaluators.object.models import Standard, ExtractedResult
from evaluator.api import compare, compare_objects, compare_list_of_objects, evaluate_batch
import pytest

@pytest.fixture
def std_json():
    return [
        {
            "id": "1",
            "labels": {"name": "John", "age": 30},
        }
    ]

@pytest.fixture
def extracted_json():
    return [
        {
            "labels": {"name": "John", "age": 30},
        }
    ]

@pytest.fixture
def schema_with_fields():
    return Schema(fields={
        "name": FieldType.STRING,
        "age": FieldType.INTEGER,
        "score": FieldType.FLOAT,
        "active": FieldType.BOOLEAN,
        "tags": FieldType.LIST
    })

@pytest.fixture
def empty_schema():
    return Schema(fields={})

def test_get_evaluate_parts():
    # 使用有效的Schema
    valid_schema = Schema(fields={"name": FieldType.STRING})
    parts = get_evaluate_parts('object', valid_schema)
    assert parts.evaluator is not None
    
    # 测试list_of_objects类型
    parts_list = get_evaluate_parts('list_of_objects', valid_schema)
    assert parts_list.evaluator is not None
    
    # 测试无效类型
    with pytest.raises(ValueError, match="Invalid type: invalid_type"):
        get_evaluate_parts('invalid_type', valid_schema)

def test_object_evaluator():
    # 使用有效的Schema
    valid_schema = Schema(fields={"name": FieldType.STRING})
    parts = get_evaluate_parts('object', valid_schema)
    assert parts.evaluator is not None
    
    # 测试评估器初始化
    evaluator = parts.evaluator
    assert evaluator.schema is not None
    assert isinstance(evaluator.schema, Schema)
    
    # 测试从字典创建Schema
    dict_schema = {"name": "str", "age": "int"}
    parts_dict = get_evaluate_parts('object', dict_schema)
    assert parts_dict.evaluator.schema is not None
    assert "name" in parts_dict.evaluator.schema.fields
    assert "age" in parts_dict.evaluator.schema.fields

def test_list_of_objects_evaluator():
    # 使用有效的Schema
    valid_schema = Schema(fields={"name": FieldType.STRING})
    parts = get_evaluate_parts('list_of_objects', valid_schema)
    assert parts.evaluator is not None
    
    # 测试评估器初始化
    evaluator = parts.evaluator
    assert evaluator.schema is not None
    assert isinstance(evaluator.schema, Schema)
    assert evaluator.similarity_threshold == 0.5  # 默认值
    
    # 测试从字典创建Schema
    dict_schema = {"name": "str", "age": "int"}
    parts_dict = get_evaluate_parts('list_of_objects', dict_schema)
    assert parts_dict.evaluator.schema is not None
    assert "name" in parts_dict.evaluator.schema.fields
    assert "age" in parts_dict.evaluator.schema.fields

def test_schema_validation():
    # 测试空Schema验证
    with pytest.raises(ValueError, match="schema不能为空"):
        Schema(fields={})
    
    # 测试有效Schema
    valid_schema = Schema(fields={"name": FieldType.STRING})
    assert valid_schema.fields["name"] == FieldType.STRING
    
    # 测试从字典创建Schema
    schema_dict = {"name": "str", "age": "int", "score": "float"}
    schema = Schema.from_dict(schema_dict)
    assert schema.fields["name"] == FieldType.STRING
    assert schema.fields["age"] == FieldType.INTEGER
    assert schema.fields["score"] == FieldType.FLOAT
    
    # 测试无效类型转换为字符串类型
    schema_dict_invalid = {"name": "invalid_type"}
    schema_invalid = Schema.from_dict(schema_dict_invalid)
    assert schema_invalid.fields["name"] == FieldType.STRING



def test_standard_model():
    # 测试标准模型创建
    standard = Standard(id="1", labels={"name": "John"})
    assert standard.id == "1"
    assert standard.labels["name"] == "John"
    
    # 测试嵌套结构
    nested_labels = {"user": {"name": "John", "age": 30}}
    nested_standard = Standard(id="2", labels=nested_labels)
    assert nested_standard.labels["user"]["name"] == "John"


def test_get_evaluate_parts_til_evaluate():
    """
    测试从get_evaluate_parts函数获取评估器，并测试准确率评估结果
    使用 API 函数进行测试
    """
    # 测试 compare_objects - 完全匹配
    result = compare_objects(
        extracted={"name": "John", "age": 30, "score": 85.5},
        standard={"name": "John", "age": 30, "score": 85.5},
        schema={"name": "str", "age": "int", "score": "float"}
    )
    assert result is not None
    assert result.total_records == 1
    assert result.total_correct == 1
    assert result.overall_accuracy == 1.0
    
    # 测试 evaluate_batch - 完全匹配
    result_batch = evaluate_batch(
        extracted_list=[
            {"name": "John", "age": 30, "score": 85.5},
            {"name": "Jane", "age": 25, "score": 92.0}
        ],
        standard_list=[
            {"name": "John", "age": 30, "score": 85.5},
            {"name": "Jane", "age": 25, "score": 92.0}
        ],
        schema={"name": "str", "age": "int", "score": "float"}
    )
    assert result_batch is not None
    assert result_batch.total_records == 2
    assert result_batch.total_correct == 2
    assert result_batch.overall_accuracy == 1.0
    
    # 测试部分匹配的情况
    partial_result = evaluate_batch(
        extracted_list=[
            {"name": "John", "age": 30, "score": 85.5},
            {"name": "Jane", "age": 25, "score": 90.0}  # 分数不匹配
        ],
        standard_list=[
            {"name": "John", "age": 30, "score": 85.5},
            {"name": "Jane", "age": 25, "score": 92.0}
        ],
        schema={"name": "str", "age": "int", "score": "float"}
    )
    assert partial_result is not None
    assert partial_result.total_records == 2
    assert partial_result.total_correct == 1
    assert partial_result.overall_accuracy == 0.5
    
    # 测试 compare_list_of_objects
    list_result = compare_list_of_objects(
        extracted=[{"name": "John"}, {"name": "Jane"}],
        standard=[{"name": "John"}, {"name": "Jane"}],
        schema={"name": "str"}
    )
    assert list_result is not None
    assert list_result.overall_accuracy == 1.0