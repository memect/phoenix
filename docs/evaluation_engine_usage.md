# Evaluation Engine Python API 使用说明

Status: active
Audience: maintainers
Last verified: 2026-04-27
Source of truth:
- `src/evaluation_engine/engine.py`
- `src/code_executor/executor.py`
- `pyproject.toml`

评估引擎模块，组合 `code_executor` 和 `evaluator`，提供数据集级别的评估能力。

命令行提取/评估入口现在统一走 `xdev run` / `xdev eval`。`evaluation-engine`
不再作为安装后的 console script 导出。

## 核心功能

- 在数据集上执行程序并评估准确率
- 支持本地数据或从 URL 下载
- 训练集/测试集分离评估
- 同步和异步 API

---

## 创建评估引擎

### 从本地数据

```python
from evaluation_engine import EvaluationEngine

# 从本地数据目录创建
engine = EvaluationEngine.from_data_path(
    data_path="./resources/dataset",
    keys=["title", "date"]  # 可选：指定评估的字段
)

# 访问属性
print(engine.schema)          # Schema 定义
print(engine.train_dataset)   # 训练集
print(engine.test_dataset)    # 测试集
```

### 从 URL 下载

```python
engine = EvaluationEngine.from_url(
    url_base="http://localhost:8008",
    dataset_id="f1dd588d-4b14-4ecd-8376-0d710930df7f",
    schema=schema_dict,
    keys=["title", "date"]
)
```

---

## 评估程序

### 异步 API

```python
from evaluation_engine import evaluate_program, evaluate_program_on_docs

program = """
from code_executor.document.models import Document

def extract(document: Document):
    texts = document.get_all_texts(max_items=1)
    return {"title": texts[0] if texts else ""}
"""

# 评估程序
result = await engine.evaluate_program(
    program=program,
    eval_type="train"  # 或 "test"
)

# 在指定文档上评估
details = await engine.evaluate_program_on_std_ids(
    program=program,
    std_ids=["doc1", "doc2"]
)
```

### 同步 API

```python
from evaluation_engine import evaluate_program_sync, evaluate_program_on_docs_sync

program = """
from code_executor.document.models import Document

def extract(document: Document):
    return {"texts": document.get_all_texts(max_items=3)}
"""

# 同步评估（内部会处理事件循环）
result = evaluate_program_sync(
    data_path="./resources/dataset",
    program=program,
    eval_type="train"
)

# 在指定文档上同步评估
details = evaluate_program_on_docs_sync(
    data_path="./resources/dataset",
    program=program,
    doc_ids=["doc1", "doc2"]
)
```

---

## 便捷函数

### 下载数据集

```python
from evaluation_engine import download_dataset

# 下载数据集到本地
data_path = download_dataset(
    set_id="f1dd588d-4b14-4ecd-8376-0d710930df7f",
    base_url="http://localhost:8008",
    download_dir=".cache",
    use_cache=True  # 使用缓存
)
```

### 读取程序

```python
from evaluation_engine import read_program

# 从文件或 ResultJson 读取程序
program = read_program("./program.py")
program = read_program("./result.json")  # 从 ResultJson 读取
```

---

## 评估结果处理

### 提取评估数据

```python
from evaluation_engine import extract_evaluation_data, EvaluationResult

result: EvaluationResult = await engine.evaluate_program(program, "train")

# 提取结构化数据
data = extract_evaluation_data(result)
print(data["field_count"])        # 字段数
print(data["field_average"])      # 字段平均准确率
print(data["document_count"])     # 文档数
print(data["overall_accuracy"])   # 总体准确率
print(data["field_stats"])        # 字段统计
```

### 格式化详情

```python
from evaluation_engine import format_record_detail

# 格式化单条记录详情
detail_str = format_record_detail(record_detail)
```

---

## 数据模型

### Info

```python
from evaluation_engine import Info

# 文档信息
info = Info(
    id="doc1",
    document=document_obj
)
```

### Standard

```python
from evaluation_engine import Standard

# 标准数据
standard = Standard(
    id="doc1",
    labels={"title": "标题", "date": "2024-01-01"},
    info=info
)
```

### ExtractedResult

```python
from evaluation_engine import ExtractedResult

# 提取结果
result = ExtractedResult(
    id="doc1",
    labels={"title": "提取的标题"},
    info=info
)
```

---

## CLI 命令

`evaluation-engine` 模块保留 Python API，但不再作为 console script 暴露。
需要命令行运行时请使用：

```bash
xdev run <doc_id> --workspace ./workspace
xdev eval --workspace ./workspace
```

---

## 与 evaluator 的关系

`evaluation_engine` 是对 `code_executor` 和 `evaluator` 的组合：

```
EvaluationEngine
    ├── code_executor  # 执行程序
    │       └── execute(program, docjson)
    └── evaluator      # 评估结果
            └── compare(extracted, standard, schema)
```

工作流程：
1. 加载数据集（标准答案 + 文档内容）
2. 使用 `code_executor` 执行程序，得到提取结果
3. 使用 `evaluator` 比较提取结果和标准答案
4. 汇总统计，生成报告

---

## 导出汇总

```python
from evaluation_engine import (
    # 核心类
    EvaluationEngine,
    
    # 数据模型
    Info, Standard, ExtractedResult,
    RecordDetailType, EvaluationResult, RecordDetailBase,
    
    # 异步 API
    evaluate_program, evaluate_program_on_docs,
    
    # 同步 API
    evaluate_program_sync, evaluate_program_on_docs_sync,
    
    # 工具函数
    download_dataset, read_program,
    extract_evaluation_data, format_record_detail,
)
```
