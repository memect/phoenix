# Extract Dev 开发工具

用于提取程序开发和调试的 CLI 工具，专为 AI Agent 设计，提供最简化的命令接口。

## 用法

### 环境变量配置

```bash
export EXTRACT_SET_ID="标准集ID"
export EXTRACT_BASE_URL="http://localhost:8008"
export EXTRACT_PROGRAM="./program.py"
```

### 命令行覆盖

命令行参数优先级高于环境变量：

```bash
extract-dev run doc1 --program ./other.py
extract-dev train --set-id "另一个标准集"
```

### 运行时输出

每次执行命令会先打印当前配置：

```
[extract-dev] set_id: xxx-xxx-xxx
[extract-dev] program: ./program.py
[extract-dev] base_url: http://localhost:8008
---
<命令输出>
```

---

## 命令列表

### `doc` - 查看文档原文

查看文档的 Markdown 原文。

```bash
extract-dev doc <doc_id>
extract-dev doc <doc_id> --dataset test
```

**可选参数**：
- `--dataset` - 数据集：train（默认）或 test

**输出格式**: Markdown

---

### `standard` - 查看标准答案

查看文档的标准答案。覆盖层数据优先。

```bash
extract-dev standard <doc_id>
extract-dev standard <doc_id> --dataset test
```

**可选参数**：
- `--dataset` - 数据集：train（默认）或 test

**输出格式**: JSON

---

### `run` - 评估单个文档

在单个文档上运行程序并评估。覆盖层存在时使用覆盖层 schema。

```bash
extract-dev run <doc_id>
extract-dev run <doc_id> --program ./other.py
extract-dev run <doc_id> --dataset test
```

**可选参数**：
- `--dataset` - 数据集：train（默认）或 test

**输出格式**: Markdown 评估报告

包含：
- 文档原文
- 标准答案
- 提取结果
- 字段对比详情

---

### `train` - 训练集整体评估

在整个训练集上评估程序，输出整体评估报告。

```bash
extract-dev train
extract-dev train --program ./other.py
extract-dev train --key field1 --key field2  # 指定字段
```

**可选参数**：
- `--key` - 指定评估的字段（可多个）
- `--standard-entry-ids` - 指定标准集条目 ID（逗号分隔），只评估这些文档
- `--concurrent` - 程序执行并发数（覆盖环境变量配置）
- `--show-correct-ids` - 显示正确文档 ID
- `--show-incorrect-ids/--no-show-incorrect-ids` - 显示错误文档 ID（默认启用）
- `--show-details` - 显示详细对比

**输出格式**: Markdown 评估报告

包含：
- 总体准确率
- 字段统计（准确率、召回率、精确率、F1）
- 正确/错误文档 ID 列表
- 详细对比（如果 --show-details）

---

### `test` - 测试集整体评估

在测试集上评估程序。

```bash
extract-dev test
extract-dev test --program ./other.py
extract-dev test --key field1 --key field2  # 指定字段
```

**可选参数**：
- `--key` - 指定评估的字段（可多个）
- `--standard-entry-ids` - 指定标准集条目 ID（逗号分隔），只评估这些文档
- `--concurrent` - 程序执行并发数（覆盖环境变量配置）
- `--show-correct-ids` - 显示正确文档 ID
- `--show-incorrect-ids/--no-show-incorrect-ids` - 显示错误文档 ID（默认启用）
- `--show-details` - 显示详细对比

**输出格式**: Markdown 评估报告（与 train 相同）

---

### `list` - 列出文档ID

列出指定数据集中所有文档的 ID。

```bash
extract-dev list
extract-dev list --dataset test
```

**可选参数**：
- `--dataset` - 数据集：train（默认）或 test

**输出格式**: 文本列表

---

### `schema` - 查看 Schema 定义

查看 Schema 定义。覆盖层数据优先。

```bash
extract-dev schema
```

**输出格式**: JSON

---

### `context` - 查看代码依赖模块文档

查看编写提取程序所需的上下文信息。

```bash
extract-dev context
```

**输出格式**: Markdown

包含：
- 代码入口签名
- `code_executor/structure.py` 内容（Table 等数据结构）
- 工具指南（如果配置了工具）

---

### `pseudo-init` - 初始化本地标注工作区

下载标准集到缓存，创建 `.extract-dev/` 目录。

```bash
extract-dev pseudo-init
extract-dev pseudo-init --set-id "标准集ID"
```

---

### `set-schema` - 设置本地标注 schema

写入 `.extract-dev/schema.json`。

```bash
extract-dev set-schema '{"type": "object", "data": {"字段名": "str"}}'
extract-dev set-schema '{"type": "list_of_objects", "data": {"名称": "str", "金额": "float"}}'
```

---

### `label` - 标注单个文档

追加/更新 `.extract-dev/labels.json` 中的标注。

```bash
extract-dev label <doc_id> '{"字段1": "值1"}'
extract-dev label <doc_id> '{"字段1": "值1"}' --dataset test
```

