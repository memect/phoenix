---
name: xdev
description: 当你需要管理提取数据（导入、查看、标注）、运行提取、评估准确率时激活此 skill。这是提取开发的基础工具，所有提取相关任务都从这里开始。
---

# xdev — 数据管理和评估工具

xdev 管理 `.xdev/` 目录中的文档数据、schema、标注，并提供提取评估能力。

## 安装

### 从 PyPI 安装

使用 uv（推荐）：

```bash
uv tool install extract-agent
```

或使用 pip（需要在虚拟环境中）：

```bash
pip install extract-agent
```

注意：
- `extract-agent` 发布到 PyPI，默认安装命令不需要指定私有 index
- macOS Homebrew Python 禁止全局 pip install，请使用 `uv tool install` 或在虚拟环境中安装

安装后可用命令：
- `xdev` — 数据管理和评估工具
- `pdf-ai-explorer` — PDF 长文档导航工具
- `agentic-extract` — 自动化提取 agentic loop（可选）

### 验证安装

```bash
xdev --help
pdf-ai-explorer --help
```

## 配置

xdev 支持三层配置（优先级：环境变量 > 项目配置 > 全局配置 > 默认值）。

### 全局配置

创建 `~/.config/xdev/config.json`。

### 项目配置

在 workspace 创建 `.xdev/config.json`。

### 环境变量

```bash
export XDEV_BASE_URL="http://localhost:8008"
export XDEV_CONCURRENT=4
export XDEV_DATA_DIR=".xdev"
export XDEV_MEMECT_API_BASE="http://localhost:6111/api"
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `data_dir` | 数据目录路径 | `.xdev` |
| `base_url` | 标准集 API 地址（用于 `--set-id` 导入） | `http://localhost:8008` |
| `concurrent` | 提取执行并发数 | `16` |
| `pdf_parse_concurrent` | PPX 批量 PDF 文件级解析并发 | `1` |
| `memect_api_base` | legacy PDF 解析服务地址（默认不再使用） | `http://localhost:6111/api` |
| `code_extractor` | 透传给 `code_executor` 的工具配置（覆盖默认 `.code_tools.env`） | `null` |

### 完整配置示例（包含现有全部字段）

```json
{
  "data_dir": ".xdev",
  "base_url": "http://localhost:8008",
  "concurrent": 16,
  "pdf_parse_concurrent": 1,
  "memect_api_base": "http://localhost:6111/api",
  "code_extractor": {
    "enabled_tools": [
      "extract",
      "llm_select",
      "pdf_to_image"
    ],
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
      "llm_select_tool": {
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
        "dpi": 150
      }
    }
  }
}
```

### code_extractor 配置示例（按工具拆分）

如果提取程序依赖 `extract` / `llm_select` / `pdf_to_image` 等工具，应该在 xdev 配置里显式配置 `code_extractor`。`xdev run` / `xdev eval` 会自动读取配置并把 `tool_hub` 注入到 `extract(document, tool_hub)`，不要在 `program.py` 中自行读取 xdev 配置。

仅启用 `extract`：

```json
{
  "code_extractor": {
    "enabled_tools": ["extract"],
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
      }
    }
  }
}
```

仅启用 `llm_select`：

```json
{
  "code_extractor": {
    "enabled_tools": ["llm_select"],
    "tool_setup": {
      "llm_select_tool": {
        "llm": {
          "type": "openai",
          "config": {
            "api_key": "YOUR_API_KEY",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4o-mini"
          }
        },
        "max_content_length": 12000
      }
    }
  }
}
```

仅启用 `pdf_to_image`：

```json
{
  "code_extractor": {
    "enabled_tools": ["pdf_to_image"],
    "tool_setup": {
      "pdf_to_image_tool": {
        "dpi": 180
      }
    }
  }
}
```

字段映射关系：
- `code_extractor.tool_setup` → `code_executor.tools.tool_setup.settings.Settings.tool_setup`
- `code_extractor.enabled_tools` → `code_executor.tools.tool_setup.settings.Settings.enabled_tools`

`enabled_tools` 可选值：
- `extract`
- `llm_select`
- `pdf_to_image`

环境变量支持说明：
- 顶层字段支持 `XDEV_*`：`data_dir` / `base_url` / `concurrent` / `pdf_parse_concurrent` / `memect_api_base`
- `code_extractor` 当前仅支持在 JSON 配置文件中设置，不支持 `XDEV_*` 环境变量

