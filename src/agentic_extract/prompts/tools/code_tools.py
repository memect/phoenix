"""Code tools documentation"""

CODE_TOOLS = """# 代码工具

## 工具系统

`xdev run` / `xdev eval` 会自动读取 xdev 配置，并把 `tool_hub` 注入到
`extract(document, tool_hub)`。不要在 `program.py` 中自行读取 xdev 配置。

```python
from code_executor.document.models.document import Document
from code_executor.tools import ToolHub

def extract(document: Document, tool_hub: ToolHub):
    extract_tool = tool_hub.get_tool('extract')      # LLM 结构化提取
    llm_select = tool_hub.get_tool('llm_select')      # LLM 段落筛选
    ...
```

## extract 工具

用 Pydantic BaseModel 定义 schema，LLM 从文本中提取结构化数据：

```python
from pydantic import BaseModel, Field

class InfoSchema(BaseModel):
    company_name: str | None = Field(description="公司名称")
    amount: float | None = Field(description="金额")

result = extract_tool(text_content, schema=InfoSchema)
# result: {"company_name": "XX公司", "amount": 100.0}
```

## llm_select 工具

从段落列表中筛选包含目标信息的段落：

```python
all_texts = document.get_all_texts()
indices = llm_select(all_texts, target="合同签订日期")
chosen = "\n".join(all_texts[i] for i in indices)
```

## 代码质量工具

### Ruff — 代码检查和格式化

```bash
ruff check <file>               # 检查代码质量
ruff check --fix <file>         # 自动修复
ruff format <file>              # 格式化代码
```

常见错误代码：
- **F401**: 导入但未使用
- **F841**: 变量赋值但未使用
- **E501**: 行太长（默认 88 字符）

### Tree-sitter CLI — 代码结构分析

```bash
tree-sitter-cli analyze <file.py>              # 代码骨架（省略函数体）
tree-sitter-cli find-symbol <file.py> <name>   # 定位符号（返回 JSON）
tree-sitter-cli list-symbols <file.py>         # 列出所有符号
```

### Mypy — 类型检查

```bash
mypy program.py                        # 基本类型检查
mypy --ignore-missing-imports <file>   # 忽略缺少类型提示的导入
```
"""