**可选参数**：
- `--dataset` - 数据集：train（默认）或 test

---

### `labels` - 查看本地标注

```bash
extract-dev labels                # 查看全部
extract-dev labels --dataset train  # 只看训练集
extract-dev labels --dataset test   # 只看测试集
```

**可选参数**：
- `--dataset` - 过滤数据集：train 或 test，不指定则显示全部

**输出格式**: JSON

---

### `reset-labels` - 清空本地标注

```bash
extract-dev reset-labels              # 清空全部
extract-dev reset-labels --dataset train  # 只清空训练集
```

**可选参数**：
- `--dataset` - 指定清空 train 或 test，不指定则清空全部

---

## 命令参数汇总

| 命令 | 位置参数 | 可选参数 |
|------|----------|----------|
| `doc <id>` | doc_id | `--set-id`, `--dataset` |
| `standard <id>` | doc_id | `--set-id`, `--dataset` |
| `run <id>` | doc_id | `--program`, `--set-id`, `--dataset` |
| `train` | 无 | `--program`, `--set-id`, `--key`, `--standard-entry-ids`, `--concurrent`, `--show-correct-ids`, `--show-incorrect-ids`, `--show-details` |
| `test` | 无 | `--program`, `--set-id`, `--key`, `--standard-entry-ids`, `--concurrent`, `--show-correct-ids`, `--show-incorrect-ids`, `--show-details` |
| `list` | 无 | `--set-id`, `--dataset` |
| `schema` | 无 | `--set-id` |
| `context` | 无 | 无 |
| `pseudo-init` | 无 | `--set-id` |
| `set-schema` | schema_json | 无 |
| `label` | doc_id, labels_json | `--dataset` |
| `labels` | 无 | `--dataset` |
| `reset-labels` | 无 | `--dataset` |

---

## 输出格式汇总

| 命令 | 输出格式 | 说明 |
|------|----------|------|
| `doc` | Markdown | 文档原文 |
| `standard` | JSON | 标准答案（覆盖层优先） |
| `run` | Markdown | 单文档评估报告 |
| `train` | Markdown | 训练集评估报告 |
| `test` | Markdown | 测试集评估报告 |
| `list` | 文本 | 文档 ID 列表 |
| `schema` | JSON | Schema 定义（覆盖层优先） |
| `context` | Markdown | 代码依赖上下文 |
| `pseudo-init` | 文本 | 初始化确认 |
| `set-schema` | 文本 | 保存确认 |
| `label` | 文本 | 标注确认 |
| `labels` | JSON | 本地标注数据 |
| `reset-labels` | 文本 | 清空确认 |

---

## 典型工作流

### Agent 迭代开发流程

```bash
# 1. 了解任务
extract-dev schema              # 查看需要提取的字段
extract-dev context             # 查看代码编写上下文

# 2. 了解数据
extract-dev list                # 列出训练集文档
extract-dev doc doc1            # 查看某篇文档
extract-dev standard doc1       # 查看标准答案

# 3. 开发迭代
extract-dev train               # 训练集整体评估
extract-dev run doc1            # 针对错误文档详细分析
# ... 修改 program.py ...
extract-dev train               # 重新评估

# 4. 最终验证
extract-dev test                # 测试集评估（只看指标）
```

### 无标注模式工作流

```bash
# 1. 初始化覆盖层
extract-dev pseudo-init --set-id "标准集ID"

# 2. 阅读文档，定义 schema
extract-dev list                # 列出文档
extract-dev doc doc1            # 查看文档内容
extract-dev set-schema '{"type": "object", "data": {"字段1": "str", "字段2": "float"}}'

# 3. 标注文档
extract-dev label doc1 '{"字段1": "值1", "字段2": 1.0}'
extract-dev label doc2 '{"字段1": "值2", "字段2": 2.0}' --dataset test
extract-dev labels              # 查看已标注数据

# 4. 开发迭代（覆盖层自动生效）
extract-dev schema              # 查看覆盖层 schema
extract-dev train               # 只评估已标注文档
extract-dev run doc1            # 单文档评估

# 5. 测试集验证
extract-dev list --dataset test
extract-dev test
```

---

## Code API

除了 CLI，`extract_dev` 还提供了面向对象的异步 Python API。

### 基本使用

```python
import asyncio
from extract_dev.api import ExtractDevEvaluator, EvaluationResultWithMetadata

async def main():
    # 创建评估器（远程数据集）
    evaluator = await ExtractDevEvaluator.create(
        set_id="xxx-xxx-xxx",
        cache_dir=".cache",  # 可选，指定缓存目录
    )
    
    # 评估训练集 - 返回带元数据的结果
    program = open("program.py").read()
    result = await evaluator.evaluate_train(program)
    
    # 查看结果（通过 .result 访问原始结果）
    print(f"准确率: {result.result.overall_accuracy:.2%}")
    print(f"eval_type: {result.eval_type}")  # 'train'

asyncio.run(main())
```

