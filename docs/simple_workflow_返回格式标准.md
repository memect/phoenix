# Simple Workflow 返回格式标准

本文档定义了 `simple_workflow` 生成的结果 JSON 文件的完整格式规范。

## 概述

结果文件（`*_result.json`）包含工作流执行的完整记录，包括：
- 生成的提取程序代码
- 评估统计信息
- 迭代优化过程的完整跟踪记录

## 顶层结构

```json
{
  "__version__": "0.0.1",
  "__type__": "all" | "single",
  "__data__": <程序代码>,
  "__meta__": <元数据>
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `__version__` | string | 格式版本号 |
| `__type__` | string | 运行模式：`"all"` 表示所有字段一起优化，`"single"` 表示按字段分别优化 |
| `__data__` | string \| object | 程序代码。`"all"` 模式为字符串，`"single"` 模式为 `{字段名: 代码}` 对象 |
| `__meta__` | object | 执行元数据，包含评估结果和跟踪记录 |

---

## `__data__` 字段

### `"all"` 模式
```json
"__data__": "def extract(article): ..."
```

### `"single"` 模式（split_object）
```json
"__data__": {
  "字段1": "def extract(article): ...",
  "字段2": "def extract(article): ..."
}
```

---

## `__meta__` 字段

```json
"__meta__": {
  "source": "simple_workflow",   // 结果来源标识
  "overall_report": <总体报告文本>,
  "elapsed_time_seconds": <耗时秒数>,
  "elapsed_time_formatted": <格式化耗时>,
  "evaluation": <评估统计>,
  "llm_info": <LLM配置信息>,      // 模型信息
  "trace": <跟踪记录>        // "all" 模式
  "traces": <跟踪记录字典>   // "single" 模式
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 结果来源标识，固定为 `"simple_workflow"`，用于区分不同流程的配置 |

---

### `llm_info` - LLM配置信息

记录工作流使用的大语言模型配置：

```json
"llm_info": {
  "code_llm": {
    "name": "deepseek-coder",        // 配置名称
    "base_url": "https://api.deepseek.com",  // API 地址
    "model": "deepseek-coder"        // 模型名称
  },
  "summary_llm": {
    "name": "gpt-4o",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code_llm` | object | 代码生成 LLM 的配置信息 |
| `summary_llm` | object | 摘要/分析 LLM 的配置信息 |
| `name` | string | 配置中的名称标识 |
| `base_url` | string | API 基础地址 |
| `model` | string | 模型名称 |

---

### `evaluation` - 评估统计

`"all"` 和 `"single"` 模式格式相同：
```json
"evaluation": {
  "train": <EvaluationStats>,
  "test": <EvaluationStats>
}
```

**注意**：`"single"` 模式会将所有字段的程序组合后做整体评估，`overall_accuracy` 表示所有字段都正确的文档占比。

#### EvaluationStats 结构

```json
{
  "field_count": 2,                    // 字段数量
  "field_average": 0.69,               // 字段平均准确率（各字段准确率的算术平均）
  "document_count": 66,                // 文档数量
  "overall_accuracy": 0.69,            // 整体准确率（所有字段都正确的文档数 / 总文档数）
  "total_correct": 46,                 // 完全正确的文档数量
  "detail_report": "...",              // 详细报告文本（仅 "all" 模式有）
  "field_stats": {
    "字段名": {
      "accuracy": 0.51,                // 准确率
      "recall": 1.0,                   // 召回率
      "precision": 1.0,                // 精确率
      "f1": 1.0                        // F1 分数
    }
  }
}
```

**指标说明**：
- `overall_accuracy`：整体准确率，一个文档只有所有字段都提取正确才计入正确
- `field_average`：字段平均准确率，各字段准确率的简单平均值
- 通常 `overall_accuracy` ≤ `field_average`，因为整体要求更严格

---

## `trace` / `traces` - 跟踪记录

### `"all"` 模式：`trace`
```json
"trace": <TraceData>
```

### `"single"` 模式：`traces`
```json
"traces": {
  "字段名1": <TraceData>,
  "字段名2": <TraceData>
}
```

### TraceData 结构

```json
{
  "metadata": <TraceMetadata>,
  "programs": { <program_id>: <ProgramData> },
  "iterations": [<Iteration>],
  "final_result": <FinalResult>
}
```

---

## TraceMetadata - 跟踪元数据

```json
{
  "workflow_id": "uuid",
  "run_id": "uuid",
  "start_time": "2025-12-17T15:10:16.232762",
  "end_time": "2025-12-17T15:21:55.100408",
  "status": "收敛" | "达到最大迭代" | "错误",
  "config": {
    "run_type": "数据集标识",
    "keys": ["字段1", "字段2"],
    "target_accuracy": 0.97,
    "max_iterations": 20
  }
}
```

---

## ProgramData - 程序数据

```json
{
  "code": "def extract(article): ...",
  "evaluations": [<EvaluationDetail>]
}
```

### EvaluationDetail - 评估详情

```json
{
  "schema_": {
    "fields": { "字段名": "类型" }
  },
  "details": [<RecordDetail>],
  "overall_accuracy": 0.51,
  "total_records": 33,
  "total_correct": 17,
  "field_stats": { ... }
}
```

### RecordDetail - 记录级评估详情

支持两种格式：**object** 和 **list_of_objects**

#### Object 格式（单对象提取）

```json
{
  "type": "correct" | "incorrect",
  "extra_info": {},
  "extracted_info": {
    "id": "generated",
    "labels": { "字段名": "提取值" },
    "success": true,
    "runtime_info": {
      "exception_info": null,
      "stdout": "程序输出...",
      "stderr": ""
    },
    "raw_data": { "字段名": "提取值" }
  },
  "standared_info": {
    "id": "文档ID (UUID)"
  },
  "related_field_details": [
    {
      "name": "字段名",
      "extracted_value": "提取值",
      "standard_value": "标准值",
      "type": "correct" | "incorrect" | "missing" | "extra"
    }
  ]
}
```

#### List of Objects 格式（列表提取）

```json
{
  "type": "correct" | "incorrect",
  "extra_info": {},
  "extracted_info": { ... },
  "standared_info": { "id": "文档ID" },
  "missing": [<标准中有但提取中没有的对象>],
  "extra": [<提取中有但标准中没有的对象>],
  "matched": [<MatchedItem>]
}
```

##### MatchedItem 结构（matched 数组元素）

```json
{
  "standard_value": { "字段名": "标准值" },
  "extracted_value": { "字段名": "提取值" },
  "similarity_score": 1.0,               // 相似度分数
  "std_list_idx": 0,                     // 标准列表中的索引
  "ext_list_idx": 0,                     // 提取列表中的索引
  "incorrect_fields": ["字段名"],        // 不正确的字段
  "correct_fields": ["字段名"],          // 正确的字段
  "extra_fields": [],                    // 多余的字段
  "missing_fields": []                   // 缺失的字段
}
```

**注意**：`standared_info.id` 是文档的唯一标识符，可用于关联 PDF 链接。

---

## Iteration - 迭代记录

```json
{
  "round": 0,                          // 迭代轮次（从0开始）
  "timestamp": "2025-12-17T15:10:16",
  "steps": [<Step>],
  "iteration_context": <IterationContext>  // 迭代上下文（可选，仅有 reflect 步骤时存在）
}
```

### IterationContext - 迭代上下文

记录每轮迭代中选中的文档及其分析结果。

```json
{
  "selected_document_ids": ["doc_id_1", "doc_id_2", ...],  // 本轮选中的文档 ID 列表
  "document_analyses": {                                   // 文档分析结果映射
    "doc_id_1": <DocumentAnalysis>,
    "doc_id_2": <DocumentAnalysis>
  }
}
```

**注意**：源程序 ID 可通过同轮迭代的 reflect step 的 `program_id` 字段获取。

### DocumentAnalysis - 文档分析结果

```json
{
  "report_type": "detail" | "summary",   // 报告类型
  "diagnosis": "错误分析内容...",        // 单文档诊断结果
  "related_info": {                      // 仅 summary 类型有此字段
    "related_info_lists": [<RelatedInfo>]
  }
}
```

#### RelatedInfo - 相关信息条目

```json
{
  "title_hierarchy": ["标题1", "子标题"],  // 原文的标题层级
  "content": "原文内容...",               // 原文的内容
  "description": "补充描述...",           // 对原文的补充描述
  "summary": "为什么相关..."              // 对原文为什么是相关信息的总结
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `selected_document_ids` | `list[str]` | 本轮迭代随机选中的错误文档 ID 列表 |
| `document_analyses` | `object` | doc_id -> DocumentAnalysis 映射 |
| `report_type` | `string` | `"detail"` 使用完整 md 内容，`"summary"` 使用 LLM 提取的关键信息 |
| `diagnosis` | `string` | 针对该文档的错误诊断分析 |
| `related_info` | `object` | 仅 `summary` 类型有，包含 LLM 从原文提取的结构化关键信息 |

### Step - 步骤记录

```json
{
  "step_type": "init" | "reflect" | "optimize" | "terminate",
  "step_id": "58",
  "start_time": "...",
  "stop_time": "...",
  "program_id": "uuid",                // 关联的程序 ID（可选）
  "llm_interaction": {                 // LLM 交互记录（可选）
    "input_messages": [...],
    "output": "...",
    "result": "..."
  }
}
```

---

## FinalResult - 最终结果

```json
{
  "status": "收敛" | "达到最大迭代" | "错误",
  "stop_reason": "达到目标准确率",
  "final_accuracy": 0.87,
  "best_program_id": "uuid"
}
```

---

## 使用示例

### 读取结果文件
```python
import json

with open('result.json') as f:
    result = json.load(f)

# 获取程序代码
if result['__type__'] == 'all':
    code = result['__data__']
else:
    codes = result['__data__']  # {字段名: 代码}

# 获取评估结果
eval_stats = result['__meta__']['evaluation']
train_accuracy = eval_stats['train']['overall_accuracy']

# 获取跟踪记录
if result['__type__'] == 'all':
    trace = result['__meta__']['trace']
else:
    traces = result['__meta__']['traces']  # {字段名: trace}
```

### 生成 HTML 报告
```bash
uv run python -m simple_workflow.report_generator result.json --set-id <标准集ID>
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.0.4 | 2025-01 | 新增 `source` 字段标识结果来源；新增 `llm_info` 字段记录 LLM 配置信息 |
| 0.0.3 | 2025-12-24 | `single` 模式移除 `by_key` 字段，改为整体评估；明确 `overall_accuracy` 和 `field_average` 的区别 |
| 0.0.2 | 2025-12 | 增加 `iteration_context` 字段，记录每轮迭代选中的文档、诊断结果和提取的关键信息 |
| 0.0.1 | 2025-12 | 初始版本 |
