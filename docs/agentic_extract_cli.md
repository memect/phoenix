# agentic-extract CLI

这份文档只覆盖命令行最常用的信息：

- 安装
- quickstart
- `agentic-extract run`
- `agentic-extract auto`
- budget / 迭代次数控制

## 安装

```bash
uv tool install extract-agent
```

安装后会同时暴露这些命令：

- `agentic-extract`
- `xdev`
- `xdev-config`
- `pdf-ai-explorer`
- `tree-sitter-cli`

## 配置

最简单的方式是直接运行：

```bash
xdev-config
```

它会同时写入全局 `agentic-extract` / `xdev` 配置。

## 快速开始

如果你已经有一批本地 PDF，最短路径是：

```bash
agentic-extract auto --workspace ws --pdfs-dir ../pdfs --message '随便提点东西'
```

本地 PDF 会通过 `ppx parse` 生成 DocJSON；批量解析并发由 xdev 的 `pdf_parse_concurrent` / `XDEV_PDF_PARSE_CONCURRENT` 控制。

继续在同一个 workspace 上迭代：

```bash
agentic-extract run --workspace ws --message '再提一个字段'
```

如果你更喜欢先用 `xdev` 手动整理数据，也可以：

```bash
xdev init ws
cd ws
xdev import-data --pdfs ../pdfs
agentic-extract run --workspace .
```

## `agentic-extract run`

`run` 是纯运行命令。

适用场景：

- workspace 已经有可运行的 `.xdev` 数据
- 你只想继续迭代，不想重新准备数据
- 默认 supervisor 使用 `simple` 模式

最小示例：

```bash
agentic-extract run --workspace /path/to/workspace
```

运行时默认会把结构化事件写到：

```bash
/path/to/workspace/.agent_state/events.jsonl
```

也可以加一条初始消息：

```bash
agentic-extract run \
  --workspace /path/to/workspace \
  --message '检查还有哪些字段提取不稳定'
```

## `agentic-extract auto`

`auto` 是一键准备加运行命令。

适用场景：

- 第一次创建 workspace
- 想直接从数据源开始跑
- 默认 supervisor 使用 `simple` 模式

从 PDF 目录启动：

```bash
agentic-extract auto \
  --workspace /path/to/workspace \
  --pdfs-dir /path/to/pdfs
```

该路径要求本机 `ppx` 命令可用。

从远程标准集启动：

```bash
agentic-extract auto \
  --workspace /path/to/workspace \
  --set-id <set-id>
```

## budget 与迭代次数控制

默认预算相当于 `standard`：

- `max_iterations = 10`
- `agent_max_iters = 25`

如果想把单个 agent 的内部迭代数收紧到更小，可以使用：

```bash
agentic-extract run --workspace /path/to/workspace --budget fast
```

`--budget fast` 会展开成：

- `max_iterations = 10`
- `agent_max_iters = 10`

如果想放宽预算，可以使用：

```bash
agentic-extract run --workspace /path/to/workspace --budget full
```

`--budget full` 会展开成：

- `max_iterations = 50`
- `agent_max_iters = 100`

如果你需要更细的控制，可以显式覆盖：

- `--max-iterations`
- `--agent-max-iters`
- `--supervisor-max-iters`
- `--business-max-iters`
- `--dev-max-iters`

常见例子：

```bash
# 默认预算运行
agentic-extract run --workspace /path/to/workspace

# 使用 fast，保持总轮数 10，但把单个 agent 限制到 10 轮
agentic-extract run --workspace /path/to/workspace --budget fast

# 放宽到 full
agentic-extract run --workspace /path/to/workspace --budget full

# full，但总轮数收紧
agentic-extract run --workspace /path/to/workspace --budget full --max-iterations 8

# 单独放宽 dev agent
agentic-extract run --workspace /path/to/workspace --dev-max-iters 40

# 严格控制总量
agentic-extract run \
  --workspace /path/to/workspace \
  --max-iterations 5 \
  --agent-max-iters 12
```

预算参数含义：

- `max_iterations`：workflow 外层最大轮数
- `agent_max_iters`：单个 agent 一次调用内部的默认最大迭代次数
- `supervisor_max_iters` / `business_max_iters` / `dev_max_iters`：按 agent 单独覆盖
