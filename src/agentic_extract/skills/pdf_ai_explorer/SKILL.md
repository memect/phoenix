---
name: pdf_ai_explorer
description: 当文档内容过长无法一次查看、需要搜索关键词定位信息、或需要按页/按节点浏览 PDF 文档结构时激活此 skill。
---

# pdf-ai-explorer — PDF 长文档导航工具

当文档过长时，`xdev doc` 只返回前 1000 字并提示 docjson 路径。使用 `pdf-ai-explorer` 按需导航完整内容。

## 配置

`pdf-ai-explorer` 在读取 `.pdf` 文件时会调用 PDF 解析服务（读取 `.json` 文件时不需要）。

推荐配置文件：

```toml
# ~/.config/pdf-ai-explorer/config.toml
api_url = "http://localhost:6111/api"
```

也可以用环境变量覆盖：

```bash
export MEMECT_API_URL="http://localhost:6111/api"
```

配置优先级：
- 代码参数 override（SDK/MCP 显式传入 `api_url`）
- 环境变量 `MEMECT_API_URL`
- 配置文件 `~/.config/pdf-ai-explorer/config.toml`
- 默认值 `http://localhost:6111/api`

与 xdev 配合时，建议把该地址和 `XDEV_MEMECT_API_BASE` 保持一致。

## 获取 docjson 路径

```bash
# 在 xdev doc 输出中会提示 docjson 路径，例如：
# [文档过长，仅显示前 1000 字。完整文档路径: .xdev/data/docjson/doc_001.json]

# 也可以通过代码获取
python -c "from xdev.api import get_docjson_path; print(get_docjson_path('doc_001'))"
```

## 命令速查

| 命令 | 用途 | 示例 |
|------|------|------|
| `pdf-ai-explorer outline <doc.json>` | 查看文档大纲结构 | `--depth 3` 展开更多层级 |
| `pdf-ai-explorer read <doc.json> <page>` | 按页阅读内容 | `read doc.json 5-8` |
| `pdf-ai-explorer search <doc.json> <query>` | 搜索关键词 | `search doc.json "营业收入"` |
| `pdf-ai-explorer content <doc.json> <ID>` | 查看指定节点内容 | 节点 ID 从 outline/search 获取 |
| `pdf-ai-explorer inspect <doc.json> <ID>` | 查看节点上下文 | 路径、兄弟节点、子节点 |

## 推荐工作流

```
1. outline 了解文档结构
   $ pdf-ai-explorer outline .xdev/data/docjson/doc_001.json

2. search 定位关键词
   $ pdf-ai-explorer search .xdev/data/docjson/doc_001.json "营业收入"

3. read/content 查看具体内容
   $ pdf-ai-explorer read .xdev/data/docjson/doc_001.json 5-8
   $ pdf-ai-explorer content .xdev/data/docjson/doc_001.json <node_id>

4. inspect 查看节点上下文（路径、兄弟、子节点）
   $ pdf-ai-explorer inspect .xdev/data/docjson/doc_001.json <node_id>
```

## 使用场景

- **业务分析**：阅读长文档理解内容结构和业务含义，为标注和 schema 定义提供依据
- **提取开发**：定位目标字段所在章节和上下文，确定提取策略
- **调试排查**：检查目标信息在文档中的具体位置和格式

## 注意事项

- 始终先 `outline` 了解结构，再定向查看，避免盲目翻页
- `search` 支持中文关键词，用于快速定位目标信息
- `content` 命令的节点 ID 来自 `outline` 或 `search` 的输出
- `inspect` 可以查看节点在文档树中的路径和相邻节点，帮助理解文档层级
