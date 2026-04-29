"""xdev CLI documentation"""

XDEV = """# xdev — 数据管理和评估工具

xdev 管理 `.xdev/` 目录中的文档数据、schema、标注，并提供提取评估能力。

## 常用命令

### 数据查看

```bash
xdev list                    # 列出所有文档
xdev doc <doc_id>            # 查看文档内容（长文档会截断并提示使用 pdf-ai-explorer）
xdev context                 # 显示 Document API 使用指南
xdev standard <doc_id>       # 查看文档的标注数据
xdev docjson-paths           # 输出 doc_id → docjson 路径映射
```

### Schema 和标注

```bash
xdev label-guide             # 查看 schema 信息和标注指导
xdev label-guide <doc_id>    # 获取特定文档的标注模板
xdev label-status            # 检查标注状态（覆盖率、schema 一致性）
xdev label-status --detail   # 详细信息（列出每个问题文档）
```

### 执行和评估

```bash
xdev run <doc_id>            # 在单文档上执行 program.py
xdev eval                    # 全量评估（所有已标注文档）
xdev eval <doc_id>           # 单文档评估
```

## 数据目录结构

```
.xdev/
├── config.json                # 项目配置（可选）
├── manifest.json              # 数据源元信息（import 时生成，只读）
├── schema.json                # Schema 定义（直接编辑文件）
├── data/
│   ├── docjson/
│   │   ├── <doc_id>.json      # DocJSON 文件（PDF 解析结果）
│   │   └── ...
│   └── pdf/
│       ├── <doc_id>.pdf       # 原始 PDF 文件
│       └── ...
└── labels/
    ├── <doc_id>.json          # 每个文档的标注（直接编辑文件）
    └── ...
```

## Schema 格式

**单条记录（object）**：
```json
{"type": "object", "data": {"公司名称": "str", "注册资本": "float"}}
```

**多条记录（list_of_objects）**：
```json
{"type": "list_of_objects", "data": {"股东名称": "str", "持股比例": "float"}}
```

**字段类型**：`"str"` / `"int"` / `"float"` / `"bool"` / `"list"`

## 标注格式

**object 模式**：
```json
{"公司名称": "XX科技有限公司", "注册资本": 1000.0}
```

**list_of_objects 模式**：
```json
[{"股东名称": "张三", "持股比例": 30.0}, {"股东名称": "李四", "持股比例": 20.0}]
```

## 代码入口

`xdev` 仅支持 Document 输入，入口签名应为：

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub
from typing import Any

def extract(document: Document, tool_hub: ToolHub) -> dict[str, Any] | list[dict[str, Any]]:
    ...
```

`tool_hub` 由 xdev 自动读取配置后注入，可用于获取 `extract`、`llm_select`
等代码工具；不要在 `program.py` 中自行读取 xdev 配置。
"""
