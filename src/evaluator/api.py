"""
Evaluator API

评估模块代码接口

使用示例:
    from evaluator.api import evaluate

    # 批量评估（自动检测 object / list_of_objects）
    result = evaluate(
        extracted_list=[{"name": "张三"}, {"name": "李四"}],
        standard_list=[{"name": "张三"}, {"name": "王五"}],
        schema={"name": "str"},
    )
    print(f"准确率: {result.overall_accuracy}")

    # 单条比较
    from evaluator.api import compare
    result = compare(
        extracted={"name": "张三", "age": 30},
        standard={"name": "张三", "age": 30},
        schema={"name": "str", "age": "int"}
    )
"""

from typing import Dict, Any, Union, Literal, Optional, List, NamedTuple

from .core.schema import Schema
from .core.models import EvaluationResult
from .core.evaluation_models import FullStandard, FullExtractedResult
from .core.base import Evaluator
from .evaluators.object import ObjectEvaluator
from .evaluators.list_of_objects import ListOfObjectsEvaluator


class EvaluateParts(NamedTuple):
    """评估组件包"""
    evaluator: Evaluator


def _make_full_standard(record_id: str, labels: Any) -> FullStandard:
    """创建 FullStandard 实例"""
    return FullStandard(id=record_id, labels=labels)


def _make_full_extracted(record_id: str, labels: Any) -> FullExtractedResult:
    """创建 FullExtractedResult 实例"""
    result = FullExtractedResult.success_result(data=labels)
    result.id = record_id
    return result


def evaluate(
    extracted_list: List[Union[Dict[str, Any], List[Dict[str, Any]]]],
    standard_list: List[Union[Dict[str, Any], List[Dict[str, Any]]]],
    schema: Union[Schema, Dict[str, str]],
    ids: Optional[List[str]] = None,
    eval_type: Optional[Literal['object', 'list_of_objects']] = None,
) -> EvaluationResult:
    """
    批量评估提取结果

    自动检测评估类型（object 或 list_of_objects），或使用指定的类型。
    支持同时评估多条记录，返回包含整体准确率和字段级统计的结果。

    Args:
        extracted_list: 提取结果列表
        standard_list: 标准答案列表（数量必须与 extracted_list 一致）
        schema: 数据模式，可以是 Schema 对象或字典
        ids: 可选的 ID 列表，用于标识每个记录
        eval_type: 评估类型，不指定则自动检测

    Returns:
        EvaluationResult: 评估结果对象

    Example:
        >>> result = evaluate(
        ...     extracted_list=[{"name": "张三"}, {"name": "李四"}],
        ...     standard_list=[{"name": "张三"}, {"name": "王五"}],
        ...     schema={"name": "str"},
        ... )
        >>> print(result.overall_accuracy)
        0.5
    """
    if len(extracted_list) != len(standard_list):
        raise ValueError(
            f"提取结果数量 ({len(extracted_list)}) 与标准答案数量 ({len(standard_list)}) 不匹配"
        )

    if not standard_list:
        raise ValueError("标准答案列表不能为空")

    # 自动检测评估类型
    if eval_type is None:
        if isinstance(standard_list[0], list):
            eval_type = 'list_of_objects'
        else:
            eval_type = 'object'

    # 转换 schema
    if isinstance(schema, dict):
        schema = Schema.from_dict(schema)

    # 生成 ID
    if ids is None:
        ids = [f"record_{i}" for i in range(len(standard_list))]

    if len(ids) != len(standard_list):
        raise ValueError(
            f"ID 数量 ({len(ids)}) 与记录数量 ({len(standard_list)}) 不匹配"
        )

    # 获取评估组件
    parts = get_evaluate_parts(eval_type, schema)
    evaluator = parts.evaluator

    # 创建评估数据
    full_standards = [
        _make_full_standard(record_id, standard)
        for record_id, standard in zip(ids, standard_list)
    ]
    full_extractions = [
        _make_full_extracted(record_id, extracted)
        for record_id, extracted in zip(ids, extracted_list)
    ]

    return evaluator.evaluate(full_extractions, full_standards)