生效时机：
- `xdev run` / `xdev eval` 在执行前会先应用这套配置，再加载并运行 `program.py`

### pdf-ai-explorer 配置（独立于 xdev）

`pdf-ai-explorer` 的配置不在 `.xdev/config.json`，它有自己的配置源：

```toml
# ~/.config/pdf-ai-explorer/config.toml
api_url = "http://localhost:6111/api"
```

或使用环境变量：

```bash
export MEMECT_API_URL="http://localhost:6111/api"
```

优先级：
- 代码参数 override（如果通过 SDK/MCP 传入）
- 环境变量 `MEMECT_API_URL`
- 配置文件 `~/.config/pdf-ai-explorer/config.toml`
- 默认值 `http://localhost:6111/api`

建议：
- 将 `MEMECT_API_URL` 与 `XDEV_MEMECT_API_BASE` 配成同一个地址，避免 `xdev import-data --pdfs` 和 `pdf-ai-explorer` 使用不同解析服务。

## 快速开始

### 1. 初始化 workspace

```bash
xdev init my_workspace
cd my_workspace
```

创建的目录结构：
```
my_workspace/
├── .git/                   # git 仓库
├── .gitignore
├── .xdev/                  # 数据目录（空）
├── program.py              # 提取代码模板
├── tests/                  # 测试模板
│   ├── conftest.py
│   └── test_extract.py
└── docs/                   # 空文档目录（可选）
```

### 2. 导入数据

```bash
# 从远程标准集导入
xdev import-data --set-id <标准集ID>

# 或从本地 PDF 目录导入
xdev import-data --pdfs /path/to/pdfs/

# 或从另一个 .xdev 目录导入
xdev import-data --from-data-dir /path/to/.xdev/
```

### 3. 查看数据

```bash
# 列出所有文档
xdev list

# 查看文档内容
xdev doc <doc_id>
```

### 4. 定义 schema

编辑 `.xdev/schema.json`：

```json
{
  "type": "object",
  "data": {
    "公司名称": "str",
    "注册资本": "float",
    "成立日期": "str"
  }
}
```

### 5. 编写提取代码

编辑 `program.py`，实现 `extract()` 函数。

`xdev` 仅支持 Document 输入，入口签名应为：

```python
from code_executor.document.models import Document
from code_executor.tools import ToolHub
from typing import Any

def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any] | list[dict[str, Any]]:
    ...
```

不要使用 `extract(article: list[str|Table])`。

### 6. 测试和评估

```bash
# 单文档测试
xdev run <doc_id>

# 全量评估（需要先标注数据）
xdev eval
```

## 数据目录结构

数据目录默认为 `.xdev`，在 workspace 内工作时无需指定。

```
.xdev/
├── config.json                # 项目配置（可选）
├── manifest.json              # 数据源元信息（import 时生成，只读）
├── schema.json                # Schema 定义（直接编辑文件）
├── data/
│   ├── docjson/
│   │   ├── <doc_id>.json      # DocJSON 文件（PDF 解析结果）
│   │   └── ...
│   └── pdf/
│       ├── <doc_id>.pdf       # 原始 PDF 文件
│       └── ...
└── labels/
    ├── <doc_id>.json          # 每个文档的标注（直接编辑文件）
    └── ...
```

### 关键约定

1. **doc_id = 文件名（不含扩展名）**：`data/docjson/report_001.json` → doc_id 为 `report_001`
2. **PDF 与 DocJSON 配对**：同一 doc_id 的 PDF 和 DocJSON 必须同时存在
3. **标注文件独立**：每个文档一个标注文件 `labels/<doc_id>.json`
4. **schema.json 和标注文件直接编辑**：xdev 不提供写入命令，通过文件写入工具操作

## CLI 命令

### `xdev init` — 初始化 workspace

```bash
xdev init [workspace_path]
```

创建 workspace 目录结构（git 仓库 + 模板文件 + .xdev/ 空目录）。

### `xdev import-data` — 导入数据

四种数据源互斥，必须且只能指定一种：

```bash
xdev import-data --set-id <id>              # 远程标准集
xdev import-data --pdfs <dir>               # 本地 PDF 目录（并发解析）
xdev import-data --from-data-dir <path>     # 从另一个 .xdev 目录
xdev import-data --source <source.json>     # 从配置文件
```

### `xdev sync-pdfs` — 同步 PDF 目录

