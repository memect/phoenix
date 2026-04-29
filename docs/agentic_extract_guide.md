# agentic-extract 使用指南

`agentic_extract` 现在分成两层：

- 低层 pure run：只负责运行 agent loop，不负责准备数据
- 高层 one-click：先按需准备 `.xdev` 数据，再运行 agent loop

如果你只是想直接管理数据，请用 `xdev`；如果你想跑完整的 agentic 提取流程，再用 `agentic-extract`。

## 相关文档

- [workspace 简短使用流程](./workspace_quick_flow.md)
- [agentic-extract Python API 使用说明](./agentic_extract_api_guide.md)
- [agent skill: xdev](./skills/xdev/SKILL.md)
- [agent skill: agentic-extract](./skills/agentic-extract/SKILL.md)
- [agent skill: pdf-ai-explorer](./skills/pdf-ai-explorer/SKILL.md)

## 能力边界

| 入口 | 适用场景 | 是否准备数据 |
|------|----------|--------------|
| `agentic-extract run` | workspace 已经有可运行 `.xdev` 数据 | 否 |
| `agentic-extract auto` | 希望一键 bootstrap + run | 是 |
| `run_agentic_extract()` | 外部 Python 程序已拿到最终 settings | 否 |
| `run_agentic_extract_auto()` | 外部 Python 程序希望一键调用完整流程 | 是 |
| `xdev import-data` / `xdev sync-pdfs` | 单独导入、增量维护、同步数据 | 仅数据层 |

当前语义已经定死：

- `agentic-extract run` 是纯运行命令
- `agentic-extract auto` 是一键准备加运行命令
- `add_pdf` / `sync_pdfs` 属于 `xdev`，不再属于 `agentic-extract`

## 配置解析规则

`agentic_extract.config.resolve_settings()` 和 CLI 走同一套配置解析逻辑。

优先级从低到高：

1. 内置默认值
2. 全局配置：`~/.config/agentic-extract/config.json`
3. 当前工作目录配置：`$CWD/.agentic-extract.json`
4. workspace 向上到 repo 根目录的配置文件：
   - `<repo_root>/.agentic-extract.json`
   - ...
   - `<workspace>/.agentic-extract.json`
5. 显式 `config_path`
6. 环境变量：`AE_*`
7. 显式 overrides / CLI 参数

说明：

- 保留 `cwd` 配置查找，是为了兼容“项目根统一放配置、不想在 workspace 暴露 API key”的用法
- workspace 配置查找会一直找到 repo 根目录
- `run_agentic_extract_auto()` 不要求调用方自己先解析配置；它会自动解析，也允许通过 `config_path` 和 `settings_overrides` 覆盖

常用环境变量：

- `AE_MODEL`
- `AE_API_BASE`
- `AE_API_KEY`
- `AE_MAX_ITERATIONS`
- `AE_TARGET_ACCURACY`
- `AE_RUN_TIMEOUT`
- `AE_API_TIMEOUT`
- `AE_REASONING_EFFORT`

## CLI 接口

### `agentic-extract run`

纯运行模式。要求 workspace 已具备可运行的 `.xdev` 数据。

```bash
agentic-extract run \
  --workspace /path/to/workspace \
  --model openai/gpt-4.1 \
  --api-base https://api.openai.com/v1 \
  --api-key "$OPENAI_API_KEY"
```

常用参数：

- `--workspace`：workspace 路径
- `--config`：显式配置文件路径
- `--model` / `--api-base` / `--api-key`
- `--supervisor-model` / `--business-model` / `--dev-model`
- `--max-iterations`
- `--target-accuracy`
- `--run-timeout`
- `--api-timeout`
- `--heartbeat-interval-sec`
- `--dry-run`：只校验配置、workspace readiness 和 API 连通性
- `--reset`：运行前清除 `.agent_state/`，并兼容清理旧版 `logs/` 运行状态
- `--supervisor default|simple`（默认 `simple`）

`run` 不再接受这些旧的数据准备参数：

- `--set-id`
- `--std-ids`
- `--std-ids-file`
- `--limit`
- `--base-url`
- `--pdfs-dir`
- `--data-dir`
- `--source-file`

使用 `--pdfs-dir` 时，本地 PDF 会通过 `ppx parse` 生成 DocJSON；批量解析并发由 xdev 的 `pdf_parse_concurrent` / `XDEV_PDF_PARSE_CONCURRENT` 控制。
- `--add-pdf`
- `--force`
- `--sync-pdfs`

如果仍然传这些参数，CLI 会直接报错，并提示你改用 `agentic-extract auto` 或 `xdev`。

### `agentic-extract auto`

高层 one-click 模式。先决定是否需要 bootstrap workspace 数据，再运行 agent loop。

