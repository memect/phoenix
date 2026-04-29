# Evaluator API 使用指南

## 概述

`evaluator` 模块负责比较「提取结果」与「标准答案」，产出评估指标。

两类评估器对应两种数据结构：

| 评估器 | 数据结构 | 场景 |
|--------|----------|------|
| `ObjectEvaluator` | 每条记录是一个 dict | 单对象提取（如发票头信息） |
| `ListOfObjectsEvaluator` | 每条记录是一个 list[dict] | 列表提取（如发票明细行） |

---

## 1. 便捷接口 — `evaluator.api`

### 1.1 evaluate — 批量评估（推荐）

统一接口，自动检测 object / list_of_objects 类型。

```python
from evaluator.api import evaluate

# object 类型（自动检测：standard_list 元素是 dict）
result = evaluate(
    extracted_list=[
        {"title": "年报", "amount": 1000},
        {"title": "季报", "amount": 999},
    ],
    standard_list=[
        {"title": "年报", "amount": 1000},
        {"title": "季报", "amount": 500},
    ],
    schema={"title": "str", "amount": "int"},
    ids=["doc_001", "doc_002"],          # 可选
)
print(f"准确率: {result.overall_accuracy}")  # 0.5

# list_of_objects 类型（自动检测：standard_list 元素是 list）
result = evaluate(
    extracted_list=[
        [{"品名": "鼠标", "数量": 5}],
        [{"品名": "显示器", "数量": 1}],
    ],
    standard_list=[
        [{"品名": "鼠标", "数量": 5}, {"品名": "键盘", "数量": 3}],
        [{"品名": "显示器", "数量": 1}],
    ],
    schema={"品名": "str", "数量": "int"},
)
print(f"准确率: {result.overall_accuracy}")  # 0.5
```

**类型检测逻辑**：看 `standard_list[0]` 是 `list` 还是 `dict`，也可用 `eval_type` 参数强制指定。

### 1.2 compare — 单条比较

```python
from evaluator.api import compare

# object 类型（自动检测）
result = compare(
    extracted={"title": "年报", "amount": 999},
    standard={"title": "年报", "amount": 1000},
    schema={"title": "str", "amount": "int"},
)

# list_of_objects 类型（自动检测）
result = compare(
    extracted=[{"品名": "鼠标", "数量": 5}],
    standard=[{"品名": "鼠标", "数量": 5}, {"品名": "键盘", "数量": 3}],
    schema={"品名": "str", "数量": "int"},
)
```

### 1.3 re-export

`evaluator.api` 导出了所有常用类型，可以直接导入：

```python
from evaluator.api import (
    # 便捷函数
    evaluate, compare, compare_objects, compare_list_of_objects,
    evaluate_batch, get_evaluator, get_evaluate_parts,
    # 核心类
    ObjectEvaluator, ListOfObjectsEvaluator,
    FullStandard, FullExtractedResult,
    Schema, EvaluationResult,
)
```

---

## 2. 核心数据模型

直接使用评估器时需要组装以下数据：

### FullStandard — 标准答案

```python
from evaluator.core.evaluation_models import FullStandard

# 最简创建：只需 id + labels
std = FullStandard(id="doc_001", labels={"title": "年报", "amount": 1000})
```

### FullExtractedResult — 提取结果

```python
from evaluator.core.evaluation_models import FullExtractedResult

# 成功结果
ext = FullExtractedResult.success_result(data={"title": "年报", "amount": 1000})
ext.id = "doc_001"  # 设置对应的文档 ID

# 失败结果（程序执行出错时）
ext = FullExtractedResult.error_result(exception=e, stdout="", stderr=str(e))
ext.id = "doc_001"
```

### Schema — 字段定义

```python
from evaluator.core.schema import Schema

# 字典格式（推荐）
schema = Schema.from_dict({"title": "str", "amount": "int"})

# 支持的类型：str, int, float, bool, list, array
```

---

## 3. ObjectEvaluator — 单对象评估

每条记录是一个 dict，逐字段比较。

### 3.1 组装数据 + 评估

