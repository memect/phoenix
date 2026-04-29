# Python API

## 推荐入口

优先记住两层 API：

- 低层纯运行：`run_agentic_extract()`
- 高层 one-click：`run_agentic_extract_auto()`

异步版本分别是：

- `run_agentic_extract_async()`
- `run_agentic_extract_auto_async()`

兼容性的 `RunRequest` / `run_agentic_extract_request()` 仍存在，但已是 deprecated，不要作为新代码首选。

## 低层 API

适用场景：

- 调用方已经准备好 workspace
- 调用方已经拿到最终 `AgenticExtractSettings`
- 只想运行 agent loop，不做数据准备

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
    },
)

result = run_agentic_extract(
    settings,
    on_event=on_event,
    heartbeat_interval_sec=10.0,
)
```

`settings.model` 的规则同 CLI：

- 推荐显式写 `provider/model_name`
- 不写前缀时，当前默认按 `openai` 解析
- 前缀按 API 协议来选，而不是按模型品牌名来选
- 如果后端是 OpenAI 兼容接口上的 GLM 等模型，通常应写成 `openai/glm-5`
- 如果后端是官方 DeepSeek API，建议写成 `deepseek/deepseek-v4-pro` 这类显式前缀

## 高层 API

适用场景：

- 希望自动解析配置
- 希望按需准备 `.xdev` 数据
- 想让外部程序一键跑完整流程

```python
from agentic_extract import run_agentic_extract_auto
from agentic_extract.types import PrepareSourceSetId, PrepareSpec


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
    },
)
```

## 配置解析

低层 API 通常搭配：

```python
from agentic_extract.config import resolve_settings
```

高层 API 则会自行解析配置，并支持：

- `config_path`
- `settings_overrides`

## prepare 的常见来源

- `PrepareSourceExisting()`
- `PrepareSourceSetId(...)`
- `PrepareSourcePdfDir(...)`
- `PrepareSourceDataDir(...)`
- `PrepareSourceConfigFile(...)`

## 事件循环规则

- 同步 API 不能在已有 event loop 中调用
- 如果当前已经在 async 环境里，改用 async 版本
