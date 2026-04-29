Status: implemented plan
Audience: maintainers
Last verified: 2026-04-27
Source of truth:
- pyproject.toml
- src/code_executor/executor.py
- src/code_executor/api.py
- src/code_executor/document/models/document.py
- src/code_executor/tools/tool_center.py
- src/xdev/config.py
- src/xdev/setup.py
- src/xdev/evaluation.py
- src/xdev/extract.py
- src/extract_agent_common/templates/tree/program.py

# xdev DocJSON 自动识别与 ToolHub 显式注入重构方案

本文按三个部分组织：

1. 完整方案
2. 执行清单
3. 执行计划

## 完整方案

### 背景

当前仓库里多个路径都使用 `docjson` 这个名字，但代码实际只支持一种运行时契约：带 `tree.root` 的内部 canonical DocJSON。

目前的隐式契约主要体现在：

- `code_executor.create_input()` 在 tree 模式下调用 `Document.from_dict(docjson)`。
- `Document.from_dict()` 只解析 `tree.root` 并构建 `Document` 节点树。
- `xdev run`、`xdev eval`、`xdev doc`、`evaluation_engine` 等路径最终都会读取 docjson 并进入 `Document` 或 `code_executor.execute(..., docjson=...)`。

`memect-ppx` 的产物也叫 `doc.json`，但结构是 `pages[].objects[]`。例如 `/path/to/ppx/doc.json` 顶层只有 `pages`。如果直接传给当前 `Document.from_dict()`，不会立刻报错，但会得到一个没有节点和文本的空 `Document`。这是高风险的静默失败。

另一方面，workspace 里的 `program.py` 当前常通过 `create_default_tool_hub()` 从全局上下文拿 code tools。这个依赖是隐式的，不利于测试，也不利于保证所有 xdev 提取 CLI/API 都使用同一套配置。

### 目标

- 所有需要 docjson 的地方都自动识别 canonical DocJSON 和 PPX DocJSON，不增加显式格式选项。
- PPX DocJSON 必须按 Markdown 标题栈还原章节结构，而不是只平铺文本。
- 全库退出 `article` / `list[str | Table]` 这类非结构化输入模式，统一使用 `Document`。
- 任何通过 xdev 发起的提取操作，包括 CLI 和 Python API，都自动读取 xdev 配置并注入单个 `ToolHub` 给 code executor。
- `code_executor` 保持底层执行器职责，不隐式读取 xdev 配置，只接受调用方显式传入的 `tool_hub`。
- 收敛 `pyproject.toml` 的 console scripts，只暴露用户需要的 CLI。

### 非目标

- 不新增 `--input-format`、`--docjson-format` 等显式格式选项。
- 不新增 PPX 专用导入命令，例如 `xdev import-data --ppx-dir`。
- 不支持多个命名 `ToolHub`。
- 不重新设计完整数据集、评估和 agentic-extract 的数据模型。
- 不立即删除 `create_default_tool_hub()` 这个 legacy API，但新模板和新文档不再推荐它。

### 分支

建议新建分支：

```bash
git switch -c codex/xdev-docjson-toolhub-refactor
```

这个分支同时处理 DocJSON 自动识别、Document-only 输入契约、xdev 自动 ToolHub 注入和 scripts 收敛。

### 方案一：DocJSON 自动识别层

新增 DocJSON dialect adapter，作为所有 docjson 读取路径的统一入口。

建议新增文件：

```text
src/code_executor/document/docjson_adapter.py
```

建议公开函数：

```python
def detect_docjson_dialect(data: dict) -> str:
    ...

def normalize_docjson(data: dict) -> dict:
    ...
```

第一版支持两种 dialect：

- `canonical_tree`: 当前内部格式，特征是存在 `tree.root`。
- `ppx_pages_objects`: PPX 格式，特征是顶层存在 `pages`，且页面里存在 `objects`。

`normalize_docjson()` 返回值必须是 canonical tree 格式。canonical 输入保持语义不变；PPX 输入转换成当前 `Document` 能读取的 canonical tree。

