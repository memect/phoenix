"""
工具函数模块

提供各种辅助函数。
"""

import pathlib


def get_structure_code() -> str:
    """获取结构化代码
    
    Returns:
        structure.py 文件的内容
    """
    with pathlib.Path(__file__).parent.joinpath("structure.py").open("r") as f:
        structure_code = f.read()
    return structure_code


def _get_tree_signature() -> str:
    """获取 tree 模式的代码入口签名"""
    return """## 代码入口签名

```python
from code_executor.document.models import Document
from code_executor.tools import ToolHub
from typing import Any

def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any]:
    \"\"\"
    从文档中提取结构化信息
    
    Args:
        document: Document 对象（树状结构）
        tool_hub: xdev 自动注入的工具中心
        
    Returns:
        提取的结构化数据
    \"\"\"
    ...
```
"""


def _get_document_api_doc() -> str:
    """获取 Document API 文档"""
    return """## Document 对象 API

Document 是树状文档结构，包含节点树和索引。

### Document 核心方法

```python
# 获取节点
node = document.get_node(node_id: int | str) -> Node | None

# 获取指定页面的所有节点
nodes = document.get_nodes_by_page(page_num: int) -> list[Node]

# 遍历所有节点（可按类型过滤）
for node in document.iter_nodes(type_filter: str | None = None):
    # type_filter: "title", "section", "table", "figure"
    ...

# 获取所有段落文本（flat list，可直接用于 llm_select）
texts = document.get_all_texts(max_items: int | None = None) -> list[str]

# 文档属性
document.total_pages  # 总页数
```

## Node 对象 API

Node 是文档中的语义单元（标题、段落、表格、图片）。

### Node 核心方法

```python
# 获取内容
title = node.get_title() -> str      # 节点标题
text = node.get_text() -> str        # 节点文本内容

# 导航
children = node.get_children() -> list[Node]  # 子节点
parent = node.get_parent() -> Node | None     # 父节点
siblings = node.get_siblings() -> list[Node]  # 兄弟节点（包括自己）
ancestors = node.get_ancestors() -> list[Node] # 祖先节点

# 收集后代内容（文本 + TableNode 混合列表，用于章节级内容收集）
content = node.collect_content() -> list[str | TableNode]

# 节点属性
node.id             # 节点 ID
node.type           # 节点类型: "title", "section", "table", "figure"
node.page_number    # 起始页码
node.end_page_number # 结束页码
node.level          # 层级深度（根节点的子节点为 level 1）
```

## 节点类型

### HeadingNode（标题节点）

```python
if node.type == "title":
    heading = node  # HeadingNode
    text = heading.text           # 标题文本
    textlines = heading.textlines # TextLine 列表
```

### ParagraphNode（段落节点）

```python
if node.type == "section":
    paragraph = node  # ParagraphNode
    textlines = paragraph.textlines  # TextLine 列表
    text = paragraph.get_text()      # 完整文本
```

### TableNode（表格节点）

```python
if node.type == "table":
    table = node  # TableNode
    table.row_num       # 行数
    table.col_num       # 列数
    table.cells         # Cell 列表（原始数据）
    
    # 按坐标访问（支持合并单元格）
    cell = table.cell_at(row, col) -> Cell | None
    
    # 按行/列获取文本
    row_texts = table.row(i) -> list[str]       # 第 i 行各列文本
    col_texts = table.col(i) -> list[str]       # 第 i 列各行文本
    
    # 按行迭代
    for row_texts in table.iter_rows(start=0, end=None):
        ...  # row_texts: list[str]
    
    # 格式化为文本（喂 LLM 分析表格结构）
    text = table.to_text(max_rows: int | None = None) -> str
```

### FigureNode（图片节点）

```python
if node.type == "figure":
    figure = node  # FigureNode
    filename = figure.filename  # 图片文件名
    title = figure.title        # 图片标题
```

## Cell（表格单元格）

```python
class Cell:
    text: str           # 单元格文本
    row_index: int      # 行索引（从 0 开始）
    col_index: int      # 列索引（从 0 开始）
    row_span: int       # 跨行数
    col_span: int       # 跨列数
    bold: bool          # 是否加粗
    page_number: int    # 页码
    spans: list[Span]   # 文本片段列表
```

## 使用示例

```python
def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any]:
    result = {}
    
    # 示例 1: 获取全文段落，用于 llm_select
    all_texts = document.get_all_texts()
    
    # 示例 2: 按章节标题定位，收集章节内容
    for node in document.iter_nodes(type_filter="title"):
        if "基本信息" in node.get_text():
            content = node.collect_content()  # list[str | TableNode]
            texts = [c for c in content if isinstance(c, str)]
            tables = [c for c in content if isinstance(c, TableNode)]
    
    # 示例 3: 表格结构化访问
    for node in document.iter_nodes(type_filter="table"):
        table = node  # TableNode
        preview = table.to_text(max_rows=5)  # 格式化文本，喂 LLM
        header = table.row(0)                # 表头行
        for row_texts in table.iter_rows(start=1):  # 跳过表头逐行遍历
            print(row_texts)
    
    # 示例 4: 导航节点树
    first_node = document.get_node(1)
    if first_node:
        children = first_node.get_children()
        parent = first_node.get_parent()
    
    return result
```
"""


def _get_structure_code_doc() -> str:
    """获取 structure.py 文档"""
    code = get_structure_code()
    return f"""## code_executor/structure.py

```python
{code}
```
"""


def _get_tools_guide() -> str:
    """获取工具指南"""
    from .tools import create_default_llm_guide
    return f"""## 工具指南

{create_default_llm_guide()}
"""


def get_llm_context() -> str:
    """获取 Document-only 代码上下文文档（给 LLM 看的）。
    
    Returns:
        Markdown 格式的完整文档
    """
    from .tools import has_default_tool
    
    sections = []
    sections.append("# 代码依赖模块文档\n")
    
    # 1. 代码入口签名
    sections.append(_get_tree_signature())
    sections.append(_get_document_api_doc())
    
    # 2. 工具指南（通用）
    if has_default_tool():
        sections.append(_get_tools_guide())
    
    return "\n".join(sections)
