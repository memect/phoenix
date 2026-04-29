---
name: extract-workflow
description: 当用户要求对某类文档或数据集开发提取程序时激活。提供从数据分析、schema 定义、标注、代码开发到评估迭代的完整无标注工作流。
---

# 提取程序开发工作流

你是提取程序开发专家。当用户提供一个数据集（PDF 文档集合），你负责走完从零开始的完整提取开发流程：分析文档、定义 schema、标注数据、编写提取代码、评估并迭代优化。

## 前置工具

- **xdev**：数据管理和评估 CLI，参见 xdev skill
- **pdf-ai-explorer**：长文档导航工具，参见 pdf_ai_explorer skill

## 完整工作流

```
阶段 1：数据分析     → 了解文档内容和结构
阶段 2：定义 Schema  → 确定需要提取的字段
阶段 3：标注数据     → 为文档标注评估基准
阶段 4：编写提取代码 → 编写 program.py
阶段 5：评估和迭代   → 提升准确率直到达标
```

---

## 阶段 1：数据分析

目标：理解文档类型、结构特征、包含的信息种类。

### 步骤

1. `xdev list` 查看文档列表和数量
2. 采样最多 20 篇代表性文档
3. `xdev doc <doc_id>` 阅读文档内容
   - 长文档使用 `pdf-ai-explorer` 导航（参见 pdf_ai_explorer skill）：
     - `pdf-ai-explorer outline <docjson_path>` — 查看大纲
     - `pdf-ai-explorer search <docjson_path> "关键词"` — 搜索定位
     - `pdf-ai-explorer read <docjson_path> --pages 1-5` — 按页阅读
4. 总结发现：文档类型、共同结构、可提取的信息

### 输出

对文档集的整体理解，为下一步 schema 定义做准备。

---

## 阶段 2：定义 Schema

目标：根据文档内容和用户需求，确定需要提取的字段。

### Schema 类型选择

**object（单条记录）**：每篇文档提取一组信息。适用于文档中只有一组目标信息的场景。

```json
{"type": "object", "data": {"公司名称": "str", "金额": "float"}}
```

**list_of_objects（多条记录）**：每篇文档提取多组同类信息。适用于文档中包含多组重复结构信息的场景（如多个股东、多笔交易）。

```json
{"type": "list_of_objects", "data": {"股东名称": "str", "持股比例": "float"}}
```

### 如何选择

- 文档中同类信息只有一条 → `object`
- 文档中有多条重复结构的同类信息 → `list_of_objects`

### 字段类型

`"str"` / `"int"` / `"float"` / `"bool"` / `"list"`

**约束**：只支持扁平一层结构，不支持嵌套。

### 写入

直接创建 `.xdev/schema.json` 文件。

---

## 阶段 3：标注数据

目标：为每个文档手动提取字段值作为评估基准。

### 步骤

1. `xdev label-guide` 确认 schema 已加载
2. `xdev label-guide <doc_id>` 获取标注模板
3. 阅读文档（`xdev doc <doc_id>`，长文档用 `pdf-ai-explorer`），从中提取字段值
4. 将标注写入 `.xdev/labels/<doc_id>.json`
5. **标注所有文档**

### 标注格式

**object 模式**：
```json
{"公司名称": "XX公司", "金额": 100.0}
```

**list_of_objects 模式**：
```json
[{"股东名称": "张三", "持股比例": 30.0}, {"股东名称": "李四", "持股比例": 20.0}]
```

### 标注要求

- 标注必须基于文档原文，不能臆测
- 标注的 key 必须与 `schema.json` 的 `data` key 完全一致
- 缺失信息标注为空字符串 `""` 或 `null`
- 要尽量准确，标注将作为评估基准

### 生成业务指导（推荐）

创建 `business_guide.md` 记录分析结论，方便后续迭代参考：

```markdown
# 业务指导

## 数据集概述
- 文档类型: [描述]
- 文档数量: [N 篇]
- 主要内容: [简述]

## Schema 字段说明
### [字段名]
- 业务含义: [详细解释]
- 数据特点: [在文档中通常如何出现]
- 提取建议: [建议的提取策略]

## 数据特点与注意事项
- [列出发现的数据特点]
- [列出可能的陷阱或难点]
```