未知格式不应静默变成空文档，必须抛出清晰错误，提示支持的格式。

### 方案二：PPX 按 Markdown 标题栈还原章节结构

PPX 对象示例：

```json
{
  "type": "markdown",
  "bbox": [1575, 1724, 2240, 1869],
  "text": "## Who Am I?"
}
```

转换规则：

- `#` / `##` / `###` 等 Markdown heading 生成 canonical `title` 节点。
- heading level 用标题前 `#` 数量决定。
- 使用标题栈构造树：新的 heading 挂到最近的上级 heading 下；同级或更浅级别出现时弹栈。
- 非 heading 的 text/markdown 对象生成 `section` 节点，挂到最近 heading 下。
- 如果正文对象出现在任何 heading 之前，则挂到 root 下。
- 节点 ID 从 1 递增；root 使用 ID 0。
- `parent_path` 必须与还原后的树一致。
- `page_number` 使用 PPX page 的 `number`。
- `bbox` 写入 `data.textlines[0].bbox`。
- `spans` 使用单个 span，内容同 text。
- canonical `pages[]` 保留 page 的 `number`、`bbox`、`width`、`height` 等基础信息。

第一版不伪造 `TableNode`。如果 PPX 表格只以 markdown 文本出现，就作为 `section` 文本处理。

### 方案三：所有 docjson 入口自动 normalize

所有需要 docjson 的地方都必须自动识别格式。调用方不需要也不能指定格式选项。

应覆盖的入口包括：

- `Document.from_dict(docjson)`
- `code_executor.create_input(docjson, ...)`
- `code_executor.execute(..., docjson=...)`
- `code_executor.api.execute_on_docjson(...)`
- `code_executor.api.batch_execute_on_docjsons(...)`
- `xdev doc`
- `xdev run <doc_id>`
- `xdev run --docjson <file>`
- `xdev eval`
- `xdev.extract.extract_from_docjson(...)`
- `evaluation_engine` 通过 `code_executor` 执行 docjson 的路径

推荐策略：

- `Document.from_dict()` 内部做防御性 normalize，避免任何遗漏路径构造空文档。
- `create_input()` 仍可显式调用 normalize，以便错误边界更靠近执行器。
- `xdev doc` 等直接读文件后调用 `Document.from_dict()` 的路径不需要重复判断格式，但测试必须覆盖。

### 方案四：全库 Document-only

本次重构后，`article` / `list[str | Table]` 非结构化输入不再作为受支持路径。

需要退出支持的行为：

- 不再根据参数名 `article`、`data`、`items` 推断非结构化输入。
- 不再支持 `CODE_EXECUTOR_INPUT_MODE=flat` 作为运行时模式。
- 不再支持 `create_input(docjson, mode="flat")`。
- 不再让 `xdev.extract.extract_from_docjson(config=...)` 走旧 config flat 执行路径。
- 不再把 `to_plain_article()` 作为新功能入口；可保留 legacy 函数时也必须标注不推荐，并避免新代码依赖它。

新契约：

```python
from code_executor.document.models import Document

def extract(document: Document):
    ...
```

或：

```python
from code_executor.document.models import Document
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub):
    ...
```

如果用户程序仍使用 `def extract(article)` 或 list 类型注解，应给出明确错误，提示改为 `Document`。

### 方案五：code executor 显式接收 ToolHub

`code_executor` 是底层执行器，不应该自动读取 xdev 配置。

应新增可选参数：

```python
async def execute(..., tool_hub: ToolHub | None = None):
    ...
```

并透传到：

- `execute_on_docjson(..., tool_hub=None)`
- `batch_execute_on_docjsons(..., tool_hub=None)`
- 其他仍保留的 workspace/docjson 执行包装函数

调用 `extract()` 时：

- 如果用户函数支持 `tool_hub` 参数，则传入 `tool_hub`。
- 如果用户函数只支持一个 `Document` 参数，则调用 `extract(document)`。
- 如果用户函数签名不是 Document-only 支持范围，则抛出清晰错误。

