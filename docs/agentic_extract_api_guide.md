# agentic-extract Python API 使用说明

本文档面向外部程序调用 `agentic_extract` 的 Python API。

## 推荐入口

当前推荐使用两层 API：

- 低层 API：`run_agentic_extract()`
  - 适合已经准备好 workspace 和最终配置，只想纯运行 agent loop 的场景
- 高层 API：`run_agentic_extract_auto()`
  - 适合希望一键完成“按需准备数据 + 开始运行”的场景

如果你只是想让外部程序“一键跑完整流程”，优先使用高层 API。

## 1. 低层 API：纯运行

低层 API 不负责导入数据，只负责运行。

### 同步版本

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

### 异步版本

```python
from agentic_extract import run_agentic_extract_async
from agentic_extract.config import resolve_settings


async def main():
    settings = resolve_settings(
        "/path/to/workspace",
        overrides={
            "model": "openai/gpt-4.1",
            "api_base": "https://api.openai.com/v1",
            "api_key": "...",
        },
    )
    result = await run_agentic_extract_async(
        settings,
        heartbeat_interval_sec=5.0,
    )
    print(result.status)
```

说明：

- 同步版本不能在已有 event loop 中调用。
- 如果你已经在 async 环境里，请使用 async 版本。

## 2. 高层 API：一键准备加运行

高层 API 会做这些事：

1. 解析配置
2. 判断 workspace 是否已经有可运行 `.xdev` 数据
3. 必要时执行 bootstrap
4. 调用低层运行逻辑

### 从远程标准集一键启动

```python
from agentic_extract import run_agentic_extract_auto
from agentic_extract.types import PrepareSourceSetId, PrepareSpec


def on_event(event):
    print(event.type, event.iteration, event.step, event.elapsed_total_run_sec)


result = run_agentic_extract_auto(
    "/path/to/workspace",
    prepare=PrepareSpec(
        source=PrepareSourceSetId(
            set_id="your-set-id",
        )
    ),
    settings_overrides={
        "model": "openai/gpt-4.1",
        "api_base": "https://api.openai.com/v1",
        "api_key": "...",
        "max_iterations": 50,
        "agent_max_iters": 100,
    },
    on_event=on_event,
    heartbeat_interval_sec=5.0,
)

print(result.status)
print(result.iteration_count)
```

### 从本地 PDF 目录一键启动

```python
from agentic_extract import run_agentic_extract_auto
from agentic_extract.types import PrepareSourcePdfDir, PrepareSpec


result = run_agentic_extract_auto(
    "/path/to/workspace",
    prepare=PrepareSpec(
        source=PrepareSourcePdfDir(
            pdfs_dir="/path/to/pdfs",
        )
    ),
    settings_overrides={
        "model": "openai/gpt-4.1",
        "api_base": "https://api.openai.com/v1",
        "api_key": "...",
    },
)
```

### 复用已有数据，只负责运行

```python
from agentic_extract import run_agentic_extract_auto


result = run_agentic_extract_auto(
    "/path/to/workspace",
    settings_overrides={
        "model": "openai/gpt-4.1",
        "api_base": "https://api.openai.com/v1",
        "api_key": "...",
    },
)
```

说明：

- 如果 workspace 已经有可运行数据，且未传新的数据来源，高层 API 会直接复用。
- 如果 workspace 已有数据，但你又传入了不同来源，默认会报错，避免误覆盖。
- 默认预算相当于 `standard`：`max_iterations=10`、`agent_max_iters=25`。
- 如果想保持总轮数不变但收紧单个 agent，可使用 CLI `--budget fast`，它会展开为 `max_iterations=10`、`agent_max_iters=10`。
- 如果需要更宽松预算，可使用 CLI `--budget full` 或在 API 中显式传入更大的 budget。
- 控制执行时长时，优先使用 `max_iterations`、`agent_max_iters` 和 `*_max_iters` 这类迭代预算。
- `run_timeout` 当前是轮间检查的兜底超时，不是对单个长步骤的硬中断。

## 3. prepare 参数

高层 API 的 `prepare` 使用 `PrepareSpec`。

### 复用已有数据

```python
from agentic_extract.types import PrepareSpec, PrepareSourceExisting

prepare = PrepareSpec(source=PrepareSourceExisting())
```

### 远程标准集

```python
from agentic_extract.types import PrepareSourceSetId, PrepareSpec

prepare = PrepareSpec(
    source=PrepareSourceSetId(
        set_id="your-set-id",
        std_ids=["doc-1", "doc-2"],
        limit=2,
    )
)
```

### 本地 PDF 目录

```python
from agentic_extract.types import PrepareSourcePdfDir, PrepareSpec

prepare = PrepareSpec(
    source=PrepareSourcePdfDir(
        pdfs_dir="/path/to/pdfs",
    )
)
```