---

## 阶段 4：编写提取代码

目标：编写 `program.py` 实现提取逻辑。

### 初始化步骤（必须按顺序执行）

1. 阅读 `business_guide.md`（如果存在）
2. `xdev label-guide` — 了解 schema 定义和字段结构
3. 采样 3-5 个文档（`xdev doc <doc_id>`），分析文档结构
4. 编写初版 `program.py`
5. `xdev run <doc_id>` — 测试单文档提取

### 代码入口

文件路径：`program.py`

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub) -> dict:
    """从文档中提取结构化信息

    Args:
        document: Document 对象（树状结构）

    Returns:
        字段名 -> 值 的字典（key 必须与 schema.json 的 data key 一致）
    """
    ...
```

### Document API

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub

# 获取节点
node = document.get_node(node_id)

# 获取指定页面的所有节点
nodes = document.get_nodes_by_page(page_num)

# 遍历所有节点（可按类型过滤: "title", "section", "table", "figure"）
for node in document.iter_nodes(type_filter="title"):
    ...

# 获取所有段落文本（flat list）
texts = document.get_all_texts(max_items=100)

# 文档属性
document.total_pages
```

### Node 核心方法

```python
# 内容
node.get_title()        # 节点标题
node.get_text()         # 节点文本

# 导航
node.get_children()     # 子节点
node.get_parent()       # 父节点
node.collect_content()  # 递归收集后代内容 -> list[str | TableNode]

# 属性
node.id, node.type, node.page_number, node.level
```

### TableNode 方法

```python
from code_executor.document.models.nodes import HeadingNode, TableNode

node.to_text(max_rows=8)          # 格式化文本（喂 LLM）
node.row(i)                       # 第 i 行各列文本
node.col(i)                       # 第 i 列各行文本
node.cell_at(row, col)            # 获取单元格
node.iter_rows(start, end)        # 按行迭代
node.row_num, node.col_num        # 行列数
```

### 工具系统

`xdev run` / `xdev eval` 会自动读取配置并把 `tool_hub` 注入到
`extract(document, tool_hub)`。

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub) -> dict:
    extract_tool = tool_hub.get_tool('extract')      # LLM 结构化提取
    llm_select = tool_hub.get_tool('llm_select')      # LLM 段落筛选
    ...
```

#### extract 工具

用 Pydantic BaseModel 定义 schema，LLM 从文本中提取结构化数据：

```python
from pydantic import BaseModel, Field

class InfoSchema(BaseModel):
    company_name: str | None = Field(description="公司名称")
    amount: float | None = Field(description="金额")

result = extract_tool(text_content, schema=InfoSchema)
# result: {"company_name": "XX公司", "amount": 100.0}
```

#### llm_select 工具

从段落列表中筛选包含目标信息的段落：

```python
all_texts = document.get_all_texts()
indices = llm_select(all_texts, target="合同签订日期")
chosen = "\n".join(all_texts[i] for i in indices)
```

---

## 提取策略（强制遵守）

以下策略是**强制性要求**，优先级高于自主判断。

### 策略 1：正则 vs LLM 决策

**决策流程**：
1. 对每个字段，先快速试探是否存在稳定的正则模式
2. 有模式 → 写正则代码，用评估结果判断是否继续
3. 无模式 / 达不到标准 → 切换 LLM

**正则适用的判断标准**（注意：这只是判断"正则方案是否可行"的阈值，**不是**整体目标准确率。整体目标以 Supervisor 指定的为准）：
1. 初版代码就有高准确率
2. 每次优化能解决 10%+ 的文档问题
3. 正则方案能达到 80%+ 准确率

正则达不到这些标准 → 切换 LLM。可以完全切换，也可以正则覆盖大部分、LLM 兜底。切换 LLM 后应继续优化直到达到 Supervisor 指定的目标准确率。

**LLM 提取基本模式**：
```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub
from pydantic import BaseModel, Field

