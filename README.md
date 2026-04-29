# Extract Agent

本 README 只给最短操作流程。

场景：从本地 PDF 准备 workspace，然后运行 agentic-extract 迭代。

## 0. 快速开始

> [quick start](docs/quickstart.md)
>
> 命令行常用用法见 [agentic-extract CLI](docs/agentic_extract_cli.md)
>
> 维护者发布流程见 [release-process skill](docs/skills/release-process/SKILL.md)

## 1. 安装

```bash
uv tool install extract-agent
```

安装 `extract-agent` 后会同时暴露这些命令：

- `agentic-extract`
- `xdev`
- `xdev-config`
- `pdf-ai-explorer`
- `tree-sitter-cli`

## 2. 配置

`~/.config/xdev/config.json`

```json
{
  "pdf_parse_concurrent": 1
}
```

PDF 解析默认使用本机 `ppx` 命令（来自 `memect-ppx`），请先确认 `ppx parse <pdf>` 可用。`pdf_parse_concurrent` 控制批量 PDF 时 PPX 同时解析多少个文件。

`~/.config/agentic-extract/config.json`

```json
{
  "model": "openai/gpt-4.1",
  "api_base": "https://api.openai.com/v1",
  "api_key": "YOUR_API_KEY"
}
```

也可以直接运行：

```bash
xdev-config
```

它会同时写入全局 `agentic-extract` / `xdev` 配置。

如果后端是 OpenAI 兼容接口上的 GLM 等模型，仍写成 `openai/<model_name>`。但官方 DeepSeek API 建议显式写成 `deepseek/<model_name>`，这样能启用 DeepSeek 专用 formatter，在 thinking + tools 场景里正确保留 `reasoning_content`。例如：

```json
{
  "model": "openai/GLM-5",
  "api_base": "http://your-openai-compatible-endpoint",
  "api_key": "YOUR_API_KEY"
}
```

官方 DeepSeek API 示例：

```json
{
  "model": "deepseek/deepseek-v4-pro",
  "api_base": "https://api.deepseek.com/v1",
  "api_key": "YOUR_DEEPSEEK_API_KEY"
}
```

## 3. 一键模式

如果你不想手动拆成“导入数据 + 运行”两步，可以直接：

```bash
agentic-extract auto \
  --workspace /path/to/workspace \
  --pdfs-dir /path/to/pdfs
```

## 4. 创建 workspace

```bash
xdev init /path/to/workspace
cd /path/to/workspace
```

## 5. 从本地 PDF 导入数据

```bash
xdev import-data --pdfs /path/to/pdfs
```

导入后先看一下：

```bash
xdev list
```

## 6. 调试

看单个文档：

```bash
xdev doc <doc_id>
```

运行单个文档：

```bash
xdev run <doc_id>
xdev run --workspace /path/to/workspace --pdf /path/to/file.pdf
xdev run --workspace /path/to/workspace --docjson /path/to/file.json
```

`--docjson` 会自动识别 canonical DocJSON 和 PPX DocJSON；不需要指定格式。

评估：

```bash
xdev eval
```

## 7. 跑 agentic-extract

```bash
agentic-extract run --workspace /path/to/workspace
```

如果只想先检查配置和连通性：

```bash
agentic-extract run --workspace /path/to/workspace --dry-run
```

如果想清空运行状态后重新开始：

```bash
agentic-extract run --workspace /path/to/workspace --reset
```

## 8. 后续继续迭代

新增 PDF：

```bash
xdev import-data --add-pdf /path/to/new.pdf
```

重新解析：

```bash
xdev import-data --reparse
```

然后继续跑：

```bash
agentic-extract run --workspace /path/to/workspace
```
