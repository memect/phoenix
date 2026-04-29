"""文档类定义

实现 Document 类，包含节点树和索引。
"""

from __future__ import annotations

from typing import Any, Iterator

from ..docjson_adapter import normalize_docjson
from .nodes import (
    Node,
    NodeId,
    TableNode,
    create_node_from_dict,
)


class Document:
    """文档的内存表示
    
    包含节点树和多种索引，支持高效的导航和查询操作。
    
    Attributes:
        raw_bytes: 原始 PDF 二进制数据（可选），用于 VLM 工具等需要访问原始文件的场景
    """

    def __init__(self) -> None:
        self.pdf_info: dict[str, Any] = {}
        self.fonts: dict[str, dict[str, Any]] = {}
        self.images: dict[str, dict[str, Any]] = {}
        self.total_pages: int = 0
        self.raw_bytes: bytes | None = None
        
        self._root: Node | None = None
        self._id_to_node: dict[NodeId, Node] = {}
        self._page_to_nodes: dict[int, list[Node]] = {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        """从 doc.json 数据创建 Document"""
        data = normalize_docjson(data)
        doc = cls()
        
        # 解析基础信息
        doc.pdf_info = data.get("pdf_info", {})
        doc.fonts = data.get("fonts", {})
        doc.images = data.get("images", {})
        
        # 计算总页数
        pages = data.get("pages", [])
        doc.total_pages = len(pages)
        
        # 解析节点树
        tree_data = data.get("tree", {})
        root_data = tree_data.get("root", {})
        
        if root_data:
            doc._root = doc._parse_node(root_data)
            doc._build_indices()
        
        return doc

    def _parse_node(self, data: dict[str, Any]) -> Node:
        """递归解析节点及其子节点"""
        node = create_node_from_dict(data, self)
        
        # 递归解析子节点
        children_data = data.get("children", [])
        for child_data in children_data:
            child_node = self._parse_node(child_data)
            child_node._doc = self
            node._children.append(child_node)
        
        return node

    def _build_indices(self) -> None:
        """构建节点索引"""
        self._id_to_node.clear()
        self._page_to_nodes.clear()
        
        if not self._root:
            return
        
        # 遍历所有节点构建索引
        for node in self._iter_all_nodes(self._root):
            self._index_node(node)

    def _index_node(self, node: Node) -> None:
        """将节点添加到索引中"""
        # 添加到 ID 索引
        self._id_to_node[node.id] = node
        
        # 处理跨页表格
        if isinstance(node, TableNode) and node.is_merged and node.original_tables:
            # 合并表格不加入页面索引，只加入 ID 索引
            # 为每个分页创建虚拟节点
            page_ids = []
            for table_data in node.original_tables:
                virtual_node = TableNode.create_virtual_node(node, table_data, self)
                page_ids.append(str(virtual_node.id))
                
                # 虚拟节点加入两个索引
                self._id_to_node[virtual_node.id] = virtual_node
                self._add_to_page_index(virtual_node)
            
            # 更新合并表格的分页 ID 列表
            node.merged_page_ids = page_ids
        else:
            # 普通节点加入页面索引
            self._add_to_page_index(node)

    def _add_to_page_index(self, node: Node) -> None:
        """将节点添加到页面索引"""
        page_num = node.page_number
        if page_num not in self._page_to_nodes:
            self._page_to_nodes[page_num] = []
        self._page_to_nodes[page_num].append(node)

    def _iter_all_nodes(self, node: Node) -> Iterator[Node]:
        """深度优先遍历所有节点"""
        yield node
        for child in node._children:
            yield from self._iter_all_nodes(child)

    def get_node(self, node_id: NodeId) -> Node | None:
        """根据 ID 获取节点"""
        return self._id_to_node.get(node_id)

    def get_nodes_by_page(self, page_num: int) -> list[Node]:
        """获取指定页面的所有节点"""
        return self._page_to_nodes.get(page_num, [])

    def iter_nodes(self, type_filter: str | None = None) -> Iterator[Node]:
        """遍历所有节点
        
        Args:
            type_filter: 可选的类型过滤器，如 "title", "section", "table", "figure"
        """
        if not self._root:
            return
        
        for node in self._iter_all_nodes(self._root):
            if type_filter is None or node.type == type_filter:
                yield node

    def get_all_texts(self, max_items: int | None = None) -> list[str]:
        """获取所有段落文本的 flat list
        
        遍历所有 title 和 section 节点，返回非空文本列表。
        方便快速获取全文段落列表，可直接用于 llm_select。
        
        Args:
            max_items: 最大条目数限制，None 表示全部
            
        Returns:
            文本字符串列表
        """
        texts: list[str] = []
        for node in self.iter_nodes():
            if node.type in ("title", "section"):
                text = node.get_text()
                if text:
                    texts.append(text)
                    if max_items and len(texts) >= max_items:
                        break
        return texts
