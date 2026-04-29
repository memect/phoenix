"""Document API documentation"""

DOCUMENT_API = """# Document API

## Document 核心方法

```python
from code_executor.document.models.document import Document

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

## Node 核心方法

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

## TableNode 方法

```python
from code_executor.document.models.nodes import HeadingNode, TableNode

node.to_text(max_rows=8)          # 格式化文本（喂 LLM）
node.row(i)                       # 第 i 行各列文本
node.col(i)                       # 第 i 列各行文本
node.cell_at(row, col)            # 获取单元格
node.iter_rows(start, end)        # 按行迭代
node.row_num, node.col_num        # 行列数
```

**TableNode 便利方法速查**：
- `node.to_text(max_rows=8)` → 格式化表格文本，喂 LLM 分析
- `node.row(i)` → 第 i 行各列文本
- `node.col(i)` → 第 i 列各行文本
- `node.cell_at(row, col)` → 获取单元格 Cell 对象
- `node.iter_rows(start, end)` → 按行迭代
- `node.row_num`, `node.col_num` → 行列数
"""
