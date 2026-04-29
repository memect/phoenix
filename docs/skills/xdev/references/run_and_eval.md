# 调试 `program.py` 与评估

## 单文档调试

先跑单文档：

```bash
xdev run <doc_id>
```

这一步适合：

- 检查 `program.py` 是否能正常执行
- 看当前提取结果是否接近预期
- 在批量评估前先做快速回归

## 评估

评估单文档：

```bash
xdev eval <doc_id>
```

评估全量：

```bash
xdev eval
```

`xdev eval` 依赖：

- `.xdev/schema.json`
- `.xdev/labels/*.json`
- workspace 中可运行的 `program.py`

## 推荐迭代方式

1. 读文档和标注
2. 修改 `program.py`
3. `xdev run <doc_id>`
4. 如有必要，修 schema 或 labels
5. `xdev eval`
6. 只在 `.xdev` 已可运行后，再交给 `agentic-extract run`

## `program.py` 入口约束

`xdev` 默认执行 workspace 下的 `program.py`，入口形态应兼容：

```python
from code_executor.document.models import Document
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub):
    ...
```

返回值应与 `.xdev/schema.json` 一致：

- `object` -> `dict`
- `list_of_objects` -> `list[dict]`

## 使用 LLM 工具时

如果 `program.py` 使用 `extract`、`llm_select`、`pdf_to_image` 等工具，优先在 `.xdev/config.json` 中显式配置 `code_extractor`。`xdev run` / `xdev eval` 会自动读取配置并把 `tool_hub` 注入到 `extract(document, tool_hub)`，不要在 `program.py` 中自行读取 xdev 配置。

## 切到 agentic-extract 的时机

满足下面条件后，再切到 `agentic-extract` skill：

- `.xdev` 数据已经准备好
- schema 和 labels 至少处于可运行状态
- `program.py` 能在单文档上跑起来
