# ConfigReader 使用指南

读取 simple_workflow 结果文件（`*_result.json`）中的评估统计信息。

## 位置

`src/simple_workflow/config_reader.py`

## 快速开始

```python
from simple_workflow.config_reader import ConfigReader

# 从文件加载
reader = ConfigReader("path/to/result.json")

# 或从已加载的 dict 构造
reader = ConfigReader.from_dict(data)
```

## 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `source` | `str \| None` | 结果来源标识（如 'simple_workflow'） |
| `train_accuracy` | `float \| None` | train 集整体准确率 |
| `test_accuracy` | `float \| None` | test 集整体准确率 |
| `train_field_stats` | `dict \| None` | train 集字段统计 |
| `test_field_stats` | `dict \| None` | test 集字段统计 |
| `llm_info` | `dict \| None` | LLM 配置信息 |
| `code_llm_model` | `str \| None` | 代码生成 LLM 模型名称 |
| `code_llm_base_url` | `str \| None` | 代码生成 LLM API 地址 |
| `summary_llm_model` | `str \| None` | 摘要 LLM 模型名称 |
| `summary_llm_base_url` | `str \| None` | 摘要 LLM API 地址 |

所有属性在字段缺失时返回 `None`。

## 示例

```python
reader = ConfigReader("result.json")

# 读取准确率
print(reader.train_accuracy)  # 0.716
print(reader.test_accuracy)   # 0.727

# 读取字段统计
print(reader.train_field_stats)
# {'字段名': {'accuracy': 0.716, 'recall': 1.0, 'precision': 1.0, 'f1': 1.0}}

# 获取单个字段的准确率
field_stats = reader.train_field_stats
if field_stats:
    for field_name, stats in field_stats.items():
        print(f"{field_name}: {stats['accuracy']}")

# 检查结果来源
print(reader.source)             # "simple_workflow"

# 获取 LLM 模型信息
print(reader.code_llm_model)      # "deepseek-coder"
print(reader.code_llm_base_url)   # "https://api.deepseek.com"
print(reader.summary_llm_model)   # "gpt-4o"

# 获取完整 LLM 配置
print(reader.llm_info)
# {'code_llm': {'name': '...', 'base_url': '...', 'model': '...'}, 'summary_llm': {...}}
```

## 数据来源

读取的是 result.json 中以下路径的数据：

```
__meta__.source                             → source
__meta__.evaluation.train.overall_accuracy  → train_accuracy
__meta__.evaluation.test.overall_accuracy   → test_accuracy
__meta__.evaluation.train.field_stats       → train_field_stats
__meta__.evaluation.test.field_stats        → test_field_stats
__meta__.llm_info                           → llm_info
__meta__.llm_info.code_llm.model            → code_llm_model
__meta__.llm_info.code_llm.base_url         → code_llm_base_url
__meta__.llm_info.summary_llm.model         → summary_llm_model
__meta__.llm_info.summary_llm.base_url      → summary_llm_base_url
```

详细格式规范参见 [simple_workflow_返回格式标准.md](./simple_workflow_返回格式标准.md)。
