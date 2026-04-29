import json
from pathlib import Path

import pytest

from code_executor.document.docjson_adapter import detect_docjson_dialect, normalize_docjson
from code_executor.document.models.document import Document
from code_executor.loader import to_plain_article


CANONICAL_DOCJSON = {
    "tree": {
        "root": {
            "id": 0,
            "type": "title",
            "parent_path": [],
            "page_number": 0,
            "data": {"text": "", "textlines": []},
            "children": [
                {
                    "id": 1,
                    "type": "title",
                    "parent_path": [],
                    "page_number": 1,
                    "data": {"text": "Canonical Title"},
                    "children": [],
                }
            ],
        }
    },
    "pages": [{"number": 1, "bbox": [0, 0, 100, 100]}],
}


PPX_DOCJSON = {
    "pages": [
        {
            "number": 1,
            "bbox": [0, 0, 3840, 2160],
            "width": 3840,
            "height": 2160,
            "objects": [
                {"type": "markdown", "bbox": [10, 10, 200, 30], "text": "# Root"},
                {"type": "markdown", "bbox": [10, 40, 300, 60], "text": "Intro text"},
                {"type": "markdown", "bbox": [10, 70, 300, 90], "text": "## Child"},
                {"type": "markdown", "bbox": [10, 100, 300, 120], "text": "Child text"},
                {"type": "markdown", "bbox": [10, 130, 300, 150], "text": "## Sibling"},
                {"type": "markdown", "bbox": [10, 160, 300, 180], "text": "Sibling text"},
                {
                    "type": "table",
                    "bbox": [10, 190, 300, 240],
                    "row_num": 2,
                    "col_num": 2,
                    "cells": [
                        {
                            "row_index": 0,
                            "col_index": 0,
                            "text": "项目",
                            "bbox": [10, 190, 100, 210],
                        },
                        {
                            "row_index": 0,
                            "col_index": 1,
                            "text": "金额",
                            "bbox": [100, 190, 200, 210],
                        },
                        {
                            "row_index": 1,
                            "col_index": 0,
                            "text": "收入",
                            "bbox": [10, 210, 100, 230],
                        },
                        {
                            "row_index": 1,
                            "col_index": 1,
                            "text": "100",
                            "bbox": [100, 210, 200, 230],
                        },
                    ],
                },
                {
                    "type": "figure",
                    "bbox": [10, 250, 300, 320],
                    "filename": "images/1-1.png",
                },
            ],
        }
    ]
}


def test_detect_canonical_tree_docjson():
    assert detect_docjson_dialect(CANONICAL_DOCJSON) == "canonical_tree"
    assert normalize_docjson(CANONICAL_DOCJSON) is CANONICAL_DOCJSON


def test_detect_ppx_pages_objects_docjson():
    assert detect_docjson_dialect(PPX_DOCJSON) == "ppx_pages_objects"


def test_ppx_normalize_restores_markdown_heading_tree():
    normalized = normalize_docjson(PPX_DOCJSON)
    root_children = normalized["tree"]["root"]["children"]

    assert normalized["docjson_version"] == "1.0"
    assert normalized["doc_meta"]["source_format"] == "ppx_pages_objects"
    assert normalized["doc_meta"]["converter"] == "extract-agent"
    assert normalized["pages"][0]["meta"] == {"source_page_index": 0}

    root_heading = root_children[0]
    assert root_heading["type"] == "title"
    assert root_heading["data"]["text"] == "Root"

    intro, child_heading, sibling_heading = root_heading["children"]
    assert intro["type"] == "section"
    assert intro["data"]["textlines"][0]["text"] == "Intro text"
    assert intro["parent_path"] == [root_heading["id"]]

    assert child_heading["type"] == "title"
    assert child_heading["data"]["text"] == "Child"
    assert child_heading["parent_path"] == [root_heading["id"]]
    assert child_heading["children"][0]["data"]["textlines"][0]["text"] == "Child text"
    assert child_heading["end_page_number"] == 1
    assert child_heading["meta"] == {
        "source_object_type": "markdown",
        "source_page_index": 0,
        "source_object_index": 2,
    }

    assert sibling_heading["type"] == "title"
    assert sibling_heading["data"]["text"] == "Sibling"
    assert sibling_heading["parent_path"] == [root_heading["id"]]


def test_ppx_normalize_converts_table_and_figure_nodes():
    document = Document.from_dict(normalize_docjson(PPX_DOCJSON))

    table = next(document.iter_nodes("table"))
    assert table.row_num == 2
    assert table.col_num == 2
    assert table.row(1) == ["收入", "100"]

    figure = next(document.iter_nodes("figure"))
    assert figure.filename == "images/1-1.png"
    assert figure.page_number == 1


def test_ppx_normalize_can_build_document_model():
    document = Document.from_dict(normalize_docjson(PPX_DOCJSON))

    titles = [node.get_title() for node in document.iter_nodes("title") if node.get_title()]
    assert titles == ["Root", "Child", "Sibling"]
    assert document.get_all_texts() == [
        "Root",
        "Intro text",
        "Child",
        "Child text",
        "Sibling",
        "Sibling text",
    ]


def test_document_from_dict_auto_normalizes_ppx_docjson():
    document = Document.from_dict(PPX_DOCJSON)

    root = next(node for node in document.iter_nodes("title") if node.get_title() == "Root")
    assert [child.get_text() for child in root.get_children()] == [
        "Intro text",
        "Child",
        "Sibling",
    ]


def test_to_plain_article_auto_normalizes_ppx_docjson():
    article = to_plain_article(PPX_DOCJSON)
    combined = "\n".join(str(item) for item in article)

    assert "Root" in combined
    assert "Child text" in combined


def test_ppx_real_fixture_restores_who_am_i_section():
    path = Path("/path/to/ppx/doc.json")
    if not path.exists():
        pytest.skip(f"PPX smoke fixture not found: {path}")

    document = Document.from_dict(normalize_docjson(json.loads(path.read_text(encoding="utf-8"))))
    titles = [node for node in document.iter_nodes("title") if node.get_title()]

    assert any(node.get_title() == "Who Am I?" for node in titles)
    who_am_i = next(node for node in titles if node.get_title() == "Who Am I?")
    child_texts = [child.get_text() for child in who_am_i.get_children()]
    assert any("Min-Te Sun" in text for text in child_texts)


def test_unknown_docjson_format_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported DocJSON format"):
        normalize_docjson({"pages": []})
