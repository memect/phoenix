# xdev - 数据管理和评估工具

extract-dev 的下一代替代品，为 AI Agent 和人工开发者提供数据导入、标注、评估的完整工具链。

## 与 extract-dev 的关系

- **完全独立**，不兼容 extract-dev 的 `.extract-dev/` 目录
- xdev 使用 `.xdev/` 作为默认数据目录
- 两者可以在同一个 workspace 中共存

## 模块结构

```
src/xdev/
├── __init__.py        # 模块入口
├── cli.py             # CLI 入口 (click)
├── config.py          # 配置管理
├── models.py          # 数据模型 (Pydantic)
├── api.py             # 核心 API 函数
├── import_data.py     # 数据导入功能
└── evaluation.py      # 评估和提取功能
```

## workspace 初始化约定

`xdev init` 只创建最小 workspace 骨架：

- `.gitignore`
- `program.py`
- `tests/`
- `docs/`
- `.xdev/`

其中 `docs/` 只是可选文档目录，不再默认生成 `data_issues.md`、
`known_limitations.md`、`notes.md` 这类记录文件。

## 数据目录结构

所有命令通过 `--data-dir` 指定数据目录，默认为 `.xdev`。

```
.xdev/
├── manifest.json              # 数据源元信息（import 时生成/更新）
├── schema.json                # Schema 定义（agent 编辑）
├── data/
│   ├── docjson/
│   │   ├── <doc_id>.json      # DocJSON 文件（PDF 解析结果）
│   │   └── ...
│   └── pdf/
│       ├── <doc_id>.pdf       # 原始 PDF 文件
│       └── ...
└── labels/
    ├── <doc_id>.json          # 每个文档的标注（agent 编辑）
    └── ...
```

### 关键约定

1. **doc_id = 文件名（不含扩展名）**：`data/docjson/report_001.json` 的 doc_id 为 `report_001`
2. **PDF 与 DocJSON 配对**：同一 doc_id 的 PDF 和 DocJSON 必须同时存在于 `data/pdf/` 和 `data/docjson/`
3. **标注文件独立**：每个文档一个标注文件 `labels/<doc_id>.json`，而不是合并在一个 `labels.json` 中
4. **schema.json 和标注文件由 agent 直接编辑**：xdev 不提供 `set-schema` 或 `label` 写入命令，agent 通过文件写入工具直接操作

---

## 文件格式规范

### manifest.json

import 时自动生成，记录数据来源。使用 `--sync` / `--skip-exist` 时可从中读取上次的导入参数。

```json
{
  "source": {
    "type": "set-id",
    "set_id": "abc-123",
    "base_url": "http://localhost:8008",
    "std_ids": ["doc-id-1", "doc-id-2"]
  },
  "imported_at": "2026-03-02T10:30:00.000000",
  "doc_count": 2
}
```

数据源类型：

| type | 字段 | 说明 |
|------|------|------|
| `set-id` | `set_id`, `base_url`, `std_ids` | 远程标准集（`std_ids` 可选，白名单） |
| `pdfs` | `pdf_dir` | 本地 PDF 目录（绝对路径） |
| `data-dir` | `path` | 另一个 .xdev 目录（绝对路径） |

### schema.json

定义提取目标的字段结构。由 agent 直接创建/编辑。

**单条记录模式（object）**：每篇文档提取一条记录。

```json
{
  "type": "object",
  "data": {
    "公司名称": "str",
    "注册资本": "float",
    "成立日期": "str",
    "是否上市": "bool"
  }
}
```

**多条记录模式（list_of_objects）**：每篇文档提取多条同类记录。

```json
{
  "type": "list_of_objects",
  "data": {
    "股东名称": "str",
    "持股比例": "float",
    "出资金额": "float"
  }
}
```

**字段类型**：`"str"` | `"int"` | `"float"` | `"bool"` | `"list"`

**约束**：
- 只支持扁平一层结构，不支持嵌套
- `data` 中的 key 就是字段名，value 是类型名

