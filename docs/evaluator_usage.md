# Evaluator 使用说明

评估模块，比较提取结果和标准答案，计算准确率。

## 核心功能

- 支持单对象（Object）和对象列表（List of Objects）评估
- 字段级别的准确率、召回率、精确率、F1 统计
- 标准集管理和数据集评估

---

## 快速开始

### 比较函数

```python
from evaluator import compare, compare_objects, compare_list_of_objects

# 通用比较（自动判断类型）
result = compare(extracted, standard, schema)

# 单对象比较
result = compare_objects(extracted, standard, schema)

# 对象列表比较
result = compare_list_of_objects(extracted, standard, schema)
```

---

## 评估器类

### ObjectEvaluator

用于单对象评估（schema.type = "object"）：

```python
from evaluator import ObjectEvaluator, Schema

schema = Schema(
    type="object",
    fields={
        "title": {"type": "string"},
        "date": {"type": "string"},
        "amount": {"type": "number"},
    }
)

evaluator = ObjectEvaluator(schema)
result = evaluator.evaluate(extracted, standard)

print(result.overall_accuracy)  # 总体准确率
print(result.field_stats)       # 字段统计
```

### ListOfObjectsEvaluator

用于对象列表评估（schema.type = "list_of_objects"）：

```python
from evaluator import ListOfObjectsEvaluator

evaluator = ListOfObjectsEvaluator(schema)
result = evaluator.evaluate(extracted_list, standard_list)
```

---

## 评估结果

### EvaluationResult

```python
from evaluator import EvaluationResult

result: EvaluationResult

# 核心属性
result.overall_accuracy     # 总体准确率
result.total_records        # 记录总数
result.total_correct        # 正确数
result.field_stats          # 字段统计 {field: FieldStat}
result.details              # 详细评估记录

# 生成报告
report = result.generate_report()
print(report)
```

### 字段统计

```python
for field_name, stat in result.field_stats.items():
    print(f"{field_name}:")
    print(f"  准确率: {stat.accuracy:.2%}")
    print(f"  召回率: {stat.recall:.2%}")
    print(f"  精确率: {stat.precision:.2%}")
    print(f"  F1: {stat.f1:.2%}")
```

---

## 详情类型

### RecordDetailType

```python
from evaluator import RecordDetailType

# 记录级别状态
RecordDetailType.CORRECT      # 完全正确
RecordDetailType.INCORRECT    # 有错误
RecordDetailType.EXCEPTION    # 执行异常
```

### FieldDetailType

```python
from evaluator import FieldDetailType

# 字段级别状态
FieldDetailType.CORRECT       # 正确
FieldDetailType.INCORRECT     # 错误
FieldDetailType.MISSING       # 缺失
FieldDetailType.EXTRA         # 多余
```

---

## 标准集管理

### StandardSet

```python
from evaluator import StandardSet, StandardSetLoader, DirectoryStandardSetLoader

# 从目录加载
loader = DirectoryStandardSetLoader("./data/train")
standard_set = loader.load()

# 访问标准数据
for standard in standard_set.standards:
    print(standard.id)
    print(standard.labels)  # 标准答案
```

### StandardSetManager

```python
from evaluator import StandardSetManager

manager = StandardSetManager(base_dir="./data")
train_set = manager.get_train_set()
test_set = manager.get_test_set()
```

### DatasetEvaluator

```python
from evaluator import DatasetEvaluator

evaluator = DatasetEvaluator(
    train_set=train_set,
    test_set=test_set,
    schema=schema
)

# 评估程序
result = await evaluator.evaluate(program, eval_type="train")
```

---

## 批量评估

```python
from evaluator import evaluate_batch, get_evaluator

# 获取合适的评估器
evaluator = get_evaluator(schema)

# 批量评估
results = evaluate_batch(
    evaluator=evaluator,
    extractions=[...],
    standards=[...],
)
```

---

## 评估部件

```python
from evaluator import get_evaluate_parts, EvaluateParts

# 获取评估所需的各个部件
parts: EvaluateParts = get_evaluate_parts(schema)

# 使用部件
evaluator = parts.evaluator
```

---

## Schema 定义

### Schema 类型

```python
from evaluator import Schema, SchemaField, FieldType

# 单对象 Schema
schema = Schema(
    type="object",
    fields={
        "title": SchemaField(type=FieldType.STRING),
        "date": SchemaField(type=FieldType.STRING),
        "amount": SchemaField(type=FieldType.NUMBER),
    }
)

# 对象列表 Schema
schema = Schema(
    type="list_of_objects",
    fields={
        "name": SchemaField(type=FieldType.STRING),
        "value": SchemaField(type=FieldType.NUMBER),
    }
)
```

### 字段类型

```python
from evaluator import FieldType

FieldType.STRING    # 字符串
FieldType.NUMBER    # 数字
FieldType.BOOLEAN   # 布尔
FieldType.DATE      # 日期
FieldType.LIST      # 列表
```

---

## CLI 命令

```bash
# 比较提取结果和标准答案
evaluator compare --extracted result.json --standard standard.json --schema schema.json
```

---

## 导出汇总

```python
from evaluator import (
    # 基础模型
    Document, Info, RuntimeInfo, ExceptionInfo,
    RecordDetailType, FieldDetailType, RecordDetailBase,
    EvaluationResult,
    
    # 评估模型
    EvaluationStandard, EvaluationExtraction,
    FullStandard, FullExtractedResult,
    
    # Schema
    Schema, FieldType, SchemaField,
    
    # 基础类
    Evaluator,
    
    # 评估器
    ObjectEvaluator, ObjectEvaluationResult,
    ListOfObjectsEvaluator, ListOfObjectsEvaluationResult,
    
    # 标准集管理
    StandardSet, StandardSetMetadata,
    StandardSetLoader, DirectoryStandardSetLoader,
    StandardSetManager, DatasetEvaluator,
    
    # API 接口
    compare, compare_objects, compare_list_of_objects,
    get_evaluator, evaluate_batch,
    get_evaluate_parts, EvaluateParts,
)
```