def extract(document: Document, tool_hub: ToolHub) -> dict:
    extract_tool = tool_hub.get_tool('extract')

    # 多个字段合并成一个 schema，一次 LLM 调用提取
    class ExtractSchema(BaseModel):
        title: str | None = Field(description="文档标题")
        category: str | None = Field(description="文档类别")

    # 获取全文段落，拼接为文本
    all_texts = document.get_all_texts()
    content = "\n".join(all_texts)
    result = extract_tool(content, schema=ExtractSchema)
    return result
```

### 策略 2：结构定位 + llm_select 缩小范围 + extract 提取

**何时用**：长文档、字段属于特定章节、全文喂 LLM 超长或噪声太多。

**核心思路**：先用 Document 层级结构按章节粗筛，再用 llm_select 精筛段落，最后 extract 提取。

**模式 A：按章节标题定位 → llm_select → extract**
```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub
from code_executor.document.models.nodes import HeadingNode, TableNode
from pydantic import BaseModel, Field

def extract(document: Document, tool_hub: ToolHub) -> dict:
    llm_select = tool_hub.get_tool('llm_select')
    extract_tool = tool_hub.get_tool('extract')

    # 1) 按章节标题定位
    for node in document.iter_nodes("title"):
        if "基本信息" in node.get_text():
            # 2) 收集该章节下所有内容（文本 + TableNode）
            content = node.collect_content()
            texts = [c for c in content if isinstance(c, str)]

            # 3) llm_select 精筛相关段落
            indices = llm_select(texts, target="注册资本")
            if indices:
                chosen = "\n".join(texts[i] for i in indices)

                # 4) extract 结构化提取
                class InfoSchema(BaseModel):
                    reg_capital: str | None = Field(description="注册资本")
                result = extract_tool(chosen, schema=InfoSchema)
                return result

    return {}
```

**模式 B：全文段落 llm_select（无明确章节时）**
```python
def extract(document: Document, tool_hub: ToolHub) -> dict:
    llm_select = tool_hub.get_tool('llm_select')
    extract_tool = tool_hub.get_tool('extract')

    all_texts = document.get_all_texts(max_items=100)
    indices = llm_select(all_texts, target="合同签订日期")
    if indices:
        chosen = "\n".join(all_texts[i] for i in indices)
        class DateSchema(BaseModel):
            sign_date: str | None = Field(description="合同签订日期")
        return extract_tool(chosen, schema=DateSchema)
    return {}
```

**模式 C：句子级精选（原文摘录型字段）**
```python
import re

def extract_summary_sentences(document: Document, target: str, tool_hub: ToolHub) -> str:
    llm_select = tool_hub.get_tool('llm_select')

    all_texts = document.get_all_texts()
    sentences = []
    for text in all_texts:
        parts = re.split(r'[。；;\n]', text)
        sentences.extend(p.strip() for p in parts if p.strip())

    indices = llm_select(sentences, target=target)
    if indices:
        return "。".join(sentences[i] for i in indices)
    return ""
```

### 策略 3：表格结构化提取

**何时用**：需要从表格中提取多条记录或特定字段值。

**核心思路**：LLM 只做轻量判断（表类型、表头映射），代码做批量遍历。避免让 LLM 输出整表数据。

```python
from typing import Literal
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub
from code_executor.document.models.nodes import TableNode
from pydantic import BaseModel, Field

