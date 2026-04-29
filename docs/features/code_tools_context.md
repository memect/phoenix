# xdev ToolHub Injection

Status: active
Audience: maintainers
Last verified: 2026-04-27
Source of truth:
- `src/xdev/setup.py`
- `src/xdev/evaluation.py`
- `src/xdev/extract.py`
- `src/code_executor/executor.py`

xdev owns code-tool configuration. Every xdev extraction entrypoint loads xdev
config, builds one `ToolHub`, and passes it explicitly to `code_executor`.

## Runtime Flow

1. `xdev` calls `prepare_extraction_runtime()`.
2. The helper loads `~/.config/xdev/config.json`, project `.xdev/config.json`,
   and `XDEV_*` environment overrides.
3. If `code_extractor.tool_setup` is configured, xdev initializes the legacy
   global policy and creates a configured ToolHub.
4. If no tools are configured, xdev injects an empty ToolHub.
5. `code_executor` calls either `extract(document)` or
   `extract(document, tool_hub)` based on the program signature.

## Program Shape

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub


def extract(document: Document, tool_hub: ToolHub):
    extract_tool = tool_hub.get_tool("extract")
    llm_select = tool_hub.get_tool("llm_select")
    ...
```

`program.py` should not read xdev config or construct tool state itself. Direct
`code_executor.execute()` also does not read xdev config; callers must pass
`tool_hub=` explicitly.