### 方案六：所有 xdev 提取 CLI/API 自动注入 ToolHub

任何通过 xdev 发起的提取操作都必须自动读取 xdev 配置，构造单个 `ToolHub`，并传给 code executor。

覆盖范围：

- CLI: `xdev run <doc_id>`
- CLI: `xdev run --docjson <file>`
- CLI: `xdev run --pdf <file>`
- CLI: `xdev eval`
- Python API: `xdev.evaluation.run_single_extraction(...)`
- Python API: `xdev.evaluation.run_single_extraction_from_file(...)`
- Python API: `xdev.evaluation.run_evaluation(...)`
- Python API: `xdev.extract.extract_from_docjson(...)`

建议新增统一 helper：

```python
@dataclass
class XdevExtractionRuntime:
    concurrent: int
    tool_hub: ToolHub | None

def prepare_extraction_runtime() -> XdevExtractionRuntime:
    ...
```

职责：

- 调用 `load_config()`。
- 读取 `code_extractor.enabled_tools` 和 `code_extractor.tool_setup`。
- 构造唯一的 `ToolHub`。
- 返回 `concurrent` 和 `tool_hub`。
- 为了 legacy 程序短期兼容，可以继续设置全局 policy，但新链路必须显式传 `tool_hub`。

`xdev` 调用方不需要手动传 `tool_hub`。如果是 xdev API，也由 API 内部自动准备 runtime。

### 方案七：配置形状保持单 ToolHub

继续使用当前配置形状，不新增多 ToolHub 配置：

```json
{
  "code_extractor": {
    "enabled_tools": ["extract", "llm_select"],
    "tool_setup": {
      "extract_tool": {
        "llm": {
          "type": "openai",
          "config": {
            "model": "model-name",
            "api_key": "api-key",
            "base_url": "base-url"
          }
        },
        "max_content_length": 50000
      },
      "llm_select_tool": {
        "llm": {
          "type": "openai",
          "config": {
            "model": "model-name",
            "api_key": "api-key",
            "base_url": "base-url"
          }
        },
        "max_content_length": 50000
      }
    }
  }
}
```

`xdev-config` 继续负责补齐默认配置，例如 `base_url`、`concurrent`、`pdf_parse_concurrent`、`memect_api_base`、`max_content_length`。

### 方案八：workspace program.py 新写法

新 workspace 模板推荐：

```python
from typing import Any

from code_executor.document.models import Document, HeadingNode, ParagraphNode, TableNode
from code_executor.tools import ToolHub


def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any] | list[dict[str, Any]]:
    extract_tool = tool_hub.get_tool("extract") if tool_hub else None
    llm_select = tool_hub.get_tool("llm_select") if tool_hub else None

    texts = document.get_all_texts()
    ...
```

不再推荐：

```python
from code_executor import create_default_tool_hub
```

`create_default_tool_hub()` 可短期保留为 legacy API，但 prompt、skill、模板和主要文档都应改成显式注入写法。

### 方案九：CLI scripts 收敛

`pyproject.toml` 的 `[project.scripts]` 应只保留：

```toml
[project.scripts]
tree-sitter-cli = "tree_sitter_cli:app"
xdev = "xdev.cli:cli"
xdev-config = "xdev.config_cli:cli"
agentic-extract = "agentic_extract.cli:cli"
pdf-ai-explorer = "pdf_ai_explorer.cli:app"
```

需要移除：

```toml
evaluation-engine = "evaluation_engine.cli:app"
code-executor = "code_executor.cli:app"
evaluator = "evaluator.cli:app"
```

移除的是 console script 暴露，不代表立即删除 Python 包。

### 迁移策略

对已有 workspace：

- `def extract(document: Document)` 仍可运行。
- `def extract(document: Document, tool_hub: ToolHub)` 是新推荐写法。
- 依赖 `create_default_tool_hub()` 的旧程序短期可通过 legacy 全局 policy 继续工作，但不作为新契约。
- `def extract(article)` 不再受支持，应报错并提示改为 `Document`。