def get_evaluate_parts(
    type: Literal['object', 'list_of_objects'],
    schema: Union[Schema, Dict[str, str]]
) -> EvaluateParts:
    """
    获取评估组件

    Args:
        type: 评估类型
        schema: 数据模式，可以是Schema对象或字典

    Returns:
        评估组件包
    """
    if isinstance(schema, dict):
        schema = Schema.from_dict(schema)

    if type == 'object':
        return EvaluateParts(evaluator=ObjectEvaluator(schema))
    elif type == 'list_of_objects':
        return EvaluateParts(evaluator=ListOfObjectsEvaluator(schema))
    else:
        raise ValueError(f"Invalid type: {type}")


def compare(
    extracted: Union[Dict[str, Any], List[Dict[str, Any]]],
    standard: Union[Dict[str, Any], List[Dict[str, Any]]],
    schema: Union[Schema, Dict[str, str]],
    eval_type: Optional[Literal['object', 'list_of_objects']] = None,
    record_id: str = "api_compare",
) -> EvaluationResult:
    """
    比较提取结果和标准答案

    自动检测评估类型（object 或 list_of_objects），或使用指定的类型。

    Args:
        extracted: 提取结果，可以是单个对象或对象列表
        standard: 标准答案，可以是单个对象或对象列表
        schema: 数据模式，可以是 Schema 对象或字典
        eval_type: 评估类型，不指定则自动检测
        record_id: 记录 ID，用于标识评估记录

    Returns:
        EvaluationResult: 评估结果对象

    Example:
        >>> result = compare(
        ...     extracted={"name": "张三", "age": 30},
        ...     standard={"name": "张三", "age": 30},
        ...     schema={"name": "str", "age": "int"}
        ... )
        >>> print(result.overall_accuracy)
        1.0
    """
    # 自动检测评估类型
    if eval_type is None:
        if isinstance(standard, list) or isinstance(extracted, list):
            eval_type = 'list_of_objects'
        else:
            eval_type = 'object'

    # 转换 schema
    if isinstance(schema, dict):
        schema = Schema.from_dict(schema)

    # 获取评估组件
    parts = get_evaluate_parts(eval_type, schema)
    evaluator = parts.evaluator

    # 创建评估数据 - 使用 FullStandard 和 FullExtractedResult（与内部调用链一致）
    full_standard = _make_full_standard(record_id, standard)
    full_extraction = _make_full_extracted(record_id, extracted)

    return evaluator.evaluate([full_extraction], [full_standard])


def compare_objects(
    extracted: Dict[str, Any],
    standard: Dict[str, Any],
    schema: Union[Schema, Dict[str, str]],
    record_id: str = "api_compare",
) -> EvaluationResult:
    """
    比较单个对象的提取结果和标准答案

    Args:
        extracted: 提取结果对象
        standard: 标准答案对象
        schema: 数据模式
        record_id: 记录 ID

    Returns:
        EvaluationResult: 评估结果对象

    Example:
        >>> result = compare_objects(
        ...     extracted={"name": "张三", "age": 30},
        ...     standard={"name": "张三", "age": 30},
        ...     schema={"name": "str", "age": "int"}
        ... )
        >>> print(result.overall_accuracy)
        1.0
    """
    return compare(extracted, standard, schema, eval_type='object', record_id=record_id)


