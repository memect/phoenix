# code_executor Usage

Status: active
Audience: maintainers
Last verified: 2026-04-27
Source of truth:
- `src/code_executor/executor.py`
- `src/code_executor/api.py`
- `src/xdev/setup.py`

`code_executor` runs a workspace `program.py` or a Python source string against
DocJSON input. Runtime DocJSON execution is Document-only:

- canonical DocJSON with `tree.root` is used as-is.
- PPX DocJSON with `pages[].objects[]` is auto-normalized.
- `extract(article)` / flat mode is not supported for DocJSON execution.

## Program Shape

For xdev workspaces, prefer this signature:

```python
from typing import Any

from code_executor.document.models.document import Document
from code_executor.tools import ToolHub


def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any] | list[dict[str, Any]]:
    texts = document.get_all_texts()
    extract_tool = tool_hub.get_tool("extract")
    ...
```

`xdev run` and `xdev eval` automatically load xdev config, construct one
`ToolHub`, and pass it into `code_executor`. Direct `code_executor.execute()`
does not read xdev config; pass `tool_hub=` explicitly if the program expects
one.

## Direct API

```python
from code_executor import execute

result = await execute(
    workspace="/path/to/workspace",
    docjson=docjson_payload,
    tool_hub=my_tool_hub,
)
```

For batch execution:

```python
from code_executor import batch_execute_on_docjsons

results = await batch_execute_on_docjsons(
    program=program_source,
    docjsons=docjson_payloads,
    concurrent=16,
    tool_hub=my_tool_hub,
)
```

## Document Helpers

```python
for node in document.iter_nodes("title"):
    print(node.get_text(), node.page_number)

texts = document.get_all_texts()
page_nodes = document.get_nodes_by_page(1)
```

`create_input(docjson)` remains available for tests and low-level code. It
always returns a `Document`; `mode="flat"` raises a clear error.

## ToolHub Rules

- `code_executor` accepts a ToolHub only through the explicit `tool_hub=`
  parameter.
- `xdev` is responsible for reading xdev config and injecting ToolHub.
- `program.py` should use the injected `tool_hub` argument instead of reading
  config or constructing tool state itself.