def extract(document: Document, tool_hub: ToolHub) -> dict:
    extract_tool = tool_hub.get_tool('extract')

    results = []
    for node in document.iter_nodes("table"):
        if not isinstance(node, TableNode) or node.row_num < 2:
            continue

        # 1) 将表格前几行喂给 LLM，分析结构
        preview = node.to_text(max_rows=8)

        class TableAnalysis(BaseModel):
            '''分析表格结构'''
            orientation: Literal["horizontal", "vertical"] = Field(
                description="horizontal=每行一条记录(横表), vertical=每行是一个字段(纵表)"
            )
            header_rows: int = Field(description="表头占几行(横表)，纵表填0")
            field_mapping: dict[str, int] = Field(
                description="目标字段名 -> 列号(横表)或行号(纵表)的映射"
            )

        analysis = extract_tool(
            f"分析这个表格，找出以下字段的位置：姓名、职务、持股数\n\n{preview}",
            schema=TableAnalysis
        )

        # 2) 代码遍历提取
        if analysis["orientation"] == "horizontal":
            for row_texts in node.iter_rows(start=analysis["header_rows"]):
                record = {}
                for field_name, col_idx in analysis["field_mapping"].items():
                    if col_idx < len(row_texts):
                        record[field_name] = row_texts[col_idx]
                results.append(record)
        else:
            record = {}
            for field_name, row_idx in analysis["field_mapping"].items():
                row_data = node.row(row_idx)
                record[field_name] = row_data[1] if len(row_data) > 1 else ""
            results.append(record)

    return {"records": results}
```

**TableNode 便利方法速查**：
- `node.to_text(max_rows=8)` → 格式化表格文本，喂 LLM 分析
- `node.row(i)` → 第 i 行各列文本
- `node.col(i)` → 第 i 列各行文本
- `node.cell_at(row, col)` → 获取单元格 Cell 对象
- `node.iter_rows(start, end)` → 按行迭代
- `node.row_num`, `node.col_num` → 行列数

### 策略 4：分字段组合

不同字段特征适合不同策略，在 `extract()` 中组合使用：

- **固定格式字段**（日期、编号、金额）→ 正则优先，extract 兜底
- **语义理解字段**（摘要、描述、原因）→ llm_select 定位 + extract 提取
- **分类型字段**（类别、状态、类型）→ extract + `Literal["A", "B", "C"]`
- **表格数据字段**（人员列表、财务数据）→ 表格结构化提取（策略 3）
- **原文摘录字段** → 句子级 llm_select（策略 2 模式 C）

```python
def extract(document: Document, tool_hub: ToolHub) -> dict:
    result = {}
    result["日期"] = extract_date_by_regex(document)
    result["会议地点"] = extract_with_llm_select(document, "会议地点")
    result["人员列表"] = extract_from_table(document)
    return result
```

### 策略 5：调试——提取结果不正确时的排查

**核心方法**：在代码关键位置加 print，用 `xdev run <id>` 查看程序 stdout，逐层定位问题。

```python
def extract(document: Document, tool_hub: ToolHub) -> str | None:
    llm_select = tool_hub.get_tool('llm_select')
    extract_tool = tool_hub.get_tool('extract')

    # 1) 定位阶段
    all_texts = document.get_all_texts()
    print(f"[DEBUG] 总段落数: {len(all_texts)}")
    print(f"[DEBUG] 前3段: {all_texts[:3]}")

    # 2) 筛选阶段
    indices = llm_select(all_texts, target="xxx")
    print(f"[DEBUG] llm_select 选中索引: {indices}")
    chosen = "\n".join(all_texts[i] for i in indices)
    print(f"[DEBUG] 喂给 extract 的文本: {chosen[:200]}")

    # 3) LLM 提取阶段
    result = extract_tool(chosen, schema=XxxSchema)
    print(f"[DEBUG] extract 返回: {result}")

    return result
