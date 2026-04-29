# 策略提示词设计

本文档说明策略提示词（Strategies）的设计原则和使用方式。

> **完整方案**：参见 [VLM 提取方案](./vlm_extract_solution.md)

## 概述

策略提示词是 Agent 系统提示词的一部分，指导 Agent **何时**以及**为什么**选择某种提取策略。

位置：`src/agentscope_agent/prompts/strategies.py`

## 策略提示词 vs LLM 工具指南

系统中有两类工具相关的提示词，服务于不同目的：

| 类型 | 位置 | 目的 | 阶段 |
|------|------|------|------|
| 策略提示词（STRATEGIES） | `agentscope_agent/prompts/strategies.py` | 指导**何时**使用某种策略 | 决策阶段 |
| LLM 工具指南（LLM Guide） | `code_executor/tools/` 各工具定义 | 说明**如何**调用工具 API | 执行阶段 |

### 策略提示词示例

```python
STRATEGIES = """
## 代码书写策略

### vlm_extract - VLM 图片提取

**何时使用**：
- 所有文档都用 VLM 提取，忽略结构化解析结果

**配合 pdf_to_image 使用**：
```python
# 示例代码...
```
"""
```

**特点**：
- 解释**使用场景**和**决策依据**
- 包含完整的使用模式示例
- 位于 Agent 系统提示词中

### LLM 工具指南示例

```python
class VLMExtractTool:
    llm_guide = """
    从图片中提取结构化数据。

    参数：
    - images: 图片（URL/base64/路径/bytes）
    - schema: pydantic BaseModel 类

    返回：dict
    """
```

**特点**：
- 解释**API 签名**和**参数说明**
- 通过 `extract-dev context` 输出给 Agent
- 是 API 参考文档

## 设计原则

### 1. 策略提示词应关注"何时"和"为什么"

**好的写法**：
```
**何时使用**：
- 文档是扫描件/图片型 PDF，文字无法直接提取
- 表格以图片形式存在，结构化解析失败
```

**不好的写法**（这属于 LLM Guide）：
```
**参数说明**：
- images: str | list[str] - 图片输入
- schema: type[BaseModel] - 输出结构
```

### 2. 策略提示词应包含完整示例

Agent 需要看到完整的代码模式才能正确实现，而不是只看 API 签名。

```python
**配合 pdf_to_image 使用**：
```python
def extract(document: Document, tool_hub: ToolHub) -> dict:
    if document.raw_bytes:
                pdf_tool = tool_hub.get_tool('pdf_to_image')
        vlm_tool = tool_hub.get_tool('vlm_extract')
        
        images = pdf_tool(document.raw_bytes, pages=1)
        result = vlm_tool(images, schema=MySchema)
        return result
    
    # fallback 逻辑...
```
```

### 3. 策略提示词应保持简洁

策略提示词会包含在每次 Agent 对话中，过长会占用上下文。只包含最关键的决策信息和示例。

## 如何添加新策略

### 步骤 1：编辑 strategies.py

`src/agentscope_agent/prompts/strategies.py`:

```python
STRATEGIES = """
## 代码书写策略

### 现有策略...

### 新策略名称

**何时使用**：
- 使用场景 1
- 使用场景 2

**示例**：
```python
def extract(document: Document, tool_hub: ToolHub) -> dict:
    # 完整示例代码
    ...
```
"""
```

### 步骤 2：确保工具已注册

如果策略依赖新工具，确保工具已在 `code_executor/tools/` 中实现并注册。

### 步骤 3：更新 LLM Guide（如需要）

如果需要更详细的 API 说明，在工具类中添加 `llm_guide` 属性。

## 文件结构

```
src/agentscope_agent/prompts/
├── strategies.py      # 策略提示词（STRATEGIES 常量）
├── extract_dev.py     # ExtractDevAgent 提示词（引用 STRATEGIES）
├── supervisor.py      # Supervisor 提示词
├── business.py        # BusinessAgent 提示词
└── code_agent.py      # CodeAgent 提示词
```

## 策略提示词的加载流程

```
┌─────────────────────────────────────────┐
│  strategies.py 定义 STRATEGIES 常量      │
└───────────────────┬─────────────────────┘
                    ▼
┌─────────────────────────────────────────┐
│  extract_dev.py 引入 STRATEGIES         │
│  from .strategies import STRATEGIES     │
└───────────────────┬─────────────────────┘
                    ▼
┌─────────────────────────────────────────┐
│  SYSTEM_PROMPT 模板包含 {strategies}    │
│  组装 ExtractDevAgent 系统提示词         │
└───────────────────┬─────────────────────┘
                    ▼
┌─────────────────────────────────────────┐
│  Agent 运行时获得策略指导                │
└─────────────────────────────────────────┘
```

## 提取策略详见

策略提示词已扩展为 4 个策略（正则 vs LLM、结构定位+llm_select、表格结构化提取、分字段组合），详见 [extraction_strategies.md](./extraction_strategies.md)。

## 相关文件

| 文件 | 功能 |
|------|------|
| `agentscope_agent/prompts/strategies.py` | 策略提示词定义 |
| `agentscope_agent/prompts/extract_dev.py` | ExtractDevAgent 提示词模板 |
| `code_executor/tools/tool_defines/*.py` | 各工具的 llm_guide 定义 |
| [extraction_strategies.md](./extraction_strategies.md) | 提取策略增强方案 |
