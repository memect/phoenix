# Extract Agent

## 安装
```bash
bash scripts/install.sh
```

脚本会用 `uv tool install` 安装 `extract-agent`，并把 `ppx` 安装到独立虚拟环境后写入 PATH。

## 配置
```bash
xdev-config
```

本地 PDF 解析默认调用 `ppx parse`；批量 PDF 解析并发可通过 `pdf_parse_concurrent` / `XDEV_PDF_PARSE_CONCURRENT` 控制。

大模型配置示例
```markdown
model: openai/GLM-5
api_base: https://your-openai-compatible-endpoint/v1
api_key: xxx
```

## 执行迭代
```bash
agentic-extract auto --workspace ws --pdfs-dir examples/pdfs --message '随便提点东西'
```

## 继续迭代
```bash
agentic-extract auto --workspace ws --message '再提一个xx字段'
```

更多 `agentic-extract` 命令行用法与 budget/迭代次数控制，见 [agentic_extract_cli.md](./agentic_extract_cli.md)。