def compare_list_of_objects(
    extracted: List[Dict[str, Any]],
    standard: List[Dict[str, Any]],
    schema: Union[Schema, Dict[str, str]],
) -> EvaluationResult:
    """
    比较对象列表的提取结果和标准答案

    Args:
        extracted: 提取结果对象列表
        standard: 标准答案对象列表
        schema: 数据模式

    Returns:
        EvaluationResult: 评估结果对象

    Example:
        >>> result = compare_list_of_objects(
        ...     extracted=[{"name": "张三"}, {"name": "李四"}],
        ...     standard=[{"name": "张三"}, {"name": "李四"}],
        ...     schema={"name": "str"}
        ... )
        >>> print(result.overall_accuracy)
        1.0
    """
    return compare(extracted, standard, schema, eval_type='list_of_objects')


def get_evaluator(
    eval_type: Literal['object', 'list_of_objects'],
    schema: Union[Schema, Dict[str, str]],
) -> EvaluateParts:
    """
    获取评估器组件

    返回评估器，用于更灵活的评估场景。

    Args:
        eval_type: 评估类型
        schema: 数据模式

    Returns:
        EvaluateParts: 包含 evaluator 的命名元组

    Example:
        >>> parts = get_evaluator('object', {"name": "str"})
        >>> evaluator = parts.evaluator
        >>> from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
        >>> std = FullStandard(id="id1", labels={"name": "张三"})
        >>> ext = FullExtractedResult.success_result(data={"name": "张三"})
        >>> ext.id = "id1"
        >>> result = evaluator.evaluate([ext], [std])
    """
    if isinstance(schema, dict):
        schema = Schema.from_dict(schema)

    return get_evaluate_parts(eval_type, schema)


def evaluate_batch(
    extracted_list: List[Dict[str, Any]],
    standard_list: List[Dict[str, Any]],
    schema: Union[Schema, Dict[str, str]],
    ids: Optional[List[str]] = None,
) -> EvaluationResult:
    """
    批量评估多个对象

    对多个提取结果和标准答案进行批量评估。

    Args:
        extracted_list: 提取结果列表
        standard_list: 标准答案列表
        schema: 数据模式
        ids: 可选的 ID 列表，用于标识每个记录

    Returns:
        EvaluationResult: 评估结果对象

    Raises:
        ValueError: 如果提取结果和标准答案数量不匹配

    Example:
        >>> result = evaluate_batch(
        ...     extracted_list=[{"name": "张三"}, {"name": "李四"}],
        ...     standard_list=[{"name": "张三"}, {"name": "王五"}],
        ...     schema={"name": "str"}
        ... )
        >>> print(result.overall_accuracy)
        0.5
    """
    if len(extracted_list) != len(standard_list):
        raise ValueError(
            f"提取结果数量 ({len(extracted_list)}) 与标准答案数量 ({len(standard_list)}) 不匹配"
        )

    if ids is None:
        ids = [f"record_{i}" for i in range(len(extracted_list))]

    if len(ids) != len(extracted_list):
        raise ValueError(
            f"ID 数量 ({len(ids)}) 与记录数量 ({len(extracted_list)}) 不匹配"
        )

    # 转换 schema
    if isinstance(schema, dict):
        schema = Schema.from_dict(schema)

    # 获取评估组件
    parts = get_evaluate_parts('object', schema)
    evaluator = parts.evaluator

    # 创建评估数据列表 - 使用 FullStandard 和 FullExtractedResult（与内部调用链一致）
    full_standards = [
        _make_full_standard(record_id, standard)
        for record_id, standard in zip(ids, standard_list)
    ]
    full_extractions = [
        _make_full_extracted(record_id, extracted)
        for record_id, extracted in zip(ids, extracted_list)
    ]

    return evaluator.evaluate(full_extractions, full_standards)


__all__ = [
    # 便捷函数
    "evaluate",
    "compare",
    "compare_objects",
    "compare_list_of_objects",
    "evaluate_batch",
    "get_evaluator",
    "get_evaluate_parts",
    "EvaluateParts",
    # 核心类 re-export
    "ObjectEvaluator",
    "ListOfObjectsEvaluator",
    "FullStandard",
    "FullExtractedResult",
    "Schema",
    "EvaluationResult",
]
