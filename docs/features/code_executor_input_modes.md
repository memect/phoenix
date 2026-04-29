# code_executor Document-only Input

Status: active
Audience: maintainers
Last verified: 2026-04-27
Source of truth:
- `src/code_executor/executor.py`
- `src/code_executor/document/docjson_adapter.py`

`code_executor` no longer supports switching DocJSON execution into a flat
article input. DocJSON inputs are normalized and passed to `program.py` as a
`Document`.

## Supported DocJSON Dialects

- Canonical DocJSON: `tree.root`
- PPX DocJSON: `pages[].objects[]`

PPX input is converted into a `title -> section` tree by reading Markdown
heading levels (`#`, `##`, `###`, ...). Non-heading text becomes a `section`
under the nearest heading.

## Program Signature

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub


def extract(document: Document, tool_hub: ToolHub):
    ...
```

`extract(document)` is still accepted for simple programs, but new xdev
templates should include `tool_hub` because xdev injects it automatically.

## Unsupported Paths

- `create_input(docjson, mode="flat")`
- `extract(article)` for DocJSON execution
- `extract(data)` for DocJSON execution

These paths fail clearly and should be migrated to `Document`.
