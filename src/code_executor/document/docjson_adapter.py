"""DocJSON dialect detection and normalization."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Literal

DocjsonDialect = Literal["canonical_tree", "ppx_pages_objects"]
CANONICAL_DOCJSON_VERSION = "1.0"

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


def detect_docjson_dialect(data: dict[str, Any]) -> DocjsonDialect:
    """Detect the supported DocJSON dialect for a document payload."""
    if _is_canonical_tree_docjson(data):
        return "canonical_tree"
    if _is_ppx_pages_objects_docjson(data):
        return "ppx_pages_objects"
    raise ValueError(
        "Unsupported DocJSON format: expected canonical tree DocJSON with "
        "`tree.root`, or PPX DocJSON with `pages[].objects[]`."
    )


def normalize_docjson(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize supported DocJSON dialects to canonical tree DocJSON."""
    dialect = detect_docjson_dialect(data)
    if dialect == "canonical_tree":
        return data
    return _ppx_to_canonical_tree(data)


def _is_canonical_tree_docjson(data: dict[str, Any]) -> bool:
    tree = data.get("tree")
    return isinstance(tree, dict) and isinstance(tree.get("root"), dict)


def _is_ppx_pages_objects_docjson(data: dict[str, Any]) -> bool:
    pages = data.get("pages")
    if not isinstance(pages, list):
        return False
    return any(isinstance(page, dict) and isinstance(page.get("objects"), list) for page in pages)


def _ppx_to_canonical_tree(data: dict[str, Any]) -> dict[str, Any]:
    pages = data.get("pages", [])
    root = {
        "id": 0,
        "type": "title",
        "parent_path": [],
        "page_number": 0,
        "end_page_number": 0,
        "data": {"text": "", "textlines": []},
        "children": [],
        "meta": {},
    }
    normalized: dict[str, Any] = {
        "docjson_version": CANONICAL_DOCJSON_VERSION,
        "doc_meta": _make_doc_meta(data),
        "pdf_info": _copy_mapping(data.get("pdf_info")),
        "fonts": _copy_mapping(data.get("fonts")),
        "images": _copy_mapping(data.get("images")),
        "pages": [
            _normalize_ppx_page(page, page_index)
            for page_index, page in enumerate(pages)
            if isinstance(page, dict)
        ],
        "tree": {"root": root},
    }

    next_id = 1
    heading_stack: list[tuple[int, dict[str, Any]]] = []

    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        page_number = _coerce_page_number(page.get("number"), default=page_index + 1)
        for object_index, obj in enumerate(page.get("objects", [])):
            if not isinstance(obj, dict):
                continue
            parent = heading_stack[-1][1] if heading_stack else root

            if _is_ppx_table(obj):
                node = _make_table_node(next_id, page_number, obj, parent, page_index, object_index)
                parent["children"].append(node)
                next_id += 1
                continue

            if _is_ppx_figure(obj):
                node = _make_figure_node(next_id, page_number, obj, parent, page_index, object_index)
                parent["children"].append(node)
                next_id += 1
                continue

            text = str(obj.get("text") or "").strip()
            if text:
                heading = _parse_markdown_heading(text)
                if heading is not None:
                    level, title = heading
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    parent = heading_stack[-1][1] if heading_stack else root
                    node = _make_title_node(
                        next_id,
                        title,
                        page_number,
                        obj,
                        parent,
                        page_index,
                        object_index,
                    )
                    parent["children"].append(node)
                    heading_stack.append((level, node))
                else:
                    node = _make_section_node(
                        next_id,
                        text,
                        page_number,
                        obj,
                        parent,
                        page_index,
                        object_index,
                    )
                    parent["children"].append(node)
                next_id += 1

    _refresh_end_page_numbers(root)
    root["end_page_number"] = 0

    return normalized


def _make_doc_meta(data: dict[str, Any]) -> dict[str, Any]:
    doc_meta = _copy_mapping(data.get("doc_meta"))
    doc_meta.setdefault("source_format", "ppx_pages_objects")
    doc_meta.setdefault("source_tool", "ppx")
    doc_meta.setdefault("converter", "extract-agent")
    return doc_meta