```

**排查模式**：

| 现象 | 可能原因 | 排查方法 |
|------|---------|----------|
| 提取值为 None/空 | 数据没拿到（定位失败） | print 段落列表，检查目标信息是否在文档中 |
| 提取值和标准值完全不同 | 喂给 LLM 的内容不含目标信息 | print llm_select 选中的段落 |
| 提取值接近但有细微差异 | LLM 理解偏差或后处理错误 | print extract 原始返回值 vs 最终值 |
| 部分文档对、部分文档错 | 文档间格式差异未覆盖 | 对比对/错文档的 print 输出 |

**注意**：调试完成后，删除或注释掉 print 语句。

---

## 阶段 5：评估和迭代

目标：提升准确率直到达标。

### 评估命令

```bash
xdev eval                       # 全量评估
xdev eval <doc_id>              # 单文档评估
xdev run <doc_id>               # 执行提取并查看结果
```

### 迭代策略

| 场景 | 触发条件 | 策略 |
|------|----------|------|
| **冷启动** | 第一次运行 | 阶段 4 初始化步骤 → 抽样 doc → 写初版 → eval |
| **整体准确率低** | <50% | 多看文档，总结模式，重写核心逻辑 |
| **个别字段准确率低** | 某字段 F1 低 | `xdev run` 查看错误 → 写字段级单元测试 → 修复 |
| **修复引入回归** | 原来对的变错 | 对比差异 → 添加回归测试 → 分支处理 |
| **准确率震荡** | 改来改去不收敛 | 暂停 → 回顾已有测试 → 总结规律后统一处理 |
| **单文档异常** | 某文档始终失败 | 仔细分析 → 写该文档回归测试 → 可能是标注问题 |
| **接近目标** | >90% | 补充边界测试 |

### 标注问题处理

评估中发现标注有误（标注值与文档内容矛盾）时：
1. 阅读对应文档确认问题
2. 修正 `.xdev/labels/<doc_id>.json` 中的标注
3. 在 `business_guide.md` 记录修正原因

---

## pytest 单元测试

**何时写测试**（必须遵守）：
1. 修 bug 前 → 先写测试复现问题
2. 发现特殊模式 → 立即写测试覆盖
3. 发现一个新的模式 → 立即写测试覆盖

简单说：**先测试，后改代码**。

```python
def test_date_extraction():
    '''测试日期提取'''
    result = {'原文_会议召开时间': '2024年1月15日'}
    assert result.get("原文_会议召开时间") == "2024年1月15日"
```

```bash
pytest tests/ -v                              # 运行所有测试
pytest tests/test_extract.py::test_xxx -v     # 运行单个测试
pytest -s tests/                               # 显示 print 输出
```

---

## 代码质量

### 代码风格

- **模块化**：每个字段一个函数，方便单元测试
- **先测试，后改代码**
- **复杂逻辑独立**：提取为独立函数

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub

def extract_date(document: Document) -> str | None:
    '''提取日期'''
    ...

def extract_meeting_method(document: Document) -> str | None:
    '''提取会议召开方式'''
    ...

def extract(document: Document, tool_hub: ToolHub) -> dict:
    return {
        "原文_会议召开时间": extract_date(document),
        "原文_会议召开方式": extract_meeting_method(document),
    }
```

### Ruff — 代码检查和格式化

```bash
ruff check <file>               # 检查代码质量
ruff check --fix <file>         # 自动修复
ruff format <file>              # 格式化代码
```

### Tree-sitter CLI — 代码结构分析

```bash
tree-sitter-cli analyze <file.py>              # 代码骨架
tree-sitter-cli find-symbol <file.py> <name>   # 定位符号
tree-sitter-cli list-symbols <file.py>         # 列出所有符号
```

---

## 工作目录

你当前已在工作目录中，包含以下文件：
- `program.py` — 你要编写的提取程序
- `.xdev/` — 数据目录（schema、标注、文档）
- `business_guide.md` — 业务指导文档（你创建）
- `tests/` — pytest 测试目录
- `docs/` — 可选文档目录（如果 workspace 中已有）

### 问题记录

如需记录数据问题、限制或观察，请补充到已有 workspace 文档中；不要假设
`docs/*.md` 会被默认创建。

### Git 使用

- 工作目录已初始化 git 仓库
- 关键迭代用 `git add . && git commit -m "..."` 保存里程碑
- 排查回归时用 `git log --oneline` / `git show <hash>` 对比历史

## 原则

- **计划先行**：了解情况后先写/更新计划，计划应持续更新
- **自主执行**：创建计划后立即执行，不要等待
- **不破坏已有功能**：修复 bug 时先写回归测试
- **不确定时多看样本**：用 `xdev doc` 查看更多文档
- **分析必须基于实际文档内容**，不要臆测
