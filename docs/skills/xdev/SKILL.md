---
name: xdev
description: 当用户需要准备或维护 workspace 数据、导入或同步 PDF、查看文档、定义 schema、管理标注、调试 program.py、或运行评估时使用此 skill。如果用户只是想启动 agentic loop 或通过 Python API 一键运行完整流程，转到 agentic-extract skill。
---

# xdev

`xdev` 负责 workspace 的数据层。

## 前置检查

开始前先确认当前环境至少能满足本次任务。

### 命令

至少检查：

```bash
xdev --help
```

如果任务里会阅读超长文档，再额外检查：

```bash
pdf-ai-explorer --help
```

如果 `xdev` 不可用，先安装：

```bash
uv tool install extract-agent
```

`extract-agent` 发布到 PyPI，默认安装命令不需要指定私有 index。

### 配置

`xdev` 配置来源：

- 全局配置：`~/.config/xdev/config.json`
- 项目配置：`$CWD/.xdev/config.json`
- 环境变量：`XDEV_*`

按任务区分最小配置：

- 只看已有 `.xdev` 数据：通常只要命令可用
- `xdev import-data --set-id`：需要 `base_url`，可放配置里或命令行传 `--base-url`
- `xdev import-data --pdfs` / `xdev sync-pdfs`：需要本机 `ppx` 命令；`pdf_parse_concurrent` 控制批量 PDF 解析并发
- `program.py` 使用 code tools：需要在 `.xdev/config.json` 里显式配置 `code_extractor`，xdev 会把 `tool_hub` 注入到 `extract(document, tool_hub)`

常用环境变量：

- `XDEV_BASE_URL`
- `XDEV_PDF_PARSE_CONCURRENT`
- `XDEV_MEMECT_API_BASE`
- `XDEV_DATA_DIR`

最小验证：

- 已有本地数据时，运行 `xdev list`
- 准备跑长文档分析时，确认 `pdf-ai-explorer --help`

优先在这些场景使用本 skill：

- 创建或检查 workspace
- 导入数据到 `.xdev/`
- 增量添加 PDF 或同步 PDF 目录
- 查看文档内容、schema、标注状态
- 编写或调试 `program.py`
- 运行单文档提取或评估

不要把下面这些事放在本 skill 里：

- 解释 `agentic-extract run` / `agentic-extract auto` 的迭代逻辑
- 解释 Python callback、heartbeat、progress event
- 把“数据准备 + 运行”重新揉成一个大工作流

## 先做判断

- 如果 workspace 还没准备好，先读 [references/workspace.md](references/workspace.md)
- 如果需要导入或同步数据，读 [references/import.md](references/import.md)
- 如果需要看文档、写 schema、补标注，读 [references/inspect_and_label.md](references/inspect_and_label.md)
- 如果需要调试 `program.py` 或做评估，读 [references/run_and_eval.md](references/run_and_eval.md)
- 如果 `.xdev` 已经准备好，用户要启动 agentic 迭代，切到 `agentic-extract` skill

## 工作原则

- `workspace` 是长期目录，不是一次性运行目录
- `.xdev/` 是数据层，`program.py` 是提取实现，`.agent_state/` 是运行态
- 日常推荐顺序是：先用 `xdev` 管数据，再用 `agentic-extract run` 做迭代
- `agentic-extract auto` 只是 one-click 入口，不替代日常的数据维护
- 文档过长时，不要只盯着 `xdev doc` 的截断输出；应切到 `pdf-ai-explorer`

## 最短路径

1. `xdev init /path/to/workspace`
2. `cd /path/to/workspace`
3. 用 `xdev import-data` 或 `xdev sync-pdfs` 准备 `.xdev`
4. 用 `xdev list` / `xdev doc` / `xdev label-guide` / `xdev label-status` 理解数据和标注状态
5. 修改 `program.py`
6. 用 `xdev run <doc_id>` 做单文档调试
7. 用 `xdev eval` 做评估
8. 如果数据已准备好，且用户要跑 agentic loop，切到 `agentic-extract` skill