def _copy_mapping(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _normalize_ppx_page(page: dict[str, Any], page_index: int) -> dict[str, Any]:
    page_number = _coerce_page_number(page.get("number"), default=page_index + 1)
    width = page.get("width", 0)
    height = page.get("height", 0)
    bbox = _coerce_bbox(page.get("bbox"), fallback=[0, 0, width or 0, height or 0])
    return {
        "number": page_number,
        "bbox": bbox,
        "width": width,
        "height": height,
        "meta": {"source_page_index": page_index},
    }


def _parse_markdown_heading(text: str) -> tuple[int, str] | None:
    match = _HEADING_RE.match(text)
    if match is None:
        return None
    title = match.group(2).strip()
    return len(match.group(1)), title


def _make_title_node(
    node_id: int,
    text: str,
    page_number: int,
    obj: dict[str, Any],
    parent: dict[str, Any],
    page_index: int,
    object_index: int,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "title",
        "parent_path": _child_parent_path(parent),
        "page_number": page_number,
        "end_page_number": page_number,
        "data": {
            "text": text,
            "textlines": [_make_single_textline(text, page_number, obj)],
            "target": None,
            "no": None,
        },
        "children": [],
        "meta": _make_node_meta(obj, page_index, object_index),
    }


def _make_section_node(
    node_id: int,
    text: str,
    page_number: int,
    obj: dict[str, Any],
    parent: dict[str, Any],
    page_index: int,
    object_index: int,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "section",
        "parent_path": _child_parent_path(parent),
        "page_number": page_number,
        "end_page_number": page_number,
        "data": {"textlines": _make_textlines(text, page_number, obj)},
        "children": [],
        "meta": _make_node_meta(obj, page_index, object_index),
    }


def _make_table_node(
    node_id: int,
    page_number: int,
    obj: dict[str, Any],
    parent: dict[str, Any],
    page_index: int,
    object_index: int,
) -> dict[str, Any]:
    cells = [
        _make_cell(cell, page_number)
        for cell in obj.get("cells", [])
        if isinstance(cell, dict)
    ]
    row_num = _coerce_positive_int(obj.get("row_num"), default=_infer_row_num(cells))
    col_num = _coerce_positive_int(obj.get("col_num"), default=_infer_col_num(cells))
    return {
        "id": node_id,
        "type": "table",
        "parent_path": _child_parent_path(parent),
        "page_number": page_number,
        "end_page_number": page_number,
        "data": {
            "row_num": row_num,
            "col_num": col_num,
            "cells": cells,
            "bbox": _coerce_bbox(obj.get("bbox")),
        },
        "children": [],
        "meta": _make_node_meta(obj, page_index, object_index),
    }


def _make_figure_node(
    node_id: int,
    page_number: int,
    obj: dict[str, Any],
    parent: dict[str, Any],
    page_index: int,
    object_index: int,
) -> dict[str, Any]:
    title = str(obj.get("text") or "").strip() or None
    return {
        "id": node_id,
        "type": "figure",
        "parent_path": _child_parent_path(parent),
        "page_number": page_number,
        "end_page_number": page_number,
        "data": {
            "bbox": _coerce_bbox(obj.get("bbox")),
            "filename": str(obj.get("filename") or ""),
            "title": title,
        },
        "children": [],
        "meta": _make_node_meta(obj, page_index, object_index),
    }


def _make_node_meta(obj: dict[str, Any], page_index: int, object_index: int) -> dict[str, Any]:
    return {
        "source_object_type": obj.get("type"),
        "source_page_index": page_index,
        "source_object_index": object_index,
    }


def _make_textlines(text: str, page_number: int, obj: dict[str, Any]) -> list[dict[str, Any]]:
    lines = obj.get("lines")
    if not isinstance(lines, list):
        return [_make_single_textline(text, page_number, obj)]

    textlines = [
        _make_textline_from_ppx_line(line, page_number)
        for line in lines
        if isinstance(line, dict)
    ]
    textlines = [line for line in textlines if line["text"]]
    return textlines or [_make_single_textline(text, page_number, obj)]


def _make_textline_from_ppx_line(line: dict[str, Any], page_number: int) -> dict[str, Any]:
    text = str(line.get("text") or "")
    bbox = _coerce_bbox(line.get("bbox"))
    spans = _make_spans_from_ppx_objects(line.get("objects"), text, bbox, page_number)
    return {
        "bbox": bbox,
        "page_number": page_number,
        "text": text,
        "bold": bool(line.get("bold", False) or any(span["bold"] for span in spans)),
        "spans": spans,
    }


def _make_single_textline(text: str, page_number: int, obj: dict[str, Any]) -> dict[str, Any]:
    bbox = _coerce_bbox(obj.get("bbox"))
    return {
        "bbox": bbox,
        "page_number": page_number,
        "text": text,
        "bold": False,
        "spans": [
            {
                "bbox": bbox,
                "page_number": page_number,
                "text": text,
                "bold": False,
            }
        ],
    }


def _make_spans_from_ppx_objects(
    objects: Any,
    fallback_text: str,
    fallback_bbox: list[Any],
    page_number: int,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    if isinstance(objects, list):
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            text = str(obj.get("text") or "")
            if not text:
                continue
            spans.append(
                {
                    "bbox": _coerce_bbox(obj.get("bbox"), fallback=fallback_bbox),
                    "page_number": page_number,
                    "text": text,
                    "bold": bool(obj.get("bold", False)),
                }
            )

    if spans:
        return spans
    return [
        {
            "bbox": fallback_bbox,
            "page_number": page_number,
            "text": fallback_text,
            "bold": False,
        }
    ]


def _make_cell(cell: dict[str, Any], page_number: int) -> dict[str, Any]:
    text = str(cell.get("text") or "")
    bbox = _coerce_bbox(cell.get("bbox"))
    spans = _make_cell_spans(cell, text, bbox, page_number)
    return {
        "text": text,
        "bold": bool(cell.get("bold", False) or any(span["bold"] for span in spans)),
        "row_index": _coerce_nonnegative_int(cell.get("row_index")),
        "col_index": _coerce_nonnegative_int(cell.get("col_index")),
        "row_span": _coerce_positive_int(cell.get("row_span"), default=1),
        "col_span": _coerce_positive_int(cell.get("col_span"), default=1),
        "bbox": bbox,
        "page_number": page_number,
        "spans": spans,
    }


def _make_cell_spans(
    cell: dict[str, Any],
    fallback_text: str,
    fallback_bbox: list[Any],
    page_number: int,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for obj in cell.get("objects", []) if isinstance(cell.get("objects"), list) else []:
        if not isinstance(obj, dict):
            continue
        lines = obj.get("lines")
        if isinstance(lines, list):
            for line in lines:
                if not isinstance(line, dict):
                    continue
                spans.extend(
                    _make_spans_from_ppx_objects(
                        line.get("objects"),
                        str(line.get("text") or ""),
                        _coerce_bbox(line.get("bbox"), fallback=fallback_bbox),
                        page_number,
                    )
                )
        else:
            spans.extend(
                _make_spans_from_ppx_objects(
                    obj.get("objects"),
                    str(obj.get("text") or ""),
                    _coerce_bbox(obj.get("bbox"), fallback=fallback_bbox),
                    page_number,
                )
            )

    if spans:
        return spans
    return [
        {
            "bbox": fallback_bbox,
            "page_number": page_number,
            "text": fallback_text,
            "bold": False,
        }
    ]


def _infer_row_num(cells: list[dict[str, Any]]) -> int:
    if not cells:
        return 0
    return max(cell["row_index"] + cell["row_span"] for cell in cells)


def _infer_col_num(cells: list[dict[str, Any]]) -> int:
    if not cells:
        return 0
    return max(cell["col_index"] + cell["col_span"] for cell in cells)


def _is_ppx_table(obj: dict[str, Any]) -> bool:
    return obj.get("type") == "table" or isinstance(obj.get("cells"), list)


def _is_ppx_figure(obj: dict[str, Any]) -> bool:
    return obj.get("type") == "figure" or "filename" in obj


def _child_parent_path(parent: dict[str, Any]) -> list[int]:
    parent_id = parent.get("id", 0)
    if parent_id == 0:
        return []
    return [*parent.get("parent_path", []), parent_id]


def _refresh_end_page_numbers(node: dict[str, Any]) -> int:
    end_page_number = _coerce_page_number(node.get("page_number"))
    for child in node.get("children", []):
        if isinstance(child, dict):
            end_page_number = max(end_page_number, _refresh_end_page_numbers(child))
    node["end_page_number"] = end_page_number
    return end_page_number


def _coerce_page_number(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_nonnegative_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _coerce_positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _coerce_bbox(value: Any, *, fallback: list[Any] | None = None) -> list[Any]:
    if _is_bbox(value):
        return list(value)
    return list(fallback) if fallback is not None else [0, 0, 0, 0]


def _is_bbox(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 4
