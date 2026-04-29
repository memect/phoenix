"""Extraction strategies"""

STRATEGIES = """# 提取策略

## 策略 1：正则 vs LLM 决策

**决策流程**：
1. 先试探正则模式
2. 有模式且准确率 >80% → 用正则
3. 无模式或准确率低 → 切换 LLM

**LLM 提取基本模式**（`tool_hub` 由 xdev 自动注入）：
```python
extract_tool = tool_hub.get_tool('extract')

class ExtractSchema(BaseModel):
    title: str | None = Field(description="文档标题")

all_texts = document.get_all_texts()
content = "\\n".join(all_texts)
result = extract_tool(content, schema=ExtractSchema)
```

## 策略 2：结构定位 + llm_select + extract

**何时用**：长文档、字段属于特定章节。

**核心思路**：章节粗筛 → llm_select 精筛 → extract 提取。

**模式 A：按章节定位**
```python
for node in document.iter_nodes("title"):
    if "基本信息" in node.get_text():
        content = node.collect_content()
        texts = [c for c in content if isinstance(c, str)]
        indices = llm_select(texts, target="注册资本")
        chosen = "\\n".join(texts[i] for i in indices)
        result = extract_tool(chosen, schema=InfoSchema)
```

**模式 B：全文 llm_select**
```python
all_texts = document.get_all_texts(max_items=100)
indices = llm_select(all_texts, target="合同签订日期")
chosen = "\\n".join(all_texts[i] for i in indices)
result = extract_tool(chosen, schema=DateSchema)
```

**模式 C：句子级精选（原文摘录）**
```python
sentences = []
for text in document.get_all_texts():
    parts = re.split(r'[。；;\\n]', text)
    sentences.extend(p.strip() for p in parts if p.strip())
indices = llm_select(sentences, target=target)
return "。".join(sentences[i] for i in indices)
```

## 策略 3：表格结构化提取

**核心思路**：LLM 做轻量判断（表类型、表头映射），代码做批量遍历。

**简单表格**：
```python
for node in document.iter_nodes("table"):
    if not isinstance(node, TableNode) or node.row_num < 2:
        continue

    # LLM 判断表类型和表头
    class TableMeta(BaseModel):
        table_type: Literal["horizontal", "vertical"]
        header_mapping: dict[str, str]  # {schema字段: 表头文本}

    meta = extract_tool(node.to_text(max_rows=8), schema=TableMeta)

    # 代码批量提取
    if meta.table_type == "horizontal":
        for row_idx in range(1, node.row_num):
            record = {}
            for schema_field, header_text in meta.header_mapping.items():
                col_idx = find_column_by_header(node, header_text)
                record[schema_field] = node.cell_at(row_idx, col_idx).text
            results.append(record)
```

**复杂表格**（合并单元格、多级表头）：
```python
# 让 LLM 直接输出结构化数据
class RecordSchema(BaseModel):
    name: str
    amount: float

class TableResult(BaseModel):
    records: list[RecordSchema]

result = extract_tool(node.to_text(), schema=TableResult)
```

## 策略 4：分字段组合

不同字段用不同策略：
- 固定格式（日期、编号）→ 正则优先
- 语义理解（摘要、描述）→ llm_select + extract
- 分类型（类别、状态）→ extract + Literal
- 表格数据 → 策略 3
- 原文摘录 → 策略 2 模式 C

## 策略 5：调试排查

**核心方法**：加 print，用 `xdev run <id>` 查看 stdout。

```python
# 1) 定位阶段
all_texts = document.get_all_texts()
print(f"[DEBUG] 总段落数: {len(all_texts)}")

# 2) 筛选阶段
indices = llm_select(all_texts, target="xxx")
print(f"[DEBUG] llm_select 选中: {indices}")

# 3) 提取阶段
result = extract_tool(chosen, schema=Schema)
print(f"[DEBUG] extract 返回: {result}")
```

调试完成后删除 print 语句。
"""
