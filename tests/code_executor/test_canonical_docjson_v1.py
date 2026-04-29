from code_executor.document.docjson_adapter import detect_docjson_dialect, normalize_docjson
from code_executor.document.models.document import Document
from code_executor.document.models.nodes import FigureNode, HeadingNode, ParagraphNode, TableNode


def _span(text: str, page_number: int, bbox: list[float] | None = None) -> dict:
    bbox = bbox or [0, 0, 100, 20]
    return {
        "text": text,
        "bold": False,
        "bbox": bbox,
        "page_number": page_number,
    }


def _textline(text: str, page_number: int, bbox: list[float] | None = None) -> dict:
    bbox = bbox or [0, 0, 100, 20]
    return {
        "text": text,
        "bold": False,
        "bbox": bbox,
        "page_number": page_number,
        "spans": [_span(text, page_number, bbox)],
    }


def _cell(
    text: str,
    row_index: int,
    col_index: int,
    page_number: int,
    *,
    row_span: int = 1,
    col_span: int = 1,
) -> dict:
    return {
        "text": text,
        "bold": False,
        "row_index": row_index,
        "col_index": col_index,
        "row_span": row_span,
        "col_span": col_span,
        "bbox": [col_index * 50, row_index * 20, (col_index + 1) * 50, (row_index + 1) * 20],
        "page_number": page_number,
        "spans": [_span(text, page_number)],
    }


CANONICAL_DOCJSON_V1 = {
    "docjson_version": "1.0",
    "doc_meta": {
        "source_format": "fixture",
        "converter": "test",
    },
    "pdf_info": {"producer": "unit-test"},
    "fonts": {"F1": {"name": "TestFont"}},
    "images": {"img1": {"path": "pages/2.png"}},
    "pages": [
        {"number": 1, "bbox": [0, 0, 595, 842], "width": 595, "height": 842},
        {"number": 2, "bbox": [0, 0, 595, 842], "width": 595, "height": 842},
    ],
    "tree": {
        "root": {
            "id": 0,
            "type": "title",
            "page_number": 0,
            "end_page_number": 0,
            "parent_path": [],
            "data": {"text": "", "textlines": []},
            "children": [
                {
                    "id": 1,
                    "type": "title",
                    "page_number": 1,
                    "end_page_number": 2,
                    "parent_path": [],
                    "data": {
                        "text": "第一节 业务概览",
                        "textlines": [_textline("第一节 业务概览", 1)],
                    },
                    "children": [
                        {
                            "id": 2,
                            "type": "section",
                            "page_number": 1,
                            "end_page_number": 1,
                            "parent_path": [1],
                            "data": {
                                "textlines": [
                                    _textline("公司主营业务稳定增长。", 1),
                                    _textline("客户覆盖国内外整车厂。", 1),
                                ]
                            },
                            "children": [],
                            "meta": {
                                "source_object_type": "textbox",
                                "source_page_index": 0,
                                "source_object_index": 1,
                            },
                        },
                        {
                            "id": 3,
                            "type": "table",
                            "page_number": 1,
                            "end_page_number": 1,
                            "parent_path": [1],
                            "data": {
                                "row_num": 2,
                                "col_num": 2,
                                "cells": [
                                    _cell("项目", 0, 0, 1),
                                    _cell("金额", 0, 1, 1),
                                    _cell("营业收入", 1, 0, 1),
                                    _cell("100", 1, 1, 1),
                                ],
                            },
                            "children": [],
                        },
                        {
                            "id": 4,
                            "type": "figure",
                            "page_number": 2,
                            "end_page_number": 2,
                            "parent_path": [1],
                            "data": {
                                "bbox": [10, 10, 200, 150],
                                "filename": "pages/2.png",
                                "title": "业务结构图",
                            },
                            "children": [],
                        },
                        {
                            "id": 5,
                            "type": "table",
                            "page_number": 1,
                            "end_page_number": 2,
                            "parent_path": [1],
                            "data": {
                                "row_num": 4,
                                "col_num": 2,
                                "merged": True,
                                "cells": [
                                    _cell("跨页项目", 0, 0, 1),
                                    _cell("跨页金额", 0, 1, 1),
                                ],
                                "merged_tables": [
                                    {
                                        "row_num": 2,
                                        "col_num": 2,
                                        "page_number": 1,
                                        "bbox": [0, 0, 100, 40],
                                        "cells": [
                                            _cell("跨页项目", 0, 0, 1),
                                            _cell("跨页金额", 0, 1, 1),
                                        ],
                                    },
                                    {
                                        "row_num": 2,
                                        "col_num": 2,
                                        "page_number": 2,
                                        "bbox": [0, 0, 100, 40],
                                        "cells": [
                                            _cell("延续项目", 0, 0, 2),
                                            _cell("200", 0, 1, 2),
                                        ],
                                    },
                                ],
                            },
                            "children": [],
                        },
                    ],
                    "meta": {"source_format": "fixture"},
                }
            ],
        }
    },
}