```bash
xdev sync-pdfs <pdf_dir>
```

保持 `.xdev/data/` 与源 PDF 目录同步：
- **新增**：源目录有、`.xdev/data/` 没有 → 解析并添加
- **删除**：源目录没有、`.xdev/data/` 有 → 删除 docjson 和 pdf（保留 label）
- **修改**：PDF 文件 hash 变化 → 重新解析
- **manifest 更新**：更新 `source.pdf_dir` 路径和 `doc_count`

前提：`manifest.json` 必须存在且 `source.type` 为 `"pdfs"`。

输出示例：
```
[sync-pdfs] 同步 PDF: /path/to/pdfs
[sync-pdfs] 检查变更...
[sync-pdfs] 新增: 3 篇
[sync-pdfs] 删除: 1 篇 (保留 label)
[sync-pdfs] 修改: 2 篇 (重新解析)
[sync-pdfs] 不变: 15 篇
[sync-pdfs] 完成。当前文档数: 19
```

### `xdev list` — 列出文档

```bash
xdev list
```

输出数据源信息和所有 doc_id。

### `xdev doc <doc_id>` — 查看文档内容

```bash
xdev doc <doc_id>
```

输出 DocJSON 转换后的纯文本（Markdown 格式）。长文档会截断并提示 docjson 路径，此时使用 `pdf-ai-explorer` 导航。

### `xdev label-guide` — 标注指导

```bash
xdev label-guide                # 通用指导（schema 信息、标注目录、格式说明）
xdev label-guide <doc_id>       # 特定文档（文件路径和标注模板）
```

前提：`schema.json` 必须已存在。

### `xdev label-status` — 检查标注状态

```bash
xdev label-status              # 输出标注状态摘要
xdev label-status --detail     # 输出详细信息（列出每个问题文档）
```

检查当前标注完整性和 schema 一致性：
- 哪些文档已标注、哪些未标注
- 已标注文档的 key 是否与 schema 一致（缺少/多余字段）
- 已标注文档的值类型是否正确

前提：`schema.json` 必须已存在。

### `xdev eval` — 运行评估

```bash
xdev eval                       # 全量评估（所有已标注文档）
xdev eval <doc_id>              # 单文档评估
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--workspace PATH` | workspace 目录（包含 program.py） | 当前目录 |

前提：schema.json + labels/ 标注 + program.py 必须存在。
并且 `program.py` 必须使用 Document 输入（`extract(document: Document, tool_hub: ToolHub)`）。
如配置了 `code_extractor`，会在评估前构造 ToolHub 并注入给 `program.py`。

### `xdev run <doc_id>` — 执行提取

```bash
xdev run <doc_id>
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--workspace PATH` | workspace 目录（包含 program.py） | 当前目录 |

在单文档上执行 `program.py`，输出提取结果 JSON 和程序 stdout。
`program.py` 必须使用 Document 输入（`extract(document: Document, tool_hub: ToolHub)`）。
如配置了 `code_extractor`，会在执行前构造 ToolHub 并注入给 `program.py`。

### `xdev export-skills` — 导出 skills

```bash
xdev export-skills -o skills.zip        # 导出到指定文件
xdev export-skills --output-dir ./dist/ # 导出到目录（自动命名）
xdev export-skills                      # 导出到当前目录
```

导出外部可用 skills（xdev、pdf_ai_explorer、extract_workflow、fact-extract）到 ZIP 文件，供其他 coding agent 使用。

## 文件格式规范

### schema.json

定义提取目标的字段结构。

**单条记录（object）**：每篇文档提取一条记录。
```json
{"type": "object", "data": {"公司名称": "str", "注册资本": "float", "成立日期": "str"}}
```

**多条记录（list_of_objects）**：每篇文档提取多条同类记录。
```json
{"type": "list_of_objects", "data": {"股东名称": "str", "持股比例": "float"}}
```

**字段类型**：`"str"` / `"int"` / `"float"` / `"bool"` / `"list"`

**约束**：只支持扁平一层结构，不支持嵌套。

### labels/\<doc_id\>.json

每个文档的标注数据。

**object 模式**：
```json
{"公司名称": "XX科技有限公司", "注册资本": 1000.0, "成立日期": "2020-01-15"}
```

**list_of_objects 模式**：
```json
[{"股东名称": "张三", "持股比例": 30.0}, {"股东名称": "李四", "持股比例": 20.0}]
```