### 另一个 `.xdev` 目录

```python
from agentic_extract.types import PrepareSourceDataDir, PrepareSpec

prepare = PrepareSpec(
    source=PrepareSourceDataDir(
        data_dir="/path/to/other/.xdev",
    )
)
```

### 数据源配置文件

```python
from agentic_extract.types import PrepareSourceConfigFile, PrepareSpec

prepare = PrepareSpec(
    source=PrepareSourceConfigFile(
        source_file="/path/to/source.json",
    )
)
```

## 4. 配置方式

有两种常见方式。

### 方式一：自己先解析 settings

适合低层 API。

```python
from agentic_extract.config import resolve_settings

settings = resolve_settings(
    "/path/to/workspace",
    overrides={
        "model": "openai/gpt-4.1",
        "api_base": "https://api.openai.com/v1",
        "api_key": "...",
    },
)
```

### 方式二：让高层 API 自动解析

适合高层 API。

```python
result = run_agentic_extract_auto(
    "/path/to/workspace",
    config_path="/path/to/.agentic-extract.json",
    settings_overrides={
        "model": "openai/gpt-4.1",
        "api_base": "https://api.openai.com/v1",
        "api_key": "...",
    },
)
```

常用参数：

- `model`
- `api_base`
- `api_key`
- `max_iterations`
- `target_accuracy`
- `run_timeout`
- `api_timeout`
- `supervisor_mode`（默认 `simple`）
- `reasoning_effort`

## 5. callback / 进度事件

运行过程中可以通过 `on_event` 持续接收进度事件。

```python
def on_event(event):
    print(event.type, event.iteration, event.step, event.message)
```

`event` 是 `ProgressEvent`，常用字段有：

- `type`
- `status`
- `iteration`
- `step`
- `message`
- `elapsed_step_sec`
- `elapsed_iteration_sec`
- `elapsed_total_iteration_sec`
- `elapsed_total_run_sec`
- `token_usage_delta`
- `token_usage_total`
- `data`

### 稳定的粗粒度事件类型

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

### 心跳事件

如果某一步运行较久，会按 `heartbeat_interval_sec` 持续收到：

- `type="heartbeat"`

这适合：

- 在 UI 上显示“还活着”
- 输出运行日志
- 向调用方持续汇报 token 和耗时

## 6. Token 用量

无论是事件还是最终结果，都会暴露 token 用量。

使用的是 `TokenUsage`，常用字段有：

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cached_input_tokens`
- `reasoning_output_tokens`
- `details_complete`

其中：

- `cached_input_tokens` 用于暴露 cache tokens
- `reasoning_output_tokens` 用于暴露 reasoning token 信息

## 7. 最终返回结果

API 最终返回 `RunResult`。

常用字段：

- `status`
- `started_at`
- `finished_at`
- `total_iteration_duration_sec`
- `total_run_duration_sec`
- `iteration_count`
- `token_usage`
- `iteration_token_usage`
- `iterations`
- `error`

### 结果示例

```python
result = run_agentic_extract_auto(...)

print(result.status)
print(result.iteration_count)
print(result.total_iteration_duration_sec)
print(result.total_run_duration_sec)
print(result.token_usage.total_tokens)

for item in result.iterations:
    print(item.iteration, item.action, item.duration_sec, item.summary)
```

## 8. reset / dry-run

### `reset=True`

高层 API 支持：

```python
result = run_agentic_extract_auto(
    "/path/to/workspace",
    reset=True,
    settings_overrides={...},
)
```

行为：

- 清除 `.agent_state/`
- 兼容清理旧版 `logs/` 运行状态
- 不删除 `.xdev` 数据

### `dry_run=True`

可用于只做检查，不真正运行：

```python
result = run_agentic_extract_auto(
    "/path/to/workspace",
    prepare=prepare,
    dry_run=True,
    settings_overrides={...},
)
```

行为：

- 检查配置
- 检查 workspace / prepare 条件
- 检查 API 连通性
- 不实际导入数据
- 不实际进入完整运行

注意：

- `dry_run=True` 与 `reset=True` 不能同时使用

## 9. 运行状态文件

运行期内部状态写入：

- `.agent_state/current.json`
- `.agent_state/iterations/iter_NNN.json`
- `.agent_state/events.jsonl`
- `.agent_state/*.json`

这些是 runtime 内部 bookkeeping，不建议外部程序直接依赖文件路径做业务逻辑。

外部程序优先使用：

- `on_event`
- `RunResult`

## 10. 兼容接口

仍然保留：

- `run_agentic_extract_request()`
- `run_agentic_extract_request_async()`
- `RunRequest`

但它们已经标记为 deprecated。

新代码建议使用：

- 低层：`run_agentic_extract()` + `AgenticExtractSettings`
- 高层：`run_agentic_extract_auto()`
