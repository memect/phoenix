# `agentic-extract run`

## 什么时候用

当 workspace 已具备可运行 `.xdev` 数据时，`run` 是日常推荐入口。

```bash
agentic-extract run \
  --workspace /path/to/workspace \
  --model openai/gpt-4.1 \
  --api-base https://api.openai.com/v1 \
  --api-key "$OPENAI_API_KEY"
```

## 关键语义

- `run` 只负责运行 agent loop
- `run` 不负责导入数据
- `run` 适合长期 workspace 的日常迭代

## 模型名前缀规则

- 推荐显式写 `provider/model_name`
- 当前常用前缀：`openai`、`deepseek`、`gemini`、`anthropic`
- 不写前缀时，当前默认按 `openai` 解析
- 前缀按接口协议选，不按模型品牌名选
- OpenAI 兼容端点上的 GLM 等模型应写成 `openai/<model_name>`
- 官方 DeepSeek API 建议写成 `deepseek/<model_name>`，例如 `deepseek/deepseek-v4-pro`
- 例如 OpenAI 兼容的 `glm-5` 应写 `openai/glm-5`，不要因为模型品牌去写 `anthropic/glm-5`

## 常用参数

- `--workspace`
- `--config`
- `--model`
- `--api-base`
- `--api-key`
- `--supervisor-model`
- `--business-model`
- `--dev-model`
- `--max-iterations`
- `--target-accuracy`
- `--run-timeout`
- `--api-timeout`
- `--heartbeat-interval-sec`
- `--dry-run`
- `--reset`

## `--dry-run`

只验证：

- 配置解析是否成功
- workspace readiness 是否通过
- API 连通性是否通过

不会真正跑 agent loop。

## `--reset`

会先清运行态目录，再重新开始本次运行：

- `.agent_state/`
- 兼容清理旧版 `logs/`

不会删除 `.xdev` 数据。

## 运行期间写入什么

重点在 workspace 下的：

```text
.agent_state/
```

其中会包含：

- `.agent_state/current.json`
- `.agent_state/iterations/iter_NNN.json`
- 其他运行态状态文件

## 不要再给 `run` 传的数据准备参数

下面这些旧参数不应再用于 `run`：

- `--set-id`
- `--std-ids`
- `--std-ids-file`
- `--limit`
- `--base-url`
- `--pdfs-dir`
- `--data-dir`
- `--source-file`
- `--add-pdf`
- `--force`
- `--sync-pdfs`

如果需要准备数据：

- one-click -> `agentic-extract auto`
- 数据维护 -> `xdev import-data` / `xdev sync-pdfs`
