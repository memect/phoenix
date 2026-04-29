---
name: agentic-extract
description: 当用户要启动 agentic loop、使用 one-click auto、通过 Python API 调用完整流程、或在运行过程中接收 callback 和 heartbeat 事件时使用此 skill。如果用户当前主要是在准备或维护 `.xdev` 数据，先转到 xdev skill。
---

# agentic-extract

`agentic-extract` 负责 workspace 的运行层。

## 前置检查

开始前先确认当前环境至少能满足本次任务。

### 命令

至少检查：

```bash
agentic-extract --help
```

如果命令不可用，先安装：

```bash
uv tool install extract-agent
```

`extract-agent` 发布到 PyPI，默认安装命令不需要指定私有 index。

### 配置

`agentic-extract` 最小需要的 LLM 配置通常是：

- `model`
- `api_base`
- `api_key`

模型名前缀规则要明确：

- 推荐总是写成 `provider/model_name`
- 当前实现支持的 provider 前缀是：`openai`、`deepseek`、`gemini`、`anthropic`
- 如果 `model` 里不写前缀，当前会默认按 `openai` 解析
- 前缀应按“API 协议 / SDK 适配层”来选，不要按模型品牌名来猜
- 如果后端是 OpenAI 兼容接口上的 GLM 或其他普通兼容模型，应写成 `openai/<model_name>`
- 官方 DeepSeek API 建议显式写成 `deepseek/<model_name>`，例如 `deepseek/deepseek-v4-pro`
- 例如 `https://code.memect.cn` 这类 OpenAI 兼容端点，`glm-5` 应写成 `openai/glm-5`，不要写 `anthropic/glm-5`
- 只有当后端真的走 Anthropic 协议时，才写 `anthropic/<model_name>`
- 不确定时，先用显式前缀加 `agentic-extract run --dry-run` 验证，不要依赖隐式默认行为

常见来源：

- CLI 参数
- 环境变量：`AE_MODEL` / `AE_API_BASE` / `AE_API_KEY`
- `~/.config/agentic-extract/config.json`
- `$CWD/.agentic-extract.json`
- workspace 向上到 repo 根目录的 `.agentic-extract.json`

如果当前任务是 `agentic-extract auto`，还要注意：

- `--set-id` 路径需要 `base_url`
- `--pdfs-dir` 路径需要本机 `ppx` 命令可用
- `--data-dir` 路径通常只依赖本地数据

最小验证优先使用：

```bash
agentic-extract run \
  --workspace /path/to/workspace \
  --model openai/gpt-4.1 \
  --api-base https://api.openai.com/v1 \
  --api-key "$OPENAI_API_KEY" \
  --dry-run
```

优先在这些场景使用本 skill：

- workspace 已有可运行 `.xdev` 数据，准备启动 agentic loop
- 希望一键完成“按需准备数据 + 开始运行”
- 外部 Python 程序要调用完整流程
- 调用方需要 progress callback、heartbeat、token usage、迭代耗时

不要把下面这些事放在本 skill 里：

- 详细的数据导入或同步操作
- 标注工作流本身
- 把 `xdev` 的数据维护命令重新包装一遍

## 先做判断

- 如果 workspace 数据已经准备好，读 [references/run.md](references/run.md)
- 如果用户要 one-click bootstrap，再运行，读 [references/auto.md](references/auto.md)
- 如果用户要从 Python 调用，读 [references/python_api.md](references/python_api.md)
- 如果用户关心 callback、heartbeat、token 与耗时，读 [references/progress_events.md](references/progress_events.md)
- 如果 `.xdev` 还没准备好且用户只是在做数据维护，切到 `xdev` skill

## 工作原则

- `agentic-extract run` 是纯运行命令
- `agentic-extract auto` 是 one-click 准备加运行
- 增量导入、补 PDF、同步 PDF 属于 `xdev`，不属于 `agentic-extract`
- 运行态信息写入 `.agent_state/`，这是运行层，不是数据层
- 稳定对外暴露的是粗粒度 progress event，不要依赖内部实现细节

## 最短路径

1. 确认 workspace 已有可运行 `.xdev`，否则先走 `xdev`
2. 日常迭代优先 `agentic-extract run --workspace /path/to/workspace`
3. 首次 bootstrap 或外部程序一键调用，优先 `agentic-extract auto`
4. Python 程序：
   - 已有最终 settings -> `run_agentic_extract()`
   - 希望自动解析配置并按需准备数据 -> `run_agentic_extract_auto()`
5. 需要持续感知进度时，使用 `on_event` callback 和 `heartbeat_interval_sec`