对用户 CLI：

- `xdev run --docjson canonical.json` 自动识别并执行。
- `xdev run --docjson ppx/doc.json` 自动识别并执行。
- `.xdev/data/docjson/<id>.json` 如果是 PPX 格式，`xdev doc`、`xdev run <doc_id>`、`xdev eval` 也应自动识别。
- 不新增格式选项。

对 PPX 导入：

- 本次不新增 PPX 专用导入命令。
- 如果用户已经把 PPX `doc.json` 放进现有 docjson 路径，读取时应自动识别。

### 风险与取舍

- PPX 章节结构依赖 Markdown heading。如果 PPX 输出缺少 heading，正文只能挂 root。
- PPX 表格第一版按文本处理，不能提供 `TableNode` API。
- 全库退出非结构化输入会影响旧测试和旧示例，需要同步清理文档和错误信息。
- `pdf-ai-explorer` 是外部包；本仓库自动识别 PPX 不代表外部 CLI 一定能直接读取 PPX 文件。
- legacy `create_default_tool_hub()` 保留期间会有两条工具获取路径，但新 xdev 路径必须以显式注入为准。

## 执行清单

### 分支与文档

- [x] 新建分支 `codex/xdev-docjson-toolhub-refactor`。
- [x] 保留本方案文档并纳入分支。
- [x] 更新 `docs/CHANGELOG.md`。

### DocJSON 自动识别

- [x] 新增 `src/code_executor/document/docjson_adapter.py`。
- [x] 实现 `detect_docjson_dialect(data)`。
- [x] 实现 `normalize_docjson(data)`。
- [x] 支持 `canonical_tree`。
- [x] 支持 `ppx_pages_objects`。
- [x] 未知格式抛出清晰错误，不返回空文档。

### PPX 章节树

- [x] 解析 Markdown heading level。
- [x] 用 heading stack 构造 `title` 层级树。
- [x] 将正文对象挂到最近 heading 下。
- [x] 正文早于 heading 时挂 root。
- [x] 正确生成 `id`、`parent_path`、`children`。
- [x] 保留 `page_number`、`bbox`、`textlines`、`spans`。

### 所有 docjson 入口

- [x] `Document.from_dict()` 做防御性 normalize。
- [x] `code_executor.create_input()` 接入 normalize。
- [x] `code_executor.execute(..., docjson=...)` 自动受益。
- [x] `code_executor.api.execute_on_docjson()` 自动受益。
- [x] `code_executor.api.batch_execute_on_docjsons()` 自动受益。
- [x] `xdev doc` 自动受益。
- [x] `xdev run` 自动受益。
- [x] `xdev eval` 自动受益。
- [x] `evaluation_engine` 的 docjson 执行路径自动受益。

### Document-only

- [x] 移除 `CODE_EXECUTOR_INPUT_MODE=flat` 支持。
- [x] 移除按 `article`、`data`、`items` 推断非结构化输入。
- [x] `create_input(..., mode="flat")` 改为清晰失败。
- [x] `xdev.extract.extract_from_docjson(config=...)` 旧 config 路径改为清晰失败。
- [x] 更新相关测试，不再期望非结构化输入成功。
- [x] 更新文档，不再推荐 `article` / `list[str | Table]`。

### ToolHub 显式注入

- [x] `code_executor.execute()` 增加可选 `tool_hub` 参数。
- [x] `execute_on_docjson()` 透传 `tool_hub`。
- [x] `batch_execute_on_docjsons()` 透传 `tool_hub`。
- [x] `_run_extract()` 支持 `extract(document)`。
- [x] `_run_extract()` 支持 `extract(document, tool_hub)`。
- [x] 非 Document-only 签名报清晰错误。

### xdev 自动读取配置并注入