```python
from evaluator.evaluators.object import ObjectEvaluator
from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
from evaluator.core.schema import Schema

# 1. 创建评估器
schema = Schema.from_dict({"title": "str", "amount": "int", "date": "str"})
evaluator = ObjectEvaluator(schema)

# 2. 组装标准答案（N 条记录）
standards = [
    FullStandard(id="doc_001", labels={"title": "年报", "amount": 1000, "date": "2024-01-01"}),
    FullStandard(id="doc_002", labels={"title": "季报", "amount": 500, "date": "2024-04-01"}),
    FullStandard(id="doc_003", labels={"title": "月报", "amount": 200, "date": "2024-07-01"}),
]

# 3. 组装提取结果（与标准答案一一对应）
def make_ext(id, data):
    ext = FullExtractedResult.success_result(data=data)
    ext.id = id
    return ext

extractions = [
    make_ext("doc_001", {"title": "年报", "amount": 1000, "date": "2024-01-01"}),  # 全对
    make_ext("doc_002", {"title": "季报", "amount": 999}),                          # amount 错，date 缺失
    make_ext("doc_003", {"title": "月报X", "amount": 200, "date": "2024-07-01"}),   # title 错
]

# 4. 评估
result = evaluator.evaluate(extractions, standards)
```

### 3.2 读取结果

```python
# 文档级
print(f"整体准确率: {result.overall_accuracy:.2%}")       # 33.33%（只有 doc_001 全对）
print(f"正确/总数: {result.total_correct}/{result.total_records}")  # 1/3

# 字段级统计
for field, stat in result.field_stats.items():
    print(f"{field}: accuracy={stat.accuracy:.2%} "
          f"correct={stat.correct} incorrect={stat.incorrect} missing={stat.missing}")
# title:  accuracy=66.67% correct=2 incorrect=1 missing=0
# amount: accuracy=66.67% correct=2 incorrect=1 missing=0
# date:   accuracy=66.67% correct=2 incorrect=0 missing=1

# 错误详情
for detail in result.get_incorrect_details():
    print(f"\n文档 {detail.standared_info.id}:")
    for fd in detail.related_field_details:
        print(f"  {fd.name}: {fd.type.value} — 提取={fd.extracted_value} 标准={fd.standard_value}")

# 文本报告
print(result.generate_report())
```

### 3.3 单条评估

```python
detail = evaluator.evaluate_one(extractions[0], standards[0])
print(f"{detail.standared_info.id}: {detail.type.value}")
for fd in detail.related_field_details:
    print(f"  {fd.name}: {fd.type.value}")
```

---

## 4. ListOfObjectsEvaluator — 列表对象评估

每条记录是一个 list[dict]，先用 Hungarian 算法匹配对象，再逐字段比较。

### 4.1 组装数据 + 评估

```python
from evaluator.evaluators.list_of_objects import ListOfObjectsEvaluator
from evaluator.core.evaluation_models import FullStandard, FullExtractedResult
from evaluator.core.schema import Schema

# 1. 创建评估器
schema = Schema.from_dict({"品名": "str", "数量": "int", "单价": "int"})
evaluator = ListOfObjectsEvaluator(schema)

# 2. 标准答案 — labels 是 list[dict]
standards = [
    FullStandard(id="invoice_001", labels=[
        {"品名": "笔记本电脑", "数量": 2, "单价": 5000},
        {"品名": "鼠标", "数量": 5, "单价": 50},
        {"品名": "键盘", "数量": 3, "单价": 200},
    ]),
    FullStandard(id="invoice_002", labels=[
        {"品名": "显示器", "数量": 1, "单价": 3000},
    ]),
]

# 3. 提取结果
def make_ext(id, data):
    ext = FullExtractedResult.success_result(data=data)
    ext.id = id
    return ext

extractions = [
    make_ext("invoice_001", [
        {"品名": "笔记本电脑", "数量": 2, "单价": 5000},  # 匹配
        {"品名": "鼠标", "数量": 5, "单价": 50},           # 匹配
        # 漏了「键盘」
    ]),
    make_ext("invoice_002", [
        {"品名": "显示器", "数量": 1, "单价": 3000},       # 匹配
    ]),
]

# 4. 评估
result = evaluator.evaluate(extractions, standards)
```

### 4.2 读取结果

