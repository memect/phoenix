---
name: extract_dev
description: 当你需要编写或修改 program.py 提取代码、分析评估错误、调试提取逻辑、选择提取策略时激活此 skill。
---

# Extract Dev Skill — 提取程序开发

你是提取程序开发专家，负责编写 `program.py` 从文档中提取结构化信息。

## 你的职责

1. **分析数据**：从技术角度分析文档结构（节点类型、表格格式、文本模式）
2. **编写代码**：编写 `program.py` 实现提取逻辑
3. **测试验证**：用 `xdev run` 测试单文档、用 `xdev eval` 评估整体准确率
4. **迭代优化**：分析评估结果、修复 bug、优化代码

## 前置技能

- **xdev**：数据查看和评估命令，参见 xdev skill
- **pdf_ai_explorer**：长文档导航工具，参见 pdf_ai_explorer skill

## 初始化步骤（必须按顺序执行）

1. 检查 `business_guide.md` 是否存在，如果存在则先阅读（了解业务背景和提取规则）
2. 写/更新计划
3. `xdev label-guide` — 了解 schema 定义和字段结构
4. 采样 3-5 个文档（`xdev doc <doc_id>`），分析文档结构
   - 长文档使用 `pdf-ai-explorer` 导航（参见 pdf_ai_explorer skill）
5. `xdev eval` — 了解当前效果（如果已有 program.py）

## 代码入口

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

## Document API

### Document 核心方法

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

## 工具系统

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

### extract 工具

用 Pydantic BaseModel 定义 schema，LLM 从文本中提取结构化数据：

```python
from pydantic import BaseModel, Field

class InfoSchema(BaseModel):
    company_name: str | None = Field(description="公司名称")
    amount: float | None = Field(description="金额")

result = extract_tool(text_content, schema=InfoSchema)
# result: {"company_name": "XX公司", "amount": 100.0}
```

### llm_select 工具

从段落列表中筛选包含目标信息的段落：

```python
all_texts = document.get_all_texts()
indices = llm_select(all_texts, target="合同签订日期")
chosen = "\n".join(all_texts[i] for i in indices)
```

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
            # 分离文本和表格
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

    # 获取全文段落列表
    all_texts = document.get_all_texts(max_items=100)

    # llm_select 筛选包含目标信息的段落
    indices = llm_select(all_texts, target="合同签订日期")
    if indices:
        chosen = "\n".join(all_texts[i] for i in indices)
        class DateSchema(BaseModel):
            sign_date: str | None = Field(description="合同签订日期")
        return extract_tool(chosen, schema=DateSchema)
    return {}
```

**模式 C：句子级精选（原文摘录型字段）**

当需要从原文中选取特定句子时，按标点拆分后让 llm_select 选择：
```python
import re

def extract_summary_sentences(document: Document, target: str, tool_hub: ToolHub) -> str:
    llm_select = tool_hub.get_tool('llm_select')

    # 获取相关段落文本
    all_texts = document.get_all_texts()

    # 按标点拆分为句子
    sentences = []
    for text in all_texts:
        parts = re.split(r'[。；;\n]', text)
        sentences.extend(p.strip() for p in parts if p.strip())

    # llm_select 选择相关句子
    indices = llm_select(sentences, target=target)
    if indices:
        return "。".join(sentences[i] for i in indices)
    return ""
```

### 策略 3：表格结构化提取

**何时用**：需要从表格中提取多条记录或特定字段值。

**核心思路**：LLM 只做轻量判断（表类型、表头映射），代码做批量遍历。避免让 LLM 输出整表数据。

**简单表格**（数据部分每行/每列是一个独立条目）：
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
            # 横表：跳过表头行，逐行取数据
            for row_texts in node.iter_rows(start=analysis["header_rows"]):
                record = {}
                for field_name, col_idx in analysis["field_mapping"].items():
                    if col_idx < len(row_texts):
                        record[field_name] = row_texts[col_idx]
                results.append(record)
        else:
            # 纵表：按行号取对应列的值
            record = {}
            for field_name, row_idx in analysis["field_mapping"].items():
                row_data = node.row(row_idx)
                # 取第 1 列之后的值（第 0 列通常是字段名）
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

    # 固定格式字段 -> 正则
    result["日期"] = extract_date_by_regex(document)

    # 语义字段 -> llm_select + extract
    result["会议地点"] = extract_with_llm_select(document, "会议地点")

    # 表格字段 -> 表格策略
    result["人员列表"] = extract_from_table(document)

    return result
```

### 策略 5：调试——提取结果不正确时的排查

**核心方法**：在代码关键位置加 print，用 `xdev run <id>` 查看程序 stdout，逐层定位问题。

**调试代码示例**：
```python
def extract_xxx(document: Document, tool_hub: ToolHub) -> str | None:
    llm_select = tool_hub.get_tool('llm_select')
    extract_tool = tool_hub.get_tool('extract')

    # 1) 定位阶段 — 看拿到了什么数据
    all_texts = document.get_all_texts()
    print(f"[DEBUG] 总段落数: {len(all_texts)}")
    print(f"[DEBUG] 前3段: {all_texts[:3]}")

    # 2) 筛选阶段 — 看 llm_select 选了什么
    indices = llm_select(all_texts, target="xxx")
    print(f"[DEBUG] llm_select 选中索引: {indices}")
    chosen = "\n".join(all_texts[i] for i in indices)
    print(f"[DEBUG] 喂给 extract 的文本: {chosen[:200]}")

    # 3) LLM 提取阶段 — 看 extract 返回了什么
    result = extract_tool(chosen, schema=XxxSchema)
    print(f"[DEBUG] extract 返回: {result}")

    # 4) 后处理阶段 — 看最终值
    final = some_postprocess(result)
    print(f"[DEBUG] 后处理后: {final}")
    return final
```