### labels/\<doc_id\>.json

每个文档的标注数据。由 agent 直接创建/编辑。

**object 模式**：

```json
{
  "公司名称": "XX科技有限公司",
  "注册资本": 1000.0,
  "成立日期": "2020-01-15",
  "是否上市": false
}
```

**list_of_objects 模式**：

```json
[
  {"股东名称": "张三", "持股比例": 30.0, "出资金额": 300.0},
  {"股东名称": "李四", "持股比例": 20.0, "出资金额": 200.0}
]
```

**约束**：
- 标注的 key 必须与 `schema.json` 的 `data` key 完全一致
- 缺失信息标注为空字符串 `""` 或 `null`
- 文件名（不含 `.json`）必须对应已有的 doc_id

---

## CLI 命令

### 全局选项

所有命令都支持：

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--data-dir PATH` | 数据目录 | `.xdev` |

### `xdev import-data` — 导入数据

从数据源导入或增量维护 PDF + DocJSON 数据。六种模式互斥，必须且只能指定一种；但如果不指定模式、只传 `--sync` / `--skip-exist`，会自动从 `manifest.json` 读取上次的 `set-id` 数据源参数。

```bash
# 从远程标准集导入
xdev import-data --set-id <id> --base-url <url>

# 从本地 PDF 目录导入（调用 memect API 并发解析）
xdev import-data --pdfs <dir>

# 从另一个 .xdev 目录导入
xdev import-data --from-data-dir <path>

# 从数据源配置文件导入
xdev import-data --source <source.json>

# 增量添加 PDF（单文件或目录）
xdev import-data --add-pdf <file_or_dir> [--force]

# 重新解析已有 PDF
xdev import-data --reparse [--doc-ids doc1,doc2]

# 复用 manifest 中的 set-id 参数进行同步
xdev import-data --sync
xdev import-data --skip-exist
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--set-id TEXT` | 远程标准集 ID | — |
| `--base-url TEXT` | 标准集 API 地址 | `http://localhost:8008` |
| `--std-ids TEXT` | 文档 ID 白名单（逗号分隔），配合 `--set-id` | — |
| `--std-ids-file PATH` | 文档 ID 白名单文件（一行一个 ID），配合 `--set-id` | — |
| `--pdfs PATH` | 本地 PDF 目录 | — |
| `--from-data-dir PATH` | 源 data-dir 路径 | — |
| `--source PATH` | 数据源配置文件 | — |
| `--add-pdf PATH` | 增量添加 PDF（单文件或目录） | — |
| `--reparse` | 重新解析已有 PDF 生成新 DocJSON | `False` |
| `--doc-ids TEXT` | 配合 `--reparse` 使用，逗号分隔的文档 ID | — |
| `--force` | 配合 `--add-pdf` 使用，覆盖已有文档 | `False` |
| `--sync` | 配合 `--set-id` 使用，导入后删除远程不存在的本地文档；也可只传该参数从 manifest 续跑 | `False` |
| `--skip-exist` | 配合 `--set-id` 使用，跳过本地已有文档；也可只传该参数从 manifest 续跑 | `False` |

**数据源配置文件格式**（`source.json`）：

```json
{"type": "set-id", "set_id": "abc-123", "base_url": "http://localhost:8008"}
```

```json
{"type": "pdfs", "pdf_dir": "/data/my_pdfs"}
```

```json
{"type": "data-dir", "path": "/other/project/.xdev"}
```

**PDF 导入说明**：
- 调用 memect API (`http://localhost:6111/api`) 解析 PDF 为 DocJSON
- 使用 `code_executor.document.utils.pdf_parser.parse_pdf_file_to_docjson` 复用已有解析逻辑
- 并发处理（线程池，max_workers=4）
- doc_id 为 PDF 文件名（不含扩展名）

**增量维护说明**：

