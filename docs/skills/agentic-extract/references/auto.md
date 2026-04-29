# `agentic-extract auto`

## 什么时候用

当用户想“一键准备数据并直接开始跑”时，使用 `auto`。

典型场景：

- 首次 bootstrap workspace
- 外部程序一键调用完整流程
- 不想把“导数据”和“运行”拆成两步

## 基本用法

```bash
agentic-extract auto \
  --workspace /path/to/workspace \
  --set-id <set_id> \
  --model openai/gpt-4.1 \
  --api-base https://api.openai.com/v1 \
  --api-key "$OPENAI_API_KEY"
```

## 模型名前缀规则

- 推荐显式写 `provider/model_name`
- 不写前缀时，当前默认按 `openai` 解析
- 前缀按接口协议来选
- 如果 `api_base` 是 OpenAI 兼容接口上的 GLM 等模型，就应使用 `openai/<model_name>`
- 官方 DeepSeek API 建议使用 `deepseek/<model_name>`，例如 `deepseek/deepseek-v4-pro`
- 例如 `https://code.memect.cn` 上的 `glm-5` 应写成 `openai/glm-5`

## prepare source

一次只能指定一种来源：

- `--set-id`
- `--pdfs-dir`
- `--data-dir`
- `--source-file`

如果使用 `--set-id`，还可配合：

- `--std-ids`
- `--std-ids-file`
- `--limit`
- `--base-url`

## 常见示例

只复用已有数据并运行：

```bash
agentic-extract auto --workspace /path/to/workspace
```

从远程标准集 bootstrap 后运行：

```bash
agentic-extract auto --workspace /path/to/workspace --set-id <set_id>
```

从 PDF 目录 bootstrap 后运行：

```bash
agentic-extract auto --workspace /path/to/workspace --pdfs-dir /path/to/pdfs
```

从另一个 `.xdev` 复制后运行：

```bash
agentic-extract auto --workspace /path/to/workspace --data-dir /path/to/other/.xdev
```

## 行为规则

- workspace 没有可运行数据时，如提供 prepare source，会执行 bootstrap
- workspace 已有可运行数据且未传新来源时，会直接复用
- workspace 已有数据但传入不同来源时，默认报错，避免误覆盖
- `--dry-run` 只做判定和校验，不实际导入数据
- `--reset` 只清运行态，不删除 `.xdev`

## 边界

`auto` 是高层 one-click 入口，但它不取代日常数据维护。

如果后续只是：

- 增量添加 PDF
- 同步 PDF 目录
- 修 schema
- 补标注

优先回到 `xdev`。
