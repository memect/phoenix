"""节点类型定义

实现 Node 基类和具体节点类型：HeadingNode, ParagraphNode, TableNode, FigureNode
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from .base import BBox, Cell, TableData, TextLine

if TYPE_CHECKING:
    from .document import Document

# NodeId 类型：整数为原始 ID，字符串如 "52:p9" 为跨页表格分页 ID
NodeId = int | str


@dataclass
class Node:
    """节点基类
    
    文档中的语义单元，包含导航和内容访问方法。
    """

    id: NodeId
    type: str
    page_number: int
    end_page_number: int
    parent_path: list[int] = field(default_factory=list)
    _children: list[Node] = field(default_factory=list, repr=False)
    _doc: Document | None = field(default=None, repr=False)

    @property
    def level(self) -> int:
        """返回节点在树中的深度（根节点的子节点为 level 1）"""
        return len(self.parent_path) + 1

    def get_parent(self) -> Node | None:
        """获取父节点"""
        if not self._doc or not self.parent_path:
            return None
        parent_id = self.parent_path[-1]
        return self._doc.get_node(parent_id)

    def get_siblings(self) -> list[Node]:
        """获取兄弟节点（包括自己）"""
        parent = self.get_parent()
        if parent:
            return parent.get_children()
        # 如果没有父节点，返回根节点的子节点
        if self._doc and self._doc._root:
            return self._doc._root.get_children()
        return [self]

    def get_ancestors(self) -> list[Node]:
        """获取祖先节点列表（从根到父）"""
        if not self._doc:
            return []
        ancestors = []
        for ancestor_id in self.parent_path:
            ancestor = self._doc.get_node(ancestor_id)
            if ancestor:
                ancestors.append(ancestor)
        return ancestors

    def get_children(self) -> list[Node]:
        """获取子节点列表"""
        return self._children

    def get_title(self) -> str:
        """获取节点标题（用于大纲显示）"""
        # 子类可以覆盖此方法
        return ""

    def get_text(self) -> str:
        """获取节点的完整文本内容"""
        # 子类可以覆盖此方法
        return ""

    def get_searchable_text(self) -> str:
        """获取可搜索的文本（用于搜索功能）"""
        # 默认返回标题和文本的组合
        title = self.get_title()
        text = self.get_text()
        if title and text:
            return f"{title}\n{text}"
        return title or text

    def collect_content(self) -> list[str | TableNode]:
        """递归收集后代节点内容
        
        ParagraphNode/HeadingNode 返回文本字符串，TableNode 保留节点对象。
        用于章节级内容收集后交给 llm_select 做段落筛选。
        
        Returns:
            内容列表，元素为文本字符串或 TableNode 对象
        """
        result: list[str | TableNode] = []
        for child in self._children:
            if isinstance(child, TableNode):
                result.append(child)
            else:
                text = child.get_text()
                if text:
                    result.append(text)
            # 递归收集子节点的内容
            result.extend(child.collect_content())
        return result



@dataclass
class HeadingNode(Node):
    """章节标题节点（JSON type="title"）
    
    同时代表整个章节。
    """

    text: str = ""
    textlines: list[TextLine] = field(default_factory=list)

    def get_title(self) -> str:
        return self.text

    def get_text(self) -> str:
        return self.text

    def get_searchable_text(self) -> str:
        # 标题节点的 title 和 text 相同，只返回一次
        return self.text

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], doc: Document | None = None
    ) -> HeadingNode:
        """从 JSON 数据解析 HeadingNode"""
        node_data = data.get("data", {}) or {}
        textlines = [TextLine.from_dict(tl) for tl in node_data.get("textlines", [])]
        text = node_data.get("text", "")
        
        # 如果没有 text 字段，从 textlines 拼接
        if not text and textlines:
            text = "".join(tl.text for tl in textlines)
        
        page_number = data.get("page_number", 0)
        # end_page_number 可能不存在，默认等于 page_number
        end_page_number = data.get("end_page_number", page_number)
        
        return cls(
            id=data.get("id", 0),
            type=data.get("type", "title"),
            page_number=page_number,
            end_page_number=end_page_number,
            parent_path=data.get("parent_path", []),
            text=text,
            textlines=textlines,
            _doc=doc,
        )


@dataclass
class ParagraphNode(Node):
    """段落节点（JSON type="section"）"""

    textlines: list[TextLine] = field(default_factory=list)

    def get_title(self) -> str:
        # 段落没有标题，返回前 50 个字符作为预览
        text = self.get_text()
        if len(text) > 50:
            return text[:50] + "..."
        return text

    def get_text(self) -> str:
        return "".join(tl.text for tl in self.textlines)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], doc: Document | None = None
    ) -> ParagraphNode:
        """从 JSON 数据解析 ParagraphNode"""
        node_data = data.get("data", {}) or {}
        textlines = [TextLine.from_dict(tl) for tl in node_data.get("textlines", [])]
        
        page_number = data.get("page_number", 0)
        end_page_number = data.get("end_page_number", page_number)
        
        return cls(
            id=data.get("id", 0),
            type=data.get("type", "section"),
            page_number=page_number,
            end_page_number=end_page_number,
            parent_path=data.get("parent_path", []),
            textlines=textlines,
            _doc=doc,
        )



@dataclass
class TableNode(Node):
    """表格节点（JSON type="table"）
    
    支持跨页表格，包含合并表格属性。
    """

    row_num: int = 0
    col_num: int = 0
    cells: list[Cell] = field(default_factory=list)
    # 跨页表格属性
    is_merged: bool = False  # 是否是合并后的完整表格
    is_merged_part: bool = False  # 是否是跨页表格的分页部分（虚拟节点）
    merged_parent_id: int | None = None  # 虚拟节点指向的原始表格 ID
    merged_page_ids: list[str] | None = None  # 合并表格的各分页虚拟节点 ID
    original_tables: list[TableData] | None = None  # 跨页表格的原始分页数据

    def get_title(self) -> str:
        # 表格没有标题，返回表格大小信息
        if self.is_merged_part:
            return f"表格 (第 {self.page_number} 页部分)"
        if self.is_merged:
            return f"跨页表格 ({self.row_num}×{self.col_num})"
        return f"表格 ({self.row_num}×{self.col_num})"

    def get_text(self) -> str:
        # 返回所有单元格文本
        return " ".join(cell.text for cell in self.cells if cell.text)

    def get_searchable_text(self) -> str:
        # 表格搜索时返回所有单元格文本
        return self.get_text()

    # ---- 二维索引（延迟构建，缓存） ----

    def _ensure_grid(self) -> None:
        """构建行列二维索引（首次访问时触发）"""
        if hasattr(self, '_grid'):
            return
        grid: dict[tuple[int, int], Cell] = {}
        for cell in self.cells:
            grid[(cell.row_index, cell.col_index)] = cell
            # 处理合并单元格：填充所有覆盖的位置
            for dr in range(cell.row_span):
                for dc in range(cell.col_span):
                    grid[(cell.row_index + dr, cell.col_index + dc)] = cell
        self._grid = grid

    def cell_at(self, row: int, col: int) -> Cell | None:
        """按行列坐标获取单元格
        
        Args:
            row: 行号（从 0 开始）
            col: 列号（从 0 开始）
            
        Returns:
            Cell 对象，不存在则返回 None
        """
        self._ensure_grid()
        return self._grid.get((row, col))

    def row(self, i: int) -> list[str]:
        """获取第 i 行所有单元格文本
        
        Args:
            i: 行号（从 0 开始）
            
        Returns:
            该行各列的文本列表
        """
        self._ensure_grid()
        return [self._grid[(i, c)].text if (i, c) in self._grid else "" for c in range(self.col_num)]

    def col(self, i: int) -> list[str]:
        """获取第 i 列所有单元格文本
        
        Args:
            i: 列号（从 0 开始）
            
        Returns:
            该列各行的文本列表
        """
        self._ensure_grid()
        return [self._grid[(r, i)].text if (r, i) in self._grid else "" for r in range(self.row_num)]

    def iter_rows(self, start: int = 0, end: int | None = None) -> Iterator[list[str]]:
        """按行迭代表格内容
        
        Args:
            start: 起始行号（默认 0）
            end: 结束行号（不含，默认到末尾）
            
        Yields:
            每行各列的文本列表
        """
        if end is None:
            end = self.row_num
        for i in range(start, min(end, self.row_num)):
            yield self.row(i)

    def to_text(self, max_rows: int | None = None) -> str:
        """格式化为表格文本，用于喂给 LLM 分析
        
        Args:
            max_rows: 最大行数限制，None 表示全部
            
        Returns:
            用 | 分隔的表格文本
        """
        rows_end = min(max_rows, self.row_num) if max_rows else self.row_num
        lines = []
        for row_texts in self.iter_rows(0, rows_end):
            lines.append(" | ".join(row_texts))
        if max_rows and max_rows < self.row_num:
            lines.append(f"... (共 {self.row_num} 行，仅显示前 {max_rows} 行)")
        return "\n".join(lines)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], doc: Document | None = None
    ) -> TableNode:
        """从 JSON 数据解析 TableNode"""
        node_data = data.get("data", {}) or {}
        cells = [Cell.from_dict(c) for c in node_data.get("cells", [])]
        
        page_number = data.get("page_number", 0)
        end_page_number = data.get("end_page_number", page_number)
        
        # 检查是否是跨页表格
        is_merged = node_data.get("merged", False)
        merged_tables_data = node_data.get("merged_tables", [])
        
        original_tables = None
        if is_merged and merged_tables_data:
            original_tables = [TableData.from_dict(mt) for mt in merged_tables_data]
            # 更新 end_page_number 为最后一页
            if original_tables:
                end_page_number = max(t.page_number for t in original_tables)
        
        return cls(
            id=data.get("id", 0),
            type=data.get("type", "table"),
            page_number=page_number,
            end_page_number=end_page_number,
            parent_path=data.get("parent_path", []),
            row_num=node_data.get("row_num", 0),
            col_num=node_data.get("col_num", 0),
            cells=cells,
            is_merged=is_merged,
            is_merged_part=False,
            merged_parent_id=None,
            merged_page_ids=None,
            original_tables=original_tables,
            _doc=doc,
        )

    @classmethod
    def create_virtual_node(
        cls,
        parent_table: TableNode,
        table_data: TableData,
        doc: Document | None = None,
    ) -> TableNode:
        """创建跨页表格的虚拟分页节点"""
        virtual_id = f"{parent_table.id}:p{table_data.page_number}"
        return cls(
            id=virtual_id,
            type="table",
            page_number=table_data.page_number,
            end_page_number=table_data.page_number,
            parent_path=parent_table.parent_path,
            row_num=table_data.row_num,
            col_num=table_data.col_num,
            cells=table_data.cells,
            is_merged=False,
            is_merged_part=True,
            merged_parent_id=parent_table.id if isinstance(parent_table.id, int) else None,
            merged_page_ids=None,
            original_tables=None,
            _doc=doc,
        )



@dataclass
class FigureNode(Node):
    """图片节点（JSON type="figure"）"""

    bbox: BBox | None = None
    filename: str = ""
    title: str | None = None

    def get_title(self) -> str:
        if self.title:
            return self.title
        return f"图片: {self.filename}"

    def get_text(self) -> str:
        return self.title or ""

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], doc: Document | None = None
    ) -> FigureNode:
        """从 JSON 数据解析 FigureNode"""
        node_data = data.get("data", {}) or {}
        
        bbox = None
        if "bbox" in node_data:
            bbox = BBox.from_dict(node_data["bbox"])
        
        page_number = data.get("page_number", 0)
        end_page_number = data.get("end_page_number", page_number)
        
        return cls(
            id=data.get("id", 0),
            type=data.get("type", "figure"),
            page_number=page_number,
            end_page_number=end_page_number,
            parent_path=data.get("parent_path", []),
            bbox=bbox,
            filename=node_data.get("filename", ""),
            title=node_data.get("title"),
            _doc=doc,
        )


def create_node_from_dict(
    data: dict[str, Any], doc: Document | None = None
) -> Node:
    """根据 type 字段创建对应的节点类型"""
    node_type = data.get("type", "")
    
    if node_type == "title":
        return HeadingNode.from_dict(data, doc)
    elif node_type == "section":
        return ParagraphNode.from_dict(data, doc)
    elif node_type == "table":
        return TableNode.from_dict(data, doc)
    elif node_type == "figure":
        return FigureNode.from_dict(data, doc)
    else:
        # 未知类型，创建基础 Node
        page_number = data.get("page_number", 0)
        return Node(
            id=data.get("id", 0),
            type=node_type,
            page_number=page_number,
            end_page_number=data.get("end_page_number", page_number),
            parent_path=data.get("parent_path", []),
            _doc=doc,
        )