- `--add-pdf`：向现有 `.xdev` 增量追加 PDF；默认跳过已存在文档，配合 `--force` 可覆盖
- `--reparse`：对现有 `data/pdf/*.pdf` 重新解析生成 DocJSON；可用 `--doc-ids` 只重解析部分文档
- `--sync`：仅支持 `set-id` 数据源；导入后删除远程已经不存在的本地文档
- `--skip-exist`：仅支持 `set-id` 数据源；保留本地已有文档，不重复下载

### `xdev sync-pdfs` — 同步 PDF 目录

用于 PDF 目录型数据源的长期维护。它会比较源目录和当前 `.xdev/data/`，自动处理新增、删除、修改，删除时保留 label。

```bash
xdev sync-pdfs /path/to/pdfs
xdev sync-pdfs /path/to/pdfs --data-dir .xdev
```

前提：

- `manifest.json` 必须已存在
- 当前数据源类型必须是 `pdfs`

输出会报告：

- 新增文档数
- 删除文档数
- 修改文档数
- 未变化文档数

### `xdev list` — 列出文档

```bash
xdev list [--data-dir .xdev]
```

输出示例：

```
数据源: set-id
文档数量: 20
导入时间: 2026-03-02T10:30:00

doc_001
doc_002
doc_003
```

### `xdev doc <doc_id>` — 查看文档内容

```bash
xdev doc doc_001 [--data-dir .xdev]
```

输出 DocJSON 自动 normalize 后的文档纯文本。canonical `tree.root` 与 PPX
`pages[].objects[]` 都会通过 `Document.from_dict()` 读取，再使用
`Document.get_all_texts()` 展示。

### `xdev label-guide` — 标注指导

```bash
# 通用指导（输出 schema 信息、标注目录、格式说明）
xdev label-guide [--data-dir .xdev]

# 特定文档的标注指导（输出文件路径和标注模板）
xdev label-guide <doc_id> [--data-dir .xdev]
```

**前提**：`schema.json` 必须已存在。

通用指导输出示例：

```
# 标注指导

## Schema 文件
路径: .xdev/schema.json
类型: object

## 标注文件
目录: .xdev/labels/
格式: <doc_id>.json

## 标注格式
每个文档标注一个对象：
{
  "公司名称": "<str>",
  "注册资本": "<float>"
}
```

特定文档输出示例：

```
# 文档 doc_001 标注指导

标注文件路径: .xdev/labels/doc_001.json

标注模板：
{
  "公司名称": "",
  "注册资本": ""
}
```

### `xdev eval` — 运行评估

```bash
# 全量评估（所有已标注的文档）
xdev eval [--data-dir .xdev] [--workspace .]

# 单文档评估
xdev eval <doc_id> [--data-dir .xdev] [--workspace .]
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--workspace PATH` | workspace 目录（包含 program.py） | 当前目录 |

**前提**：
- `schema.json` 必须已存在
- `labels/` 下必须有标注数据
- workspace 中必须有 `program.py`

复用 `evaluation_engine` 进行评估。输出准确率和错误详情。

`xdev eval` 内部使用 `xdev.evaluation_result.EvaluationResult` 包装评估结果。
该对象会额外保存 `set_id` / `base_url` 元数据，同时透传底层评估对象的常用属性，
因此可以直接访问 `overall_accuracy`、`total_records`、`field_stats`、`details` 等字段。

### `xdev run <doc_id>` — 执行提取

```bash
xdev run <doc_id> [--data-dir .xdev] [--workspace .]
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--workspace PATH` | workspace 目录（包含 program.py） | 当前目录 |

在单个文档上执行 `program.py`，输出提取结果 JSON。`xdev` 会自动读取配置，
构造一个 `ToolHub`，并通过 `code_executor` 注入给
`extract(document, tool_hub)`。

---

## 环境变量

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `XDEV_DATA_DIR` | 默认数据目录 | `.xdev` |
| `XDEV_CONCURRENT` | 评估并发数（`xdev eval`） | `16` |
| `XDEV_PDF_PARSE_CONCURRENT` | PPX 批量 PDF 文件级解析并发 | `1` |
| `XDEV_MEMECT_API_BASE` | legacy memect PDF API 地址（默认不再使用） | `http://localhost:6111/api` |