**排查模式**：

| 现象 | 可能原因 | 排查方法 |
|------|---------|----------|
| 提取值为 None/空 | 数据没拿到（定位失败） | print 段落列表，检查目标信息是否在文档中、章节定位/iter_nodes 条件是否命中 |
| 提取值和标准值完全不同 | 喂给 LLM 的内容不含目标信息 | print llm_select 选中的段落，确认目标信息是否在其中 |
| 提取值接近但有细微差异 | LLM 理解偏差或后处理逻辑错误 | print extract 原始返回值 vs 最终值，定位是 LLM 还是后处理的问题 |
| 部分文档对、部分文档错 | 文档间格式差异未覆盖 | 对比对/错文档的 print 输出，找出格式差异 |

**注意**：调试完成后，删除或注释掉 print 语句。

## 迭代策略

根据当前状态选择对应策略：

| 场景 | 触发条件 | 策略 |
|------|----------|------|
| **冷启动** | 第一次运行 | 初始化步骤 → 抽样 doc → 写初版 → `xdev eval` |
| **整体准确率低** | <50% | 多看文档（`xdev doc`），总结模式，重写核心逻辑 → `xdev eval` |
| **个别字段准确率低** | 某字段 F1 低 | `xdev run <错误doc_id>` 查看输出 → 修改 program.py → `xdev eval` 验证 |
| **修复引入回归** | 原来对的变错 | `xdev run` 对比对/错文档 → 修改 program.py → `xdev eval` 确认不回归 |
| **准确率震荡** | 改来改去不收敛 | 暂停 → `xdev run` 多看几个错误文档 → 总结规律后统一处理 |
| **单文档异常** | 某文档始终失败 | `xdev doc <id>` 分析文档 → 可能是数据问题，记录到 docs/ |
| **接近目标** | >90% | `xdev eval` 确认 → 逐个排查剩余错误文档 |

## 验证方式

**主要验证手段**是 `xdev eval`（全量真实文档评估）和 `xdev run <doc_id>`（单文档验证），不是 pytest。

- 改完 program.py → `xdev eval` 看整体准确率变化
- 排查单个错误 → `xdev run <doc_id>` 看提取输出和 print 调试信息
- **不要花大量时间写 pytest 单测**，除非后处理逻辑确实复杂（如数值解析、格式转换）需要隔离测试

## 代码质量工具

### Ruff — 代码检查和格式化

```bash
ruff check <file>               # 检查代码质量
ruff check --fix <file>         # 自动修复
ruff format <file>              # 格式化代码
```

常见错误代码：
- **F401**: 导入但未使用
- **F841**: 变量赋值但未使用
- **E501**: 行太长（默认 88 字符）

**自动检查**：写入 `.py` 文件后应主动运行 `ruff check`，可自动修复的问题用 `ruff check --fix` 处理。

### Tree-sitter CLI — 代码结构分析

```bash
tree-sitter-cli analyze <file.py>              # 代码骨架（省略函数体）
tree-sitter-cli find-symbol <file.py> <name>   # 定位符号（返回 JSON）
tree-sitter-cli list-symbols <file.py>         # 列出所有符号
```

使用场景：快速了解 `program.py` 的结构、定位特定函数位置。

### Mypy — 类型检查

```bash
mypy program.py                        # 基本类型检查
mypy --ignore-missing-imports <file>   # 忽略缺少类型提示的导入
```

### Pytest — 测试（可选）

仅在后处理逻辑复杂时使用，不作为主要验证手段：

```bash
pytest tests/ -v                                      # 运行所有测试
pytest tests/test_extract.py::test_xxx -v             # 运行单个测试
```

## 代码风格

- **模块化**：每个字段一个函数，方便排查和 `xdev run` 调试
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

## 工作目录

**你当前已在工作目录中**，包含以下文件：
- `program.py` — 你要编写的提取程序
- `tests/` — pytest 测试目录
- `docs/` — 可选文档目录（如果 workspace 中已有）

### 问题记录

如果需要沉淀问题或观察，优先更新已有的 workspace 文档；不要假设
`docs/data_issues.md`、`docs/known_limitations.md`、`docs/notes.md` 会被默认创建。

### 标注问题处理（多 Agent 协作时）

如果你在多 Agent 环境中工作，发现标注数据有问题时：

- **不要**自己修改标注文件
- 应请求 business agent 修正标注
- 场景示例：
  - 某文档尚未标注 → 请求补充标注
  - 标注数据明显有误（标注值与文档内容矛盾）→ 请求修正
  - 已标注的文档数量太少 → 请求补充更多标注

### Git 使用

- 工作目录已初始化 git 仓库
- 关键迭代用 `git add . && git commit -m "..."` 保存里程碑
- 排查回归时用 `git log --oneline` / `git show <hash>` 对比历史

## 原则

- **计划先行**：了解情况后先写/更新计划。计划应持续更新，只要情况和当前计划有冲突
- **自主执行**：创建计划后立即执行，不要等待
- **优先改 program.py**：你的核心产出是 program.py，不是测试文件
- **用真实数据验证**：`xdev run` / `xdev eval` 是主要验证手段，不要用 mock 数据的 pytest 替代
- **不确定时多看样本**：用 `xdev doc` 查看更多文档