- [x] 新增统一 runtime helper，例如 `prepare_extraction_runtime()`。
- [x] helper 自动 `load_config()`。
- [x] helper 构造单个 `ToolHub | None`。
- [x] helper 返回 `concurrent` 和 `tool_hub`。
- [x] `run_single_extraction()` 使用 helper 并传入 `tool_hub`。
- [x] `run_single_extraction_from_file()` 使用 helper 并传入 `tool_hub`。
- [x] `run_evaluation()` 使用 helper 并传入 `tool_hub`。
- [x] `xdev.extract.extract_from_docjson()` 使用 helper 并传入 `tool_hub`。
- [x] CLI 通过这些 API 自动获得同样行为。

### 模板、prompt、skill 和 scripts

- [x] 更新 `src/extract_agent_common/templates/tree/program.py`。
- [x] 更新 `src/agentic_extract/prompts/tools/code_tools.py`。
- [x] 更新 `src/agentic_extract/prompts/strategies.py`。
- [x] 更新 `src/agentic_extract/skills/extract_dev/SKILL.md`。
- [x] 更新 `src/agentic_extract/skills/extract_workflow/SKILL.md`。
- [x] 更新 `src/agentic_extract/skills/xdev/SKILL.md`。
- [x] 更新 docs 中主要示例。
- [x] 收敛 `pyproject.toml` scripts 到指定 5 个。

## 执行计划

### 阶段 0：开工保护

目的：把后续实现放到独立分支，并避免覆盖用户改动。

步骤：

1. 运行 `git status --short --branch`。
2. 新建 `codex/xdev-docjson-toolhub-refactor`。
3. 确认本方案文档在新分支上。

测试/验证：

```bash
git status --short --branch
```

完成条件：

- 当前分支为 `codex/xdev-docjson-toolhub-refactor`。
- 没有覆盖无关用户改动。

### 阶段 1：DocJSON adapter 与 PPX 章节树

目的：先把 canonical/PPX 自动识别和 PPX 章节结构还原做成独立可测单元。

预计改动：

- `src/code_executor/document/docjson_adapter.py`
- `tests/code_executor/test_docjson_adapter.py`

步骤：

1. 实现 dialect 检测。
2. 实现 canonical 原样 normalize。
3. 实现 PPX Markdown heading stack。
4. 实现 PPX `section` 挂载规则。
5. 增加未知格式错误测试。

测试/验证：

```bash
uv run pytest -q tests/code_executor/test_docjson_adapter.py
uv run python - <<'PY'
import json
from pathlib import Path
from code_executor.document.docjson_adapter import normalize_docjson
from code_executor.document.models.document import Document

data = json.loads(Path("/path/to/ppx/doc.json").read_text())
doc = Document.from_dict(normalize_docjson(data))
print([n.get_title() for n in doc.iter_nodes("title")])
print(doc.get_all_texts())
PY
```

完成条件：

- `Who Am I?` 是 title。
- bullet 文本是该 title 下的 section。
- 未知格式不静默成功。

### 阶段 2：接入所有 docjson 入口

目的：保证所有读取 docjson 的地方自动识别，不需要格式选项。

预计改动：

- `src/code_executor/document/models/document.py`
- `src/code_executor/executor.py`
- `src/code_executor/api.py`
- `src/xdev/cli.py`
- 相关测试

步骤：

1. `Document.from_dict()` 内部 normalize。
2. `create_input()` 保持 Document-only 并 normalize。
3. 确认 `execute_on_docjson()` / batch API 经过 normalize。
4. 覆盖 `xdev doc`、`xdev run`、`xdev eval`。

测试/验证：

```bash
uv run pytest -q tests/code_executor/test_docjson_adapter.py tests/code_executor/test_document_model.py tests/code_executor/test_unified_execute.py
xdev run --docjson /path/to/ppx/doc.json --workspace <tmp-workspace>
```

完成条件：

- canonical DocJSON 行为不变。
- PPX DocJSON 不再产生空 Document。
- 所有 docjson 读取路径不需要显式格式参数。

### 阶段 3：退出非结构化输入模式

目的：统一运行时输入为 `Document`。

预计改动：

- `src/code_executor/executor.py`
- `src/code_executor/loader.py`
- `src/code_executor/utils.py`
- `src/xdev/extract.py`
- 相关测试和文档

