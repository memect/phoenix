# Simple Workflow 使用说明

## 概述

`simple_workflow` 模块支持命令行和代码接口两种调用方式。

**数据源三选一**：
- `--data-path` 本地数据目录
- `--set-id` + `--base-url` 从 API 下载
- `--dataset-url` 数据集 URL

**init_program 支持格式**：
- `.py` 文件路径
- `.json` ResultJson 文件（自动解析，type='single' 时自动开启 split_object）
- 程序代码字符串

---

## CLI 命令

### 单个标准集优化

```bash
# 从 API 下载数据并运行（最常用）
simple-workflow run \
  --init-program examples/extract_raw.py \
  --set-id "f1dd588d-4b14-4ecd-8376-0d710930df7f" \
  --base-url "http://localhost:8008" \
  --split-object \
  --result-path local/output/result.json

# 使用本地数据
simple-workflow run \
  --init-program examples/extract_raw.py \
  --data-path resources/GDDH \
  --split-object
```

### 使用 uv 运行

```bash
# 从 API 下载数据并运行
uv run simple-workflow run \
  --init-program examples/extract_raw.py \
  --set-id "f1dd588d-4b14-4ecd-8376-0d710930df7f" \
  --base-url "http://localhost:8008" \
  --split-object \
  --result-path local/output/result.json

# 使用本地数据
uv run simple-workflow run \
  --init-program examples/extract_raw.py \
  --data-path resources/GDDH \
  --split-object
```

---

## 代码接口

```python
import asyncio
from simple_workflow import run_simple_workflow, ResultJson

# 基本用法
result: ResultJson = asyncio.run(run_simple_workflow(
    init_program="examples/extract_raw.py",  # 文件路径或代码字符串
    set_id="f1dd588d-4b14-4ecd-8376-0d710930df7f",
    base_url="http://localhost:8008",
    split_object=True,
    result_path="local/output/result.json",
))

# 访问结果
print(result.meta['evaluation']['test']['field_average'])

# 带工具控制
result = asyncio.run(run_simple_workflow(
    init_program="examples/extract_raw.py",
    data_path="resources/GDDH",
    enable_tools=True,
    enabled_tools=["ner_regex_tool", "extract"],  # 指定启用的工具
    user_instruction="请特别注意日期格式的解析",  # 用户指令
))
```

---

## 主要参数

### 数据源参数（三选一）

| 参数 | 说明 |
|------|------|
| `--data-path` | 本地数据目录 |
| `--set-id` + `--base-url` | 从 API 下载数据 |
| `--dataset-url` | 数据集 URL |

### 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--init-program` | **必填** | 初始程序（.py/.json 文件或代码） |
| `--keys` | - | 要评估的字段（可多个） |
| `--split-object` | False | 按字段分别优化 |
| `--target-accuracy` | 0.9 | 目标准确率 |
| `--max-iteration` | 20 | 最大迭代次数 |
| `--result-path` | - | 结果保存路径 |

### 工具控制参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--enable-tools/--disable-tools` | 启用 | 是否启用大模型工具 |
| `--enabled-tools` | - | 启用的工具名称列表（ner_regex_tool, extract） |
| `--user-instruction` | - | 用户指令，在 reflect/optimize 提示词中全程使用 |

### 并发与调试参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--allow-key-concurrency` | False | 并发执行各字段 |
| `--max-key-concurrency` | 8 | 最大并发数 |
| `--export-trace` | False | 导出 trace 数据 |
| `--assign-id` | - | 指定运行 ID |

### 数据下载参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--max-size` | 200 | 最大数据集大小 |
| `--train-ratio` | 2/3 | 训练集比例 |
| `--download-dir` | /tmp/simple_workflow/resources | 下载目录 |
| `--no-cleanup` | False | 不清理下载的数据 |

---

## 返回结果结构

`ResultJson` 包含：
- **type**: `'all'`（整体优化）或 `'single'`（按字段分别优化）
- **data**: 程序代码（type='single' 时为 `{field: program}` 字典）
- **meta.evaluation**: 结构化评估数据
  ```json
  {
    "train": {"field_average": 0.95, "document_count": 20, ...},
    "test": {"field_average": 0.90, "document_count": 10, ...},
    "by_key": {...}  // split_object 模式下各字段详情
  }
  ```

---

## 结果文件格式

详见 [simple_workflow_返回格式标准.md](./simple_workflow_返回格式标准.md)
