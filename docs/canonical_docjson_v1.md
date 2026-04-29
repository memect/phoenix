# Canonical DocJSON v1

Status: draft
Audience: maintainers
Last verified: 2026-04-28
Source of truth:
- `src/code_executor/document/models/document.py`
- `src/code_executor/document/models/nodes.py`
- `src/code_executor/document/models/base.py`
- `pdf_ai_explorer` 0.1.1 wheel models

This document defines the first repository-local Canonical DocJSON format.
All parser-specific formats, including PPX `pages[].objects[]`, should be
converted to this format before being stored in `.xdev/data/docjson/`.

## Goals

- Keep one stable stored DocJSON shape for `xdev`, `code_executor`, and `pdf-ai-explorer`.
- Make adapters responsible for converting external parser output into Canonical DocJSON.
- Preserve enough source metadata for debugging without requiring downstream tools to understand the source parser.

## Top-Level Object

Canonical DocJSON is a JSON object with these fields:

```json
{
  "docjson_version": "1.0",
  "doc_meta": {},
  "pdf_info": {},
  "fonts": {},
  "images": {},
  "pages": [],
  "tree": {
    "root": {}
  }
}
```

Required for runtime parsing:

- `tree.root`
- `pages`

Recommended for persisted files:

- `docjson_version`
- `doc_meta`
- `pdf_info`
- `fonts`
- `images`

Current `Document` runtime reads `pdf_info`, `fonts`, `images`, `pages`, and `tree.root`. It ignores `docjson_version` and `doc_meta`, but adapters should still write them for provenance and future compatibility.

## Pages

Each page entry should contain:

```json
{
  "number": 1,
  "bbox": [0, 0, 595, 842],
  "width": 595,
  "height": 842,
  "meta": {}
}
```

Required:

- `number`
- `bbox`

Recommended:

- `width`
- `height`
- `meta`

The runtime currently uses `pages` to calculate `Document.total_pages`. Page lookup is driven by node `page_number`, not by the page list itself.

## Node Tree

The tree starts at `tree.root`. The root node is a structural container:

```json
{
  "id": 0,
  "type": "title",
  "page_number": 0,
  "end_page_number": 0,
  "parent_path": [],
  "data": {
    "text": "",
    "textlines": []
  },
  "children": [],
  "meta": {}
}
```

Each node has these common fields:

```json
{
  "id": 1,
  "type": "title",
  "page_number": 1,
  "end_page_number": 1,
  "parent_path": [],
  "data": {},
  "children": [],
  "meta": {}
}
```

Required:

- `id`
- `type`
- `page_number`
- `parent_path`
- `data`
- `children`

Recommended:

- `end_page_number`
- `meta`

`parent_path` is the list of ancestor node IDs excluding root id `0`. A root child uses `[]`. A child of node `1` uses `[1]`. A grandchild under `1 -> 2` uses `[1, 2]`.

Allowed canonical node types:

- `title`
- `section`
- `table`
- `figure`

Unknown node types are tolerated by the current parser as base nodes, but adapters should not emit them for Canonical DocJSON v1.

## Text Primitives

Bounding boxes may be encoded as a list or an object:

```json
[0, 0, 100, 20]
```

```json
{"x0": 0, "y0": 0, "x1": 100, "y1": 20}
```

`span`:

```json
{
  "text": "example",
  "bold": false,
  "bbox": [0, 0, 100, 20],
  "page_number": 1
}
```

`textline`:

```json
{
  "text": "example",
  "bold": false,
  "bbox": [0, 0, 100, 20],
  "page_number": 1,
  "spans": []
}
```

Required for text extraction:

- `text`
- `bbox`
- `page_number`

Recommended:

- `bold`
- `spans`

If `spans` are unavailable, adapters should still create one span mirroring the textline.

## Title Nodes

`title` nodes represent headings or section containers.

```json
{
  "id": 1,
  "type": "title",
  "page_number": 1,
  "end_page_number": 1,
  "parent_path": [],
  "data": {
    "text": "第一节 业务概览",
    "textlines": []
  },
  "children": [],
  "meta": {}
}
```

Required in `data`:

- `text`

Recommended in `data`:

- `textlines`

If `data.text` is missing, the current runtime can derive title text by concatenating `data.textlines[].text`.

## Section Nodes

`section` nodes represent paragraph-like text blocks.

```json
{
  "id": 2,
  "type": "section",
  "page_number": 1,
  "end_page_number": 1,
  "parent_path": [1],
  "data": {
    "textlines": []
  },
  "children": [],
  "meta": {}
}
```

Required in `data`:

- `textlines`

The current runtime returns section text by concatenating `textlines[].text` without inserting separators.

## Table Nodes

`table` nodes represent structured tables.

```json
{
  "id": 3,
  "type": "table",
  "page_number": 1,
  "end_page_number": 1,
  "parent_path": [1],
  "data": {
    "row_num": 2,
    "col_num": 2,
    "cells": []
  },
  "children": [],
  "meta": {}
}
```

Required in `data`:

- `row_num`
- `col_num`
- `cells`

`cell`:

```json
{
  "text": "字段",
  "bold": false,
  "row_index": 0,
  "col_index": 0,
  "row_span": 1,
  "col_span": 1,
  "bbox": [0, 0, 50, 20],
  "page_number": 1,
  "spans": []
}
```

Required in cells:

- `text`
- `row_index`
- `col_index`
- `bbox`

Recommended in cells:

- `bold`
- `row_span`
- `col_span`
- `page_number`
- `spans`

For merged cross-page tables, set `data.merged = true` and include `data.merged_tables`:

```json
{
  "merged": true,
  "merged_tables": [
    {
      "row_num": 2,
      "col_num": 2,
      "page_number": 1,
      "bbox": [0, 0, 100, 40],
      "cells": []
    }
  ]
}
```

The current runtime creates virtual page nodes with IDs like `3:p1` for merged tables.

## Figure Nodes

`figure` nodes represent images or non-text visual blocks.

```json
{
  "id": 4,
  "type": "figure",
  "page_number": 2,
  "end_page_number": 2,
  "parent_path": [1],
  "data": {
    "bbox": [10, 10, 200, 150],
    "filename": "pages/2.png",
    "title": "公司架构图"
  },
  "children": [],
  "meta": {}
}
```

Required in `data`:

- `filename`

Recommended in `data`:

- `bbox`
- `title`

## Provenance Metadata

Adapters should preserve parser provenance without changing canonical node semantics.

Top-level example:

```json
{
  "doc_meta": {
    "source_format": "ppx_pages_objects",
    "source_tool": "ppx",
    "converter": "extract-agent",
    "converter_version": "0.4.x"
  }
}
```

Node-level example:

```json
{
  "meta": {
    "source_object_type": "textbox",
    "source_page_index": 0,
    "source_object_index": 12
  }
}
```

Current runtimes ignore `meta`, but it is part of the persisted canonical format so converters can keep debugging information.

## Adapter Requirements

External formats must be converted before storage:

- apiserver canonical-like DocJSON: validate and backfill missing recommended fields.
- PPX `pages[].objects[]`: convert to `tree.root`, pages, canonical textlines/spans, and provenance metadata.
- Future formats: add a new adapter, do not add format-specific logic to downstream tools.

Adapters must not silently produce a document with no `tree.root`. Unknown input formats should fail with a clear error.
