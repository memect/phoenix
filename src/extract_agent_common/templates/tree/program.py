from typing import Any
from code_executor.document.models import Document, HeadingNode, ParagraphNode, TableNode
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any] | list[dict[str, Any]]:
    """从文档树中提取结构化数据
    
    Args:
        document: 文档对象，包含完整的节点树
        tool_hub: xdev 自动注入的工具中心，可获取 extract / llm_select 等工具
    
    Returns:
        提取的结构化数据（字典或字典列表）
    """
    result = {}
    
    # === 示例 1: 遍历所有章节标题 ===
    sections = []
    for heading in document.iter_nodes(type_filter="title"):
        if isinstance(heading, HeadingNode):
            sections.append({
                "title": heading.text,
                "level": heading.level,
                "page": heading.page_number,
            })
    result["sections"] = sections
    
    # === 示例 2: 访问文档根节点，递归处理子节点 ===
    if document._root:
        # 获取根节点的直接子节点
        root_children = document._root.get_children()
        result["root_child_count"] = len(root_children)
        
        # 处理第一个章节（如果存在）
        if root_children:
            first_section = root_children[0]
            if isinstance(first_section, HeadingNode):
                result["first_section_title"] = first_section.text
                
                # 获取该章节的段落子节点
                paragraphs = []
                for child in first_section.get_children():
                    if isinstance(child, ParagraphNode):
                        paragraphs.append(child.get_text())
                result["first_section_paragraphs"] = paragraphs
    
    # === 示例 3: 处理表格 ===
    tables = []
    for table_node in document.iter_nodes(type_filter="table"):
        if isinstance(table_node, TableNode):
            # 跳过虚拟分页节点，只处理完整表格
            if table_node.is_merged_part:
                continue
            
            # 提取表格数据
            table_data = {
                "page": table_node.page_number,
                "size": f"{table_node.row_num}x{table_node.col_num}",
                "is_merged": table_node.is_merged,
                "rows": [],
            }
            
            # 按行组织单元格
            for row_idx in range(table_node.row_num):
                row_cells = [
                    cell.text 
                    for cell in table_node.cells 
                    if cell.row_index == row_idx
                ]
                table_data["rows"].append(row_cells)
            
            tables.append(table_data)
    
    result["tables"] = tables
    
    # === 示例 4: 使用父子关系导航 ===
    # 找到某个节点的父节点和兄弟节点
    for node in document.iter_nodes():
        if isinstance(node, TableNode):
            parent = node.get_parent()
            if parent:
                result["example_table_parent"] = {
                    "table_page": node.page_number,
                    "parent_type": parent.type,
                    "parent_title": parent.get_title(),
                }
            
            # 获取兄弟节点
            siblings = node.get_siblings()
            result["example_table_siblings_count"] = len(siblings)
            break
    
    # === 示例 5: 按页面查询 ===
    # 获取第 1 页的所有节点
    page_1_nodes = document.get_nodes_by_page(1)
    result["page_1_node_count"] = len(page_1_nodes)
    result["page_1_node_types"] = [node.type for node in page_1_nodes]
    
    return result
