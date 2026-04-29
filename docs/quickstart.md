## 安装
```bash
uv tool install extract-agent
```

## 配置
```bash
xdev-config
```

本地 PDF 解析默认调用 `ppx parse`。使用 `--pdfs-dir` 或 `xdev run --pdf` 前，先确认 `ppx` 命令可用；批量 PDF 解析并发可通过 `pdf_parse_concurrent` / `XDEV_PDF_PARSE_CONCURRENT` 控制。

大模型配置示例
```markdown
model: openai/GLM-5
api_base: https://your-openai-compatible-endpoint/v1
api_key: xxx
```

## 执行迭代
```bash
agentic-extract auto --workspace ws --pdfs-dir ../pdfs --message '随便提点东西'
```

## 继续迭代
```bash
agentic-extract auto --workspace ws --message '再提一个xx字段'
```

## 在新文档上提取
```bash
xdev run --workspace ws --pdf ../pdfs/1.pdf
xdev run --workspace ws --docjson ../docs/doc.json
```

`--docjson` 会自动识别 canonical DocJSON 和 PPX DocJSON，不需要格式选项。

更多 `agentic-extract` 命令行用法与 budget/迭代次数控制，见 [agentic_extract_cli.md](./agentic_extract_cli.md)。
