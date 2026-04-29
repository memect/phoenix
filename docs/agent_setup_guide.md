# 提取代码开发环境配置

你是一个提取代码开发 Agent。先安装并配置工具，再按 `docs/skills/` 里的 skill 开始工作。

## 1. 安装工具

主工具包是 `extract-agent`，它提供：

- `xdev`
- `agentic-extract`
- `pdf-ai-explorer`

推荐使用 `uv`：

```bash
uv tool install extract-agent
```

安装 `extract-agent` 后应可直接使用：

```bash
xdev --help
agentic-extract --help
pdf-ai-explorer --help
```

如果只想单独安装长文档导航工具，才需要单独安装：

```bash
uv tool install pdf-ai-explorer
```

或在虚拟环境中使用 pip：

```bash
pip install extract-agent
```

注意：

- `extract-agent` 发布到 PyPI，默认安装命令不需要指定私有 index
- macOS Homebrew Python 不适合全局 `pip install`，优先 `uv tool install`

验证安装：

```bash
xdev --help
agentic-extract --help
pdf-ai-explorer --help
```

## 2. 使用 Skills

skill 源文档现在直接放在仓库里：

```text
docs/skills/
  xdev/
  agentic-extract/
  pdf-ai-explorer/
  release-process/
```

每个 skill 目录都是自包含的，可以直接复制给 agent 使用，不依赖 `xdev export-skills`。

### 复制到 Codex 本地目录

```bash
mkdir -p .agents/skills
cp -R docs/skills/xdev .agents/skills/
cp -R docs/skills/agentic-extract .agents/skills/
cp -R docs/skills/pdf-ai-explorer .agents/skills/
cp -R docs/skills/release-process .agents/skills/
```

安装后的目录结构：

```text
.agents/skills/
  xdev/
    SKILL.md
    references/
  agentic-extract/
    SKILL.md
    references/
  pdf-ai-explorer/
    SKILL.md
  release-process/
    SKILL.md
    references/
```

## 3. 配置

按任务选择最小需要的配置，不要一开始把所有配置都配满。

### xdev

全局配置：

```json
{
  "base_url": "<标准集 API 地址>",
  "pdf_parse_concurrent": 1
}
```

文件位置：

```text
~/.config/xdev/config.json
```

常用环境变量：

- `XDEV_BASE_URL`
- `XDEV_PDF_PARSE_CONCURRENT`
- `XDEV_MEMECT_API_BASE`
- `XDEV_DATA_DIR`

任务差异：

- 只看已有 `.xdev` 数据：通常不必额外配置
- `xdev import-data --set-id`：需要 `base_url`
- `xdev import-data --pdfs` / `xdev sync-pdfs`：需要本机 `ppx` 命令；`pdf_parse_concurrent` 控制批量 PDF 解析并发

### agentic-extract

全局配置示例：

```json
{
  "model": "openai/gpt-4.1",
  "api_base": "https://api.openai.com/v1",
  "api_key": "YOUR_API_KEY"
}
```

文件位置：

```text
~/.config/agentic-extract/config.json
```

常用环境变量：

- `AE_MODEL`
- `AE_API_BASE`
- `AE_API_KEY`
- `AE_MAX_ITERATIONS`
- `AE_TARGET_ACCURACY`

`agentic-extract run` / Python API 最小需要：

- `model`
- `api_base`
- `api_key`

### pdf-ai-explorer

直接读 `.pdf` 时需要解析服务配置。

配置文件：

```toml
# ~/.config/pdf-ai-explorer/config.toml
api_url = "http://localhost:6111/api"
```

或环境变量：

```bash
export MEMECT_API_URL="http://localhost:6111/api"
```

建议将 `MEMECT_API_URL` 与 `XDEV_MEMECT_API_BASE` 保持一致。

## 4. 开始工作

按任务选择 skill：

- 准备 workspace、导入数据、看 schema/标注、评估：使用 `xdev`
- 启动 agentic loop、one-click auto、Python API：使用 `agentic-extract`
- 查看长文档大纲、按页阅读、关键词定位：使用 `pdf-ai-explorer`

推荐顺序：

1. `xdev init <workspace>`
2. `xdev import-data` 或 `xdev sync-pdfs`
3. 参考 `xdev` skill 做数据分析、schema、标注、评估
4. `.xdev` 可运行后，再参考 `agentic-extract` skill 启动迭代
