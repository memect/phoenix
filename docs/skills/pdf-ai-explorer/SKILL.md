---
name: pdf-ai-explorer
description: 当文档内容过长无法一次查看、需要搜索关键词定位信息、或需要按页按节点浏览 DocJSON/PDF 结构时使用此 skill。适合与 xdev、agentic-extract 配合做长文档阅读与定位。
---

# pdf-ai-explorer

`pdf-ai-explorer` 负责长文档导航，不负责 schema、标注、评估或 agentic loop。

## 前置检查

### 命令

先检查：

```bash
pdf-ai-explorer --help
```

如果命令不可用，先安装：

```bash
uv tool install extract-agent
```

如果你只想单独安装这个导航工具，再单独装：

```bash
uv tool install pdf-ai-explorer
```

`extract-agent` 和 `pdf-ai-explorer` 发布到 PyPI，默认安装命令不需要指定私有 index。

### 配置

按读取对象区分：

- 读 docjson：通常只要命令可用
- 直接读 `.pdf`：需要 PDF 解析服务配置

配置来源：

- 环境变量：`MEMECT_API_URL`
- 配置文件：`~/.config/pdf-ai-explorer/config.toml`

最小配置示例：

```toml
api_url = "http://localhost:6111/api"
```

或：

```bash
export MEMECT_API_URL="http://localhost:6111/api"
```

如果和 `xdev` 一起使用，建议把它和 `XDEV_MEMECT_API_BASE` 配成同一个地址。

最小验证：

- 命令存在：`pdf-ai-explorer --help`
- 已有 docjson：`pdf-ai-explorer outline /path/to/doc.json`

## 什么时候用

- `xdev doc` 只显示前 1000 字，不够看
- 需要先看文档大纲再定位字段
- 需要用关键词快速定位章节
- 需要查看某个节点的上下文、兄弟节点、子节点

## 不要用来做什么

- 不要把它当成 schema/标注工具
- 不要在这里解释 `agentic-extract run` / `auto`
- 不要用它替代 `xdev` 的数据导入和评估

## 最短路径

1. 先拿到 docjson 路径
2. `outline` 看整体结构
3. `search` 找关键词
4. `read` / `content` 看具体内容
5. `inspect` 看节点上下文

## 获取 docjson 路径

在 `xdev doc <doc_id>` 输出里通常会直接提示 docjson 路径。

也可以通过代码拿：

```bash
python -c "from xdev.api import get_docjson_path; print(get_docjson_path('doc_001'))"
```

## 命令速查

- `pdf-ai-explorer outline <doc.json>`：查看文档大纲
- `pdf-ai-explorer read <doc.json> <page>`：按页阅读
- `pdf-ai-explorer search <doc.json> <query>`：搜索关键词
- `pdf-ai-explorer content <doc.json> <node_id>`：查看指定节点内容
- `pdf-ai-explorer inspect <doc.json> <node_id>`：查看节点上下文

## 使用建议

- 先 `outline`，再 `search` 或 `read`
- `search` 适合快速定位字段相关章节
- `inspect` 适合理解节点在整棵文档树里的位置
- 如果用户真正要做的是数据维护，切到 `xdev`
- 如果用户真正要做的是启动 agentic loop，切到 `agentic-extract`