**约束**：
- 标注的 key 必须与 `schema.json` 的 `data` key 完全一致
- 缺失信息标注为空字符串 `""` 或 `null`
- 文件名（不含 `.json`）必须对应已有的 doc_id

### manifest.json

import 时自动生成，记录数据来源，**不应手动修改**。

## Python API

```python
from xdev.api import (
    list_doc_ids,           # 列出所有 doc_id
    get_docjson_path,       # 获取 docjson 文件路径
    get_pdf_path,           # 获取 PDF 文件路径
    get_label_path,         # 获取标注文件路径
    get_label,              # 读取标注数据
    list_labeled_doc_ids,   # 列出已标注的 doc_id
    get_schema,             # 读取 schema
    get_manifest,           # 读取 manifest
    check_label_status,     # 检查标注状态，返回 LabelStatusReport
    LabelStatusReport,      # 标注状态报告
    LabelIssue,             # 单个标注问题
)

from xdev.import_data import (
    sync_pdfs,              # 同步 PDF 目录，返回 SyncResult
    add_pdfs,               # 增量添加 PDF
    reparse_docs,           # 重新解析文档
    SyncResult,             # 同步结果（added, removed, modified, unchanged）
)
```

所有函数都接受 `data_dir` 参数，默认为 `.xdev`。

## 配套 Skills

xdev 是数据管理和评估的基础工具。完整的提取开发流程需要配合以下 skills：

| Skill | 说明 |
|-------|------|
| **extract_workflow** | 完整的提取开发工作流（数据分析 → schema → 标注 → 编码 → 评估迭代），开始提取任务时先加载此 skill |
| **pdf_ai_explorer** | 长文档导航工具，`xdev doc` 截断时用它按需导航大纲、搜索、翻页 |
| **fact-extract** | 单文档/多文档 PDF 事实抽取工作流（计划 → 并发抽取 → 合并），用户说”提取 fact”时优先使用 |

## 关系提取（enrich）

`fact-extract enrich` 是事实提取的后处理阶段，从已提取的事实中抽取结构化知识：**实体、属性、关系、事件**。

### 前置条件

需要先完成事实提取（`fact-extract run`），产生 `manifest.json` 和 `sources/` 目录。

### CLI 用法

```bash
# 对 manifest 进行 enrich
fact-extract enrich \
  --manifest <FACTS_DIR>/manifest.json \
  --model <MODEL> \
  --api-base <API_BASE> \
  --api-key <API_KEY> \
  --max-workers 32

# 或对 chunks 进行 enrich
fact-extract enrich \
  --chunks <FACTS_DIR>/chunks.json \
  --max-workers 32
```

`--manifest` 和 `--chunks` 二选一。

### 输出

- 中间产物：`<FACTS_DIR>/enriched/<fact_id>.json`（逐条保存，支持断点续跑）
- 最终输出：`<FACTS_DIR>/manifest.enriched.json`（manifest 模式）或 `<FACTS_DIR>/enriched.json`（chunks 模式）

### 提取的四类知识

每条事实会被扩充以下四个字段：

```json
{
  “id”: “fact_0001”,
  “summary”: “孙悟空大闹天宫，打败十万天兵”,
  “source_ids”: [“e0001”],
  “entities”: [
    {“name”: “孙悟空”, “type”: “人物”},
    {“name”: “天宫”, “type”: “地点”}
  ],
  “attributes”: [
    {“entity”: “孙悟空”, “attr”: “能力”, “value”: “七十二变”}
  ],
  “relations”: [
    {“subject”: “孙悟空”, “predicate”: “大闹”, “object”: “天宫”},
    {“subject”: “孙悟空”, “predicate”: “打败”, “object”: “十万天兵”}
  ],
  “events”: [
    {“action”: “大闹天宫”, “agent”: “孙悟空”, “patient”: “天兵天将”, “location”: “天宫”, “time”: null}
  ]
}
```

### 典型流程

```bash
# 1. 事实提取
fact-extract run --pdf book.pdf --facts-dir facts

# 2. 关系提取（enrich）
fact-extract enrich --manifest facts/manifest.json

# 3. 查看结果
jq '.[0] | {summary, entities, relations}' facts/manifest.enriched.json
```

### 断点续跑

enrich 支持断点续跑：`enriched/` 目录下已完成的 fact 会跳过，中断后重跑只处理剩余部分。