也支持 `.xdev.env` 配置文件。

## 配置文件（`~/.config/xdev/config.json` 或 `.xdev/config.json`）

`xdev` 支持通过配置统一管理 code tools。`xdev run` / `xdev eval` 会读取该配置并注入 `ToolHub`：

```json
{
  "concurrent": 16,
  "code_extractor": {
    "enabled_tools": ["extract", "pdf_to_image"],
    "tool_setup": {
      "extract_tool": {
        "llm": {
          "type": "openai",
          "config": {
            "api_key": "YOUR_API_KEY",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4o-mini"
          }
        },
        "max_content_length": 50000
      },
      "pdf_to_image_tool": {
        "dpi": 180
      }
    }
  }
}
```

- `code_extractor.tool_setup` 对应 `code_executor` 的 `tool_setup`
- `code_extractor.enabled_tools` 对应 `code_executor` 的 `enabled_tools`
- 在 `xdev run` / `xdev eval` 执行前会构造 ToolHub 并传给 `program.py`

如果你想同时配置全局 `agentic-extract` 和 `xdev` 的模型，可以直接运行：

```bash
xdev-config
```

它会：

- 写入 `~/.config/agentic-extract/config.json` 的 `llm`
- 写入 `~/.config/xdev/config.json` 的 `extract-llm`
- 让 `xdev` 的 `extract_tool` 和 `llm_select_tool` 共用同一套 `extract-llm`

---

## Python API

```python
from xdev.api import (
    list_doc_ids,
    get_docjson_path,
    get_pdf_path,
    get_label_path,
    get_label,
    list_labeled_doc_ids,
    get_schema,
    get_manifest,
)

from xdev.evaluation import (
    run_evaluation,
    run_single_extraction,
)

from xdev.import_data import (
    import_from_set_id,
    import_from_pdfs,
    import_from_data_dir,
    import_from_source,
    add_pdfs,
    reparse_docs,
    sync_pdfs,
    resolve_std_ids,
)
```

## `xdev run` 的单文件模式

除了传统的 `xdev run <doc_id>` 之外，也可以直接对单个文件执行提取：

```bash
xdev run --workspace /path/to/workspace --pdf /path/to/file.pdf
xdev run --workspace /path/to/workspace --docjson /path/to/file.json
```

- `doc_id`、`--pdf`、`--docjson` 三者必须且只能选一个
- `--pdf` 会调用本机 `ppx parse` 先解析 PDF，再执行 workspace 的 `program.py`
- `--docjson` 直接读取现成 DocJSON，不依赖 `.xdev/data/`

批量 PDF 导入和同步也默认使用 `ppx parse <dir>`；`pdf_parse_concurrent` / `XDEV_PDF_PARSE_CONCURRENT` 控制 PPX 同时解析多少个 PDF，默认 `1`。

所有 API 函数都接受 `data_dir` 参数，默认为 `.xdev`。

`run_evaluation()` 返回 `xdev.evaluation_result.EvaluationResult`，可直接当作评估结果使用：

```python
result = run_evaluation(data_dir=".xdev", workspace=".")
print(result.overall_accuracy)
print(result.total_records)
print(result.field_stats)
```

---

## Agent 工作流（无标注模式）

以下是 agent 使用 xdev 完成无标注提取任务的典型流程：

```
1. 导入数据
   $ xdev import-data --pdfs /path/to/pdfs

2. 查看数据
   $ xdev list
   $ xdev doc <doc_id>

3. 定义 schema（直接写文件）
   → 写入 .xdev/schema.json

4. 获取标注指导
   $ xdev label-guide <doc_id>

5. 标注数据（直接写文件）
   → 写入 .xdev/labels/<doc_id>.json

6. 编写提取程序
   → 写入 program.py

7. 测试提取
   $ xdev run <doc_id>

8. 运行评估
   $ xdev eval

9. 根据评估结果迭代优化 program.py
   → 重复 7-8
```