def test_canonical_docjson_v1_is_detected_as_canonical_tree():
    assert detect_docjson_dialect(CANONICAL_DOCJSON_V1) == "canonical_tree"
    assert normalize_docjson(CANONICAL_DOCJSON_V1) is CANONICAL_DOCJSON_V1


def test_canonical_docjson_v1_document_metadata_and_pages():
    document = Document.from_dict(CANONICAL_DOCJSON_V1)

    assert document.pdf_info == {"producer": "unit-test"}
    assert document.fonts == {"F1": {"name": "TestFont"}}
    assert document.images == {"img1": {"path": "pages/2.png"}}
    assert document.total_pages == 2


def test_canonical_docjson_v1_title_section_and_parent_path():
    document = Document.from_dict(CANONICAL_DOCJSON_V1)

    title = document.get_node(1)
    section = document.get_node(2)

    assert isinstance(title, HeadingNode)
    assert title.get_title() == "第一节 业务概览"
    assert title.parent_path == []

    assert isinstance(section, ParagraphNode)
    assert section.parent_path == [1]
    assert section.get_parent() is title
    assert section.get_text() == "公司主营业务稳定增长。客户覆盖国内外整车厂。"
    assert section.textlines[0].spans[0].text == "公司主营业务稳定增长。"


def test_canonical_docjson_v1_table_shape_and_grid_helpers():
    document = Document.from_dict(CANONICAL_DOCJSON_V1)
    table = document.get_node(3)

    assert isinstance(table, TableNode)
    assert table.row_num == 2
    assert table.col_num == 2
    assert table.cell_at(1, 0).text == "营业收入"
    assert table.row(1) == ["营业收入", "100"]
    assert table.to_text() == "项目 | 金额\n营业收入 | 100"


def test_canonical_docjson_v1_figure_shape():
    document = Document.from_dict(CANONICAL_DOCJSON_V1)
    figure = document.get_node(4)

    assert isinstance(figure, FigureNode)
    assert figure.filename == "pages/2.png"
    assert figure.title == "业务结构图"
    assert figure.get_title() == "业务结构图"
    assert figure.page_number == 2


def test_canonical_docjson_v1_merged_table_creates_virtual_page_nodes():
    document = Document.from_dict(CANONICAL_DOCJSON_V1)
    table = document.get_node(5)

    assert isinstance(table, TableNode)
    assert table.is_merged is True
    assert table.end_page_number == 2
    assert table.merged_page_ids == ["5:p1", "5:p2"]

    page_1_nodes = document.get_nodes_by_page(1)
    page_2_nodes = document.get_nodes_by_page(2)
    assert any(node.id == "5:p1" for node in page_1_nodes)
    assert any(node.id == "5:p2" for node in page_2_nodes)


def test_canonical_docjson_v1_get_all_texts_uses_title_and_section_nodes_only():
    document = Document.from_dict(CANONICAL_DOCJSON_V1)

    assert document.get_all_texts() == [
        "第一节 业务概览",
        "公司主营业务稳定增长。客户覆盖国内外整车厂。",
    ]
