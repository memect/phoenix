# Progress Events 与 Heartbeat

## 目标

对外暴露稳定、粗粒度的运行进度，不要求调用方理解内部 agent 实现。

## callback 入口

CLI 会把事件打印到 stdout。

Python API 使用 `on_event` callback：

```python
def on_event(event):
    print(
        event.type,
        event.iteration,
        event.step,
        event.elapsed_total_run_sec,
        event.token_usage_total.total_tokens,
    )
```

传入方式：

```python
result = run_agentic_extract(
    settings,
    on_event=on_event,
    heartbeat_interval_sec=10.0,
)
```

## 事件类型

当前稳定的粗粒度事件包括：

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

## 常见字段

- `event.iteration`
- `event.step`
- `event.message`
- `event.status`
- `event.elapsed_step_sec`
- `event.elapsed_iteration_sec`
- `event.elapsed_total_iteration_sec`
- `event.elapsed_total_run_sec`
- `event.token_usage_delta`
- `event.token_usage_total`
- `event.data`

## heartbeat

- `heartbeat` 是第一版必需能力
- 通过 `heartbeat_interval_sec` 控制频率
- 默认值是 `10.0` 秒
- 适合调用方做超时监控、UI 刷新、长步骤存活探测

## token usage

`TokenUsage` 目前至少包含：

- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cached_input_tokens`
- `reasoning_output_tokens`
- `details_complete`

调用方如果只想拿稳定指标，优先依赖：

- `total_tokens`
- `input_tokens`
- `output_tokens`
- `cached_input_tokens`

## 结果对象里的耗时

最终 `RunResult` 至少可读到：

- `iteration_count`
- `total_iteration_duration_sec`
- `total_run_duration_sec`
- `token_usage`
- `iterations`

每个 `IterationResult` 至少包含：

- `iteration`
- `duration_sec`
- `token_usage`
- `evaluation`
- `summary`
- `error`

注意：

- `IterationResult.duration_sec` 表示这一轮迭代完整完成所需的全部时间
- `total_iteration_duration_sec` 是各轮迭代耗时的累计
- `total_run_duration_sec` 包含整次运行的总时间，不仅是迭代正文

## 对 agent 的建议

- 把这些事件当成外部契约，不要依赖更细的内部 trace
- 需要展示进度时，优先做“轮次 + 当前 step + 总耗时 + token usage”
- 需要保活时，优先监听 `heartbeat`