```bash
agentic-extract auto \
  --workspace /path/to/workspace \
  --set-id c84ee54b-cc83-4d6d-b79f-f9268b3e32ed \
  --model openai/gpt-4.1 \
  --api-base https://api.openai.com/v1 \
  --api-key "$OPENAI_API_KEY"
```

可选的数据来源参数，互斥，只能指定一个：

- `--set-id`
- `--pdfs-dir`
- `--data-dir`
- `--source-file`

其中 `--set-id` 还支持：

- `--std-ids`
- `--std-ids-file`
- `--limit`
- `--base-url`

示例：

```bash
# 复用已有 workspace 数据，只负责运行
agentic-extract auto --workspace /path/to/workspace

# 首次从远程标准集 bootstrap
agentic-extract auto --workspace /path/to/workspace --set-id <id>

# 从另一个 .xdev 复制数据后运行
agentic-extract auto --workspace /path/to/workspace --data-dir /path/to/other/.xdev

# 从 PDF 目录初始化后运行
agentic-extract auto --workspace /path/to/workspace --pdfs-dir /path/to/pdfs
```

行为规则：

- workspace 没有可运行数据时，如果提供了 prepare source，会执行 bootstrap
- workspace 已有数据且与 prepare source 可证明同源时，会直接复用
- workspace 已有数据但传入了不同来源时，会报错，避免误覆盖
- `--dry-run` 只做 prepare 判定和 API 连通性验证，不实际导入数据
- `--reset` 只清运行期状态，不删除 `.xdev` 数据

## 执行时长控制

推荐优先使用“迭代预算”控制执行时长：

- 默认预算相当于 `standard`：
  - `max_iterations = 10`
  - `agent_max_iters = 25`
- `--budget fast`：保持 workflow 外层 10 轮，但把单个 agent 收紧到更小预算
  - `max_iterations = 10`
  - `agent_max_iters = 10`
- `--max-iterations`：workflow / supervisor 外层最大轮数
- `--agent-max-iters`：三个 agent 单次调用内部默认最大迭代次数
- `--supervisor-max-iters` / `--business-max-iters` / `--dev-max-iters`：按 agent 单独覆盖
- `--budget full`：放宽到更宽松的预算
  - `max_iterations = 50`
  - `agent_max_iters = 100`

示例：

```bash
agentic-extract run \
  --workspace /path/to/workspace \
  --max-iterations 6 \
  --agent-max-iters 8

agentic-extract run \
  --workspace /path/to/workspace \
  --budget fast

agentic-extract auto \
  --workspace /path/to/workspace \
  --set-id <id> \
  --budget full
```

`--run-timeout` 当前仍然保留，但它是轮间检查的兜底超时，不会强制中断一个已经在执行中的长步骤；如果想更稳定地控制执行时长，优先调小迭代预算。

## 运行状态文件

运行期 bookkeeping 统一写入 `.agent_state/`：

- `.agent_state/current.json`：最近一次运行的粗粒度状态与迭代计数
- `.agent_state/iterations/iter_NNN.json`：每轮迭代记录
- `.agent_state/events.jsonl`：结构化事件流，包含 workflow 进度事件、prepare 事件和 agent 详细消息
- `.agent_state/*.json`：agent memory 等内部状态

为了兼容已有 workspace，读取时仍兼容旧版 `logs/current.json` 与
`logs/iterations/iter_NNN.json`。

### `agentic-extract resume`

从指定迭代的 git commit 创建新分支恢复：

```bash
agentic-extract resume --workspace /path/to/workspace --from-iteration 3
```

### `agentic-extract export-prompts`

导出当前组装后的提示词，便于查看和审阅：

```bash
agentic-extract export-prompts --agent all --output local/prompts/
agentic-extract export-prompts --agent supervisor --output -
```

## Python API

### 低层 API：`run_agentic_extract()`

低层 API 接受最终 `AgenticExtractSettings`，不做数据准备。

```python
from agentic_extract import run_agentic_extract
from agentic_extract.config import resolve_settings


def on_event(event):
    print(event.type, event.iteration, event.step, event.elapsed_total_run_sec)


settings = resolve_settings(
    "/path/to/workspace",
    overrides={
        "model": "openai/gpt-4.1",
        "api_base": "https://api.openai.com/v1",
        "api_key": "...",
        "max_iterations": 10,
        "agent_max_iters": 25,
    },
)

result = run_agentic_extract(
    settings,
    on_event=on_event,
    heartbeat_interval_sec=10.0,
)

print(result.status)
print(result.iteration_count)
print(result.total_run_duration_sec)
print(result.token_usage.total_tokens)
```

异步版本：

- `run_agentic_extract_async()`

同步版本不能在已有 event loop 中直接调用；如果你已经在 async 环境里，请用 async 版本。

### 高层 API：`run_agentic_extract_auto()`

高层 API 负责：

