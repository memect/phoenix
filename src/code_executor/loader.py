"""
DocJSON 加载和转换模块

提供将 DocJSON 格式转换为纯文本文章的功能。
"""

import numpy
from .structure import Table, Cell
from typing import Any, Union
from itertools import product
import logging

from .document.docjson_adapter import normalize_docjson

logger = logging.getLogger(__name__)


def to_plain_article(json_data: dict) -> list[str | Table]:
    """将 DocJSON 转换为纯文本文章格式
    
    Args:
        json_data: DocJSON 格式的文档数据
        
    Returns:
        包含字符串和 Table 对象的列表
    """
    normalized = normalize_docjson(json_data)
    if "tree" in normalized and "root" in normalized["tree"]:
        return _to_plain_article(normalized["tree"]["root"])
    else:
        return []


def _to_plain_article(node: dict[str, Any]) -> list[Union[str, Table]]:
    """递归处理 DocJSON 节点
    
    Args:
        node: DocJSON 树节点
        
    Returns:
        包含字符串和 Table 对象的列表
    """
    result: list[Union[str, Table]] = []

    # 处理当前节点的数据
    if node.get("type") == "title":
        if "data" in node and node["data"] is not None and "text" in node["data"] and node["data"]["text"]:
            result.append(node["data"]["text"])

    elif node.get("type") == "section":
        section_text = []
        if "data" in node and node["data"] is not None and "textlines" in node["data"]:
            for textline in node["data"]["textlines"]:
                if "text" in textline:
                    section_text.append(textline['text'])
        if section_text:
            result.append("\n".join(section_text))

    elif node.get("type") == "table":
        if "data" in node and node["data"] is not None and "cells" in node["data"]:
            cells_data = node["data"]["cells"]
            row_num = node["data"].get("row_num", 0)
            col_num = node["data"].get("col_num", 0)

            # A more direct way to build the table with spans.
            # The `table_data` for the Table object should be a list of lists,
            # where each inner list represents a row, and cells covered by spans
            # are omitted.
            final_table = numpy.full((row_num, col_num), None, dtype=object)
            # Sort cells by row and column to ensure correct processing order.
            sorted_cells = sorted(cells_data, key=lambda c: (c['row_index'], c['col_index']))

            for cell_info in sorted_cells:
                r = cell_info['row_index']
                c = cell_info['col_index']
                row_span = cell_info.get('row_span', 1)
                col_span = cell_info.get('col_span', 1)
                if r < row_num:
                    cell = Cell(
                        row_index=r,
                        col_index=c,
                        text=cell_info.get('text', ''),
                        row_span=row_span,
                        col_span=col_span
                    )
                for r_offset, c_offset in product(range(row_span), range(col_span)):
                    final_table[r + r_offset, c + c_offset] = cell

            result.append(Table(table_data=final_table, row_num=row_num, col_num=col_num))

    # 递归处理子节点
    if "children" in node and node["children"]:
        for child in node["children"]:
            result.extend(_to_plain_article(child))

    return result