步骤：

1. 移除或禁用 `CODE_EXECUTOR_INPUT_MODE=flat`。
2. `detect_input_mode()` 不再把 `article/data/items` 判为可运行模式。
3. `create_input(mode="flat")` 抛出清晰错误。
4. `xdev.extract_from_docjson(config=...)` 抛出清晰错误。
5. 更新旧测试预期。

测试/验证：

```bash
uv run pytest -q tests/code_executor tests/xdev
```

完成条件：

- 非结构化输入不再成功执行。
- 错误信息指向 `def extract(document: Document, ...)`。

### 阶段 4：code executor 显式 ToolHub 参数

目的：让底层执行器支持注入，但不读取 xdev 配置。

预计改动：

- `src/code_executor/executor.py`
- `src/code_executor/api.py`
- `tests/code_executor/test_unified_execute.py`

步骤：

1. `execute()` 增加 `tool_hub` 参数。
2. API 包装函数透传 `tool_hub`。
3. `_run_extract()` 根据签名传入或不传入 `tool_hub`。
4. 使用 mock ToolHub 写单测。

测试/验证：

```bash
uv run pytest -q tests/code_executor/test_unified_execute.py
```

完成条件：

- `extract(document)` 可运行。
- `extract(document, tool_hub)` 可运行。
- `code_executor` 不读取 xdev 配置。

### 阶段 5：xdev 自动读取配置并注入 ToolHub

目的：所有 xdev 提取 CLI/API 都自动准备 runtime。

预计改动：

- `src/xdev/setup.py`
- `src/xdev/evaluation.py`
- `src/xdev/extract.py`
- `tests/xdev/*`
- `tests/integration/test_suite.py`

步骤：

1. 新增 `XdevExtractionRuntime`。
2. 新增 `prepare_extraction_runtime()`。
3. `run_single_extraction()` 使用 runtime。
4. `run_single_extraction_from_file()` 使用 runtime。
5. `run_evaluation()` 使用 runtime。
6. `extract_from_docjson()` 使用 runtime。
7. CLI 通过这些 API 自动获得注入。

测试/验证：

```bash
uv run pytest -q tests/xdev tests/integration/test_suite.py
```

完成条件：

- 任意 xdev 提取 CLI/API 都自动读取配置。
- ToolHub 显式传给 code executor。
- 调用方不需要传 `tool_hub`。

### 阶段 6：模板、prompt、skill、docs 和 scripts

目的：把用户可见写法切到新契约。

预计改动：

- `src/extract_agent_common/templates/tree/program.py`
- `src/agentic_extract/prompts/*`
- `src/agentic_extract/skills/*`
- `docs/*`
- `pyproject.toml`

步骤：

1. 新模板改为 `extract(document, tool_hub)`。
2. prompt 和 skill 改为显式注入示例。
3. 文档移除对非结构化输入的推荐。
4. `pyproject.toml` scripts 只保留指定 5 个。

测试/验证：

```bash
rg -n "extract\\(article|CODE_EXECUTOR_INPUT_MODE|to_plain_article|create_default_tool_hub|code-executor|evaluation-engine|evaluator" README.md docs src pyproject.toml
uv run ruff check src/code_executor src/xdev src/agentic_extract src/extract_agent_common tests/code_executor tests/xdev
```

完成条件：

- 剩余命中只属于 legacy 说明或内部 API。
- console scripts 符合要求。

### 阶段 7：端到端回归与提交

目的：在提交前压低集成风险。

测试/验证：

```bash
uv run pytest -q tests/code_executor tests/xdev tests/integration/test_suite.py
uv run ruff check src/code_executor src/xdev src/agentic_extract src/extract_agent_common tests/code_executor tests/xdev
uv build
```

完成条件：

- 相关测试通过。
- ruff 通过。
- build 通过。
- `docs/CHANGELOG.md` 已更新。

建议提交信息：

```bash
git commit -m "refactor: normalize docjson inputs and inject xdev tool hub"
```
