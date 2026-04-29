"""基础数据类型定义

实现 BBox, Span, TextLine, Cell, TableData 等基础数据类。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BBox:
    """边界框"""

    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def from_dict(cls, data: list[float] | dict[str, float]) -> BBox:
        """从 JSON 数据解析 BBox
        
        支持两种格式:
        - 列表格式: [x0, y0, x1, y1]
        - 字典格式: {"x0": ..., "y0": ..., "x1": ..., "y1": ...}
        """
        if isinstance(data, list):
            return cls(x0=data[0], y0=data[1], x1=data[2], y1=data[3])
        return cls(
            x0=data["x0"],
            y0=data["y0"],
            x1=data["x1"],
            y1=data["y1"],
        )

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass
class Span:
    """文本片段"""

    text: str
    bold: bool
    bbox: BBox
    page_number: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Span:
        """从 JSON 数据解析 Span"""
        return cls(
            text=data.get("text", ""),
            bold=data.get("bold", False),
            bbox=BBox.from_dict(data["bbox"]) if "bbox" in data else BBox(0, 0, 0, 0),
            page_number=data.get("page_number", 0),
        )


@dataclass
class TextLine:
    """文本行"""

    text: str
    bold: bool
    bbox: BBox
    page_number: int
    spans: list[Span] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextLine:
        """从 JSON 数据解析 TextLine"""
        spans = [Span.from_dict(s) for s in data.get("spans", [])]
        return cls(
            text=data.get("text", ""),
            bold=data.get("bold", False),
            bbox=BBox.from_dict(data["bbox"]) if "bbox" in data else BBox(0, 0, 0, 0),
            page_number=data.get("page_number", 0),
            spans=spans,
        )


@dataclass
class Cell:
    """表格单元格"""

    text: str
    bold: bool
    row_index: int
    col_index: int
    row_span: int
    col_span: int
    bbox: BBox
    page_number: int
    spans: list[Span] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cell:
        """从 JSON 数据解析 Cell"""
        spans = [Span.from_dict(s) for s in data.get("spans", [])]
        
        # 优先使用 data 中的 page_number，否则从 spans 中推断
        page_number = data.get("page_number", 0)
        if not page_number and spans:
            page_number = spans[0].page_number
        
        return cls(
            text=data.get("text", ""),
            bold=data.get("bold", False),
            row_index=data.get("row_index", 0),
            col_index=data.get("col_index", 0),
            row_span=data.get("row_span", 1),
            col_span=data.get("col_span", 1),
            bbox=BBox.from_dict(data["bbox"]) if "bbox" in data else BBox(0, 0, 0, 0),
            page_number=page_number,
            spans=spans,
        )


@dataclass
class TableData:
    """表格数据（用于跨页表格的单页部分）"""

    row_num: int
    col_num: int
    cells: list[Cell]
    page_number: int
    bbox: BBox | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableData:
        """从 JSON 数据解析 TableData"""
        cells = [Cell.from_dict(c) for c in data.get("cells", [])]
        # 从 cells 中推断 page_number
        page_number = data.get("page_number", 0)
        if not page_number and cells:
            page_number = cells[0].page_number
        
        bbox = None
        if "bbox" in data:
            bbox = BBox.from_dict(data["bbox"])
        
        return cls(
            row_num=data.get("row_num", 0),
            col_num=data.get("col_num", 0),
            cells=cells,
            page_number=page_number,
            bbox=bbox,
        )
