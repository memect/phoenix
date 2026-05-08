<div align="center">

# Phoenix

[![PyPI version](https://img.shields.io/pypi/v/extract-agent)](https://pypi.org/project/extract-agent/) [![Python](https://img.shields.io/pypi/pyversions/extract-agent)](https://pypi.org/project/extract-agent/) [![Python Package](https://img.shields.io/github/actions/workflow/status/memect/phoenix/python-package.yml?branch=main&label=Python%20Package)](https://github.com/memect/phoenix/actions/workflows/python-package.yml) [![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm%20Noncommercial-blue.svg)](LICENSE)

</div>

## 说明

Phoenix 是面向文档结构化提取任务的自动迭代 Agent 工具链。

它不是一次性让大模型抽字段，而是把一批 PDF 转成 DocJSON 后，在同一个 workspace 中自动完成：

- 业务归纳：BusinessAgent 阅读样本，沉淀 `business_guide.md`、`.xdev/schema.json` 和 `.xdev/labels/`
- 程序生成：DevAgent 编写和修正 `program.py`
- 评估反馈：`xdev evaluate` 对提取结果和 labels 做对比
- 迭代记忆：`.agent_state` 保存每轮决策、事件流、评估快照和 Agent 会话状态


## 安装

要求：Python >= 3.12，推荐先安装 [uv](https://docs.astral.sh/uv/)。

快速安装：

```bash
curl -fsSL https://raw.githubusercontent.com/memect/phoenix/main/scripts/install.sh | bash
```

> 脚本会用 uv tool install 安装 extract-agent，并把 ppx 安装到独立虚拟环境后写入 PATH。

## 源代码方式

```bash
git clone https://github.com/memect/phoenix.git
cd phoenix
bash scripts/install.sh
```

开发安装：

```bash
uv sync
uv run agentic-extract --help
uv run xdev --help
```

## 配置

推荐使用交互式配置：

```bash
xdev-config
```

配置会写入：

- `~/.config/agentic-extract/config.json`
- `~/.config/xdev/config.json`

查看当前配置：

```bash
xdev-config --show
```

模型角色：

- `llm`：Supervisor / BusinessAgent / DevAgent 使用的主模型，需要较强推理和代码能力
- `extract-llm`：生成的 `program.py` 在提取字段时使用
- `label-llm`：批量标注子 Agent 使用，通常需要工具调用能力

## 执行

如果不克隆仓库，先准备自己的 PDF：

```bash
agentic-extract auto \
  --workspace ws \
  --pdfs-dir examples/pdfs \
  --message '任意提取一个关键字段'
```

如果已经克隆仓库，可以直接使用真实示例 PDF：

```bash
agentic-extract auto \
  --workspace ws \
  --pdfs-dir examples/pdfs \
  --message '归纳样本文档，定义字段口径，生成并评估提取程序'
```

`auto` 会在 workspace 尚未准备好时执行 bootstrap：调用 `ppx parse` 解析 PDF，导入 `.xdev` 数据目录，然后启动 Agent 闭环。

继续迭代同一个 workspace：

```bash
agentic-extract run \
  --workspace ws \
  --message '根据最近评估结果继续修正提取逻辑，并沉淀必要的业务规则'
```

在单个新文档上复用当前提取程序：

```bash
xdev run --workspace ws --pdf examples/pdfs/1.pdf
```

也可以先准备数据，再运行 Agent：

```bash
xdev init ws
xdev import-data --pdfs examples/pdfs --data-dir ws/.xdev
agentic-extract run --workspace ws --message '开始提取'
```

常用预算：

```bash
# 快速模式：max_iterations=10, agent_max_iters=10
agentic-extract run --workspace ws --budget fast

# 充分模式：max_iterations=50, agent_max_iters=100
agentic-extract run --workspace ws --budget full
```

## Agent 迭代

Phoenix 当前由三类 Agent 和一个评估环组成：

| 角色 | 职责 |
| --- | --- |
| Supervisor | 读取最近迭代摘要、workspace 状态和评估结果，决定下一步 `call_business` / `call_dev` / `evaluate` / `done` |
| BusinessAgent | 阅读文档样本，归纳字段口径，维护 `business_guide.md`、`.xdev/schema.json` 和 labels |
| DevAgent | 根据业务口径和评估反馈编写、调试、优化 `program.py` |
| xdev eval | 执行提取程序并和 labels 对比，输出准确率、错误样本和字段表现 |

一次运行会持续沉淀：

```text
ws/
├── business_guide.md
├── program.py
├── tests/
├── docs/
├── .xdev/
│   ├── schema.json
│   ├── data/
│   └── labels/
└── .agent_state/
    ├── current.json
    ├── events.jsonl
    └── iterations/
```

这里的“记忆”是 workspace 内的运行记忆和业务沉淀，不是跨项目的通用长期记忆库。

## 命令

### agentic-extract

| 命令 | 说明 |
| --- | --- |
| `agentic-extract auto` | 一键准备数据并运行 Agent |
| `agentic-extract run` | 运行已准备好的 workspace |
| `agentic-extract resume` | 从指定迭代恢复运行并创建新 git 分支 |
| `agentic-extract export-prompts` | 导出 Agent 系统提示词 |

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--workspace` | 工作目录，默认 `workspace` |
| `--pdfs-dir` | `auto` 模式下导入本地 PDF 目录 |
| `--budget` | 预算预设：`fast` / `full` |
| `--max-iterations` | workflow 外层最大迭代次数 |
| `--agent-max-iters` | 单个 Agent 内部最大迭代次数 |
| `--dry-run` | 检查配置和 workspace，不启动循环 |
| `--reset` | 清除运行状态后重新开始 |
| `--message` | 传给 Supervisor 的初始需求 |

### xdev

| 命令 | 说明 |
| --- | --- |
| `xdev init` | 初始化 workspace |
| `xdev import-data` | 导入本地 PDF、远程标准集或其他 `.xdev` 数据 |
| `xdev list` | 列出数据目录中的文档 |
| `xdev doc <doc_id>` | 查看文档 Markdown 内容 |
| `xdev label-guide [doc_id]` | 输出标注指导 |
| `xdev run` | 使用当前 `program.py` 在 PDF/DocJSON 上执行提取 |
| `xdev evaluate` | 对当前提取程序做评估 |

## 开发

```bash
uv sync
uv run pytest
uv run agentic-extract --help
uv run xdev --help
```

主要目录：

| 路径 | 说明 |
| --- | --- |
| `src/agentic_extract/` | Agentic 提取主流程、CLI、配置和状态管理 |
| `src/xdev/` | 数据管理、workspace、评估与导入 |
| `src/code_executor/` | 提取程序执行器和文档工具 |
| `src/evaluation_engine/` | 评估引擎 |
| `examples/pdfs/` | 可直接试用的示例 PDF |
| `docs/` | 设计文档和使用说明 |
| `tests/` | 测试 |

## 常见问题

### ppx 命令不可用

先运行安装脚本，并重新加载 shell：

```bash
bash scripts/install.sh
source ~/.zshrc
ppx --help
```

### 只想检查配置

```bash
agentic-extract run --workspace ws --dry-run
```

### 想重新开始一次运行

```bash
agentic-extract run --workspace ws --reset
```

这会清理运行状态和日志，不会删除 `.xdev` 数据目录。

## 相关链接

- [更新日志](docs/CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)
- [许可证](LICENSE)