### 创建评估器

```python
# 远程数据集（异步）
evaluator = await ExtractDevEvaluator.create(
    set_id="xxx-xxx-xxx",
    base_url="http://example.com",  # 可选
    cache_dir=".cache",             # 可选
    concurrent=4,                   # 可选
)

# 本地数据集（同步）
evaluator = ExtractDevEvaluator.from_data_path(
    "/path/to/dataset",
    concurrent=4,  # 可选
)
```

### 评估方法

三种输入方式互斥：

```python
# 方式1：程序代码字符串
result = await evaluator.evaluate_train(program)

# 方式2：workspace 目录路径
result = await evaluator.evaluate_train(workspace="/path/to/workspace")

# 方式3：老的 config 格式
result = await evaluator.evaluate_train(config={'__type__': 'all', '__data__': program})
```

其他参数：

```python
# 评估测试集
result = await evaluator.evaluate_test(program)

# 指定字段
result = await evaluator.evaluate_train(program, keys=['field1', 'field2'])

# 指定文档
result = await evaluator.evaluate_train(program, std_ids=['doc1', 'doc2'])

# 进度回调
def on_progress(event):
    if event['event'] == 'done':
        print(f"[{event['completed']}/{event['total']}] {event['std_id']}")

result = await evaluator.evaluate_train(program, progress_callback=on_progress)
```

### 保存与加载结果

评估结果自带元数据，可以直接保存和加载。

```python
# 保存结果（元数据自动包含）
result = await evaluator.evaluate_train(program)
result.save("result.json")           # 默认 indent=2
result.save("result.json", indent=4) # 指定缩进

# 加载结果
loaded = EvaluationResultWithMetadata.load("result.json")
print(loaded.eval_type)              # 'train'
print(loaded.set_id)                 # 标准集 ID
print(loaded.result.overall_accuracy) # 准确率
```

### HTML 报告生成

评估结果可以生成美观的 HTML 报告，包含：
- 元数据信息
- 总体统计（准确率、正确/错误数）
- 字段级统计表格（准确率、精确率、召回率、F1）
- 详细的每条记录评估结果（可展开/折叠，可筛选）
- **右侧 PDF 原文预览**（点击左侧记录自动加载对应 PDF）

```python
# 方式1：通过结果对象直接保存
result = await evaluator.evaluate_train(program)
result.save_html("report.html")

# 方式2：指定 base_url 以启用 PDF 预览
result.save_html("report.html", base_url="http://localhost:8008")

# 方式3：从已保存的 JSON 加载后生成
loaded = EvaluationResultWithMetadata.load("result.json")
loaded.save_html("report.html", base_url="http://localhost:8008")

# 方式4：使用独立函数
from extract_dev.api import generate_html_report, save_html_report
html_str = generate_html_report(result, base_url="...")  # 获取 HTML 字符串
save_html_report(result, "report.html", base_url="...") # 保存到文件
```

> **注意**：PDF 预览功能需要提供 `base_url` 和 `set_id`，系统会通过 DatasetApp API 获取 PDF 链接。

### 特殊值支持

序列化支持以下特殊 Python 值：

- `Ellipsis` (`...`)
- `set`
- `bytes`
- `float('inf')`, `float('-inf')`, `float('nan')`

```python
# 程序返回 ... 也可以正确序列化
from code_executor.document.models import Document

def extract(document: Document):
    return {"field": ...}  # Ellipsis
```

### 工具函数

```python
from extract_dev.api import get_article, get_standard, get_schema, list_doc_ids, get_doc_data

# 获取文档内容
article = get_article("doc-id")

# 获取标准答案
standard = get_standard("doc-id")

# 获取 schema
schema = get_schema()

# 列出文档 ID
doc_ids = list_doc_ids()                    # 训练集
doc_ids = list_doc_ids(dataset="test")      # 测试集

# 获取文档和标准答案
article, standard = get_doc_data("doc-id")
```

### EvaluationResultWithMetadata

评估结果包装类，包含原始结果和元数据。

元数据支持两种场景：
- **远程标准集**：`set_id` + `base_url` + `cache_dir`
- **本地标准集**：`data_path`

| 属性 | 说明 |
|------|------|
| `result` | 原始 EvaluationResult 对象（通过此属性访问 overall_accuracy 等） |
| `eval_type` | 评估类型 ('train' 或 'test') |
| `set_id` | 标准集 ID（远程标准集） |
| `base_url` | 标准集服务器 URL（远程标准集） |
| `cache_dir` | 缓存目录（远程标准集） |
| `data_path` | 本地标准集路径 |
| `is_remote` | 是否为远程标准集 |
| `is_local` | 是否为本地标准集 |

| 方法 | 说明 |
|------|------|
| `save(path, indent=2)` | 保存到 JSON 文件 |
|| `save_html(path)` | 保存为 HTML 报告 |
|| `load(path)` | 从 JSON 文件加载（类方法） |