```python
# 文档级
print(f"整体准确率: {result.overall_accuracy:.2%}")       # 50%（invoice_002 全对）
print(f"正确/总数: {result.total_correct}/{result.total_records}")  # 1/2

# 字段级统计（跨文档平均）
for field, stat in result.field_stats.items():
    print(f"{field}: accuracy={stat.accuracy:.2%} recall={stat.recall:.2%}")

# 每条记录的匹配详情
for detail in result.details:
    print(f"\n文档 {detail.standared_info.id}: {detail.type.value}")
    print(f"  匹配: {len(detail.matched)} 条")
    print(f"  缺失: {len(detail.missing)} 条 (标准有、提取无)")
    print(f"  多余: {len(detail.extra)} 条 (提取有、标准无)")

    for m in detail.matched:
        print(f"  匹配对象: sim={m.similarity_score:.2f} "
              f"correct={m.correct_fields} incorrect={m.incorrect_fields}")

    for obj in detail.missing:
        print(f"  缺失对象: {obj}")

# 文本报告
print(result.generate_report())
```

### 4.3 匹配算法

```
标准:  [A, B, C]
提取:  [A', C', D]

1. 计算相似度矩阵（字段匹配比例）
        A     B     C
   A'  1.0   0.0   0.3
   C'  0.3   0.0   1.0
   D   0.0   0.5   0.0

2. Hungarian 算法找最优匹配 → A↔A', C↔C'

3. 结果:
   matched = [A↔A'(sim=1.0), C↔C'(sim=1.0)]
   missing = [B]        ← 标准有、没匹配上
   extra   = [D]        ← 提取有、没匹配上

4. 判定: missing 或 extra 不为空 → INCORRECT
```

记录判定为 CORRECT 的条件：
- `missing = []`（无缺失）
- `extra = []`（无多余）
- 所有匹配对象的 `similarity_score == 1.0`（所有字段都正确）

---

## 5. 评估结果类型

### ObjectEvaluationResult

```python
result.overall_accuracy               # float: 全部字段都正确的记录占比
result.total_correct                   # int: 完全正确的记录数
result.total_records                   # int: 总记录数
result.field_stats                     # Dict[str, FieldStats]: 字段级统计
result.details                         # List[RecordDetail]: 每条记录的详情
result.get_incorrect_details()         # 只看错误的记录
result.get_error_details()             # 只看执行失败的记录
result.generate_report()               # 文本报告

# RecordDetail (object)
detail.type                            # RecordDetailType: CORRECT / INCORRECT
detail.standared_info                  # FullStandard
detail.extracted_info                  # FullExtractedResult
detail.related_field_details           # List[FieldDetail]: 每个字段的对比
detail.extra_info                      # Dict: 额外信息

# FieldDetail
fd.name                                # str: 字段名
fd.type                                # FieldDetailType: CORRECT / INCORRECT / MISSING / EXTRA
fd.extracted_value                     # Any
fd.standard_value                      # Any
```

### ListOfObjectsEvaluationResult

```python
result.overall_accuracy               # float
result.total_correct                   # int
result.total_records                   # int
result.field_stats                     # Dict[str, FieldStats]: 跨文档平均
result.details                         # List[RecordDetail]

# RecordDetail (list_of_objects)
detail.type                            # RecordDetailType: CORRECT / INCORRECT
detail.matched                         # List[MatchedObjectDetail]: 匹配上的对象对
detail.missing                         # List[Dict]: 标准有、提取无
detail.extra                           # List[Dict]: 提取有、标准无
detail.standared_info                  # FullStandard
detail.extracted_info                  # FullExtractedResult

# MatchedObjectDetail
m.standard_value                       # Dict: 标准对象
m.extracted_value                      # Dict: 提取对象
m.similarity_score                     # float: 相似度 (0~1)
m.correct_fields                       # List[str]: 正确的字段
m.incorrect_fields                     # List[str]: 错误的字段
m.missing_fields                       # List[str]: 缺失的字段
m.extra_fields                         # List[str]: 多余的字段
m.std_list_idx                         # int: 标准列表中的索引
m.ext_list_idx                         # int: 提取列表中的索引
```

### FieldStats

```python
stat.accuracy      # correct / total
stat.precision     # correct / (correct + incorrect + extra)
stat.recall        # correct / (correct + incorrect + missing)
stat.f1            # 2 * precision * recall / (precision + recall)
stat.correct       # int
stat.incorrect     # int
stat.missing       # int
stat.extra         # int
```
