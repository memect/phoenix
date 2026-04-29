# 提取策略增强

## 背景

AgentScope Agent 在编写 `program.py` 时，没有充分利用可用工具（`llm_select`、`extract`）和 Document 结构信息。现有策略只有一个"正则 vs LLM"的决策流程，且 LLM 提取示例只展示了最简单的全文喂入方式。

**问题**：
- 长文档全文喂 LLM 超长或噪声太多
- 不知道用 `llm_select` 做段落预筛选
- 不知道利用 Document 的层级结构（章节、标题）缩小搜索范围
- 表格提取只会让 LLM 输出整表数据，token 消耗巨大
- 不同字段特征没有对应的策略指导

## 方案

### 一、Document 模型增强

给 Document 体系添加便利方法，让策略代码可以简洁地操作表格和章节。

#### TableNode 新增方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `cell_at(row, col)` | `Cell \| None` | 按行列坐标取单元格 |
| `row(i)` | `list[str]` | 第 i 行所有单元格文本 |
| `col(i)` | `list[str]` | 第 i 列所有单元格文本 |
| `iter_rows(start, end)` | `Iterator[list[str]]` | 按行迭代 |
| `to_text(max_rows)` | `str` | 格式化为表格文本，喂 LLM 分析 |

内部基于 `cells: list[Cell]` 按 `row_index/col_index` 建立二维索引（延迟构建，缓存）。

#### Node 新增方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `collect_content()` | `list[str \| TableNode]` | 递归收集后代内容，文本节点返回字符串，表格保留节点对象 |

#### Document 新增方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_all_texts(max_items)` | `list[str]` | 所有段落文本 flat list |

### 二、策略提示词

重写 `src/agentscope_agent/prompts/strategies.py` 中的 `STRATEGIES` 常量：

1. **策略 1：正则 vs LLM 决策** — 保留现有逻辑，微调措辞
2. **策略 2：结构定位 + llm_select → extract** — 按章节粗筛 → 段落精筛 → 提取
   - 模式 A：按章节标题定位
   - 模式 B：全文段落 llm_select
   - 模式 C：句子级精选（原文摘录型字段）
3. **策略 3：表格结构化提取** — LLM 分析表头映射，代码遍历提取
4. **策略 4：分字段组合** — 不同字段特征选不同方法

详细代码示例见 `src/agentscope_agent/prompts/strategies.py`。

## 相关文件

- `src/code_executor/document/models/nodes.py` — TableNode/Node 新增方法
- `src/code_executor/document/models/document.py` — Document 新增方法
- `src/agentscope_agent/prompts/strategies.py` — 策略提示词
- [tool_strategies.md](./tool_strategies.md) — 策略提示词设计原则