1. 自动解析配置
2. 判断 workspace 是否已有可运行 `.xdev` 数据
3. 必要时执行 bootstrap
4. 调用低层 run

```python
from agentic_extract import run_agentic_extract_auto
from agentic_extract.types import PrepareSourceSetId, PrepareSpec


def on_event(event):
    if event.type == "heartbeat":
        print("heartbeat", event.elapsed_total_run_sec, event.token_usage_total.total_tokens)


result = run_agentic_extract_auto(
    "/path/to/workspace",
    prepare=PrepareSpec(
        source=PrepareSourceSetId(
            set_id="c84ee54b-cc83-4d6d-b79f-f9268b3e32ed",
            std_ids=["doc-1", "doc-2"],
            limit=2,
        )
    ),
    config_path="/path/to/.agentic-extract.json",
    settings_overrides={
        "max_iterations": 50,
        "agent_max_iters": 100,
        "supervisor_mode": "simple",
    },
    on_event=on_event,
    heartbeat_interval_sec=5.0,
)
```

异步版本：

- `run_agentic_extract_auto_async()`

高层 API 的 `prepare` 类型：

- `PrepareSourceExisting`
- `PrepareSourceSetId`
- `PrepareSourcePdfDir`
- `PrepareSourceDataDir`
- `PrepareSourceConfigFile`

推荐规则：

- 外部程序已经有最终 settings，就用低层 API
- 外部程序想“一键调用完整流程”，就用高层 API

### 兼容 API

以下接口仍然保留，但已经标记为 deprecated：

- `run_agentic_extract_request()`
- `run_agentic_extract_request_async()`
- `RunRequest`

新代码不要再基于 `RunRequest` 组装请求；请改用：

- 低层：`AgenticExtractSettings`
- 高层：`run_agentic_extract_auto(..., prepare=..., settings_overrides=...)`

## 进度事件与返回结果

`on_event` callback 会收到稳定的粗粒度事件 `ProgressEvent`。

事件类型：

- `run_started`
- `phase_started`
- `phase_completed`
- `iteration_started`
- `supervisor_decided`
- `step_started`
- `step_completed`
- `heartbeat`
- `iteration_completed`
- `run_completed`
- `run_failed`

常用字段：

- `iteration`
- `step`
- `status`
- `message`
- `elapsed_step_sec`
- `elapsed_iteration_sec`
- `elapsed_total_iteration_sec`
- `elapsed_total_run_sec`
- `token_usage_delta`
- `token_usage_total`
- `data`

约定：

- `heartbeat` 是第一版必需能力，长步骤执行期间会周期性发出
- `supervisor_decided` 和 `iteration_completed` 的 `data["action"]` 表示本轮决策
- `run_completed` / `run_failed` 的 `data["iteration_count"]` 表示总轮数
- 事件设计目标是“稳定的粗粒度接口”，调用方不要依赖内部细碎实现细节

CLI / API 默认还会把更完整的结构化事件写入 `workspace/.agent_state/events.jsonl`。

其中除了上述粗粒度 `ProgressEvent`，还包括：

- `settings_resolved`
- `prepare_decided` / `prepare_started` / `prepare_completed` / `prepare_failed`
- `agent_call_started` / `agent_call_completed`
- `agent_message`

`agent_message` 会记录 agent 的详细消息块（包括 print、observe 和部分内部 system notice），适合排障和回放。

`TokenUsage` 字段：

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cached_input_tokens`
- `reasoning_output_tokens`
- `details_complete`

最终返回 `RunResult`，包含：

- `status`
- `iteration_count`
- `total_iteration_duration_sec`
- `total_run_duration_sec`
- `token_usage`
- `iteration_token_usage`
- `iterations`
- `error`

其中：

- `IterationResult.duration_sec` 表示整轮迭代的完整 wall-clock 时间
- `RunResult.total_iteration_duration_sec` 是所有已完成迭代时长之和
- `RunResult.total_run_duration_sec` 包括 setup、probe、iteration、finalize 在内的整次运行总耗时

## 提示词放哪里

提示词素材在 `src/agentic_extract/prompts/` 下，主要包括：

- `supervisor.py`
- `supervisor_simple.py`
- `business.py`
- `extract_dev.py`
- `xdev.py`
- `tools/`
- `assembly.py`

如果要查看“最终组装后的 prompt”，不要手工拼，直接用：

```bash
agentic-extract export-prompts --agent all --output local/prompts/
```

## 与 xdev 的关系

`agentic_extract` 负责 agent loop、运行期事件、token 统计和最终评估反馈。

`xdev` 负责数据层动作：

- `xdev import-data`
- `xdev import-data --add-pdf`
- `xdev import-data --reparse`
- `xdev sync-pdfs`
- `xdev fix-symlinks`

如果你只是想导数据、补 PDF、重解析、同步 PDF，不要走 `agentic-extract`，直接走 `xdev`。
