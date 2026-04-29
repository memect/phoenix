"""
LabelingAgent prompts

单文档标注 Agent 的提示词，适配 xdev 数据工具。
"""


SYSTEM_PROMPT = """你是一个文档标注专家。你的任务是阅读文档内容，根据 schema 定义和业务指导，为文档生成准确的标注数据。

## 工作流程

1. 使用 `xdev doc <doc_id>` 查看文档内容
   - 长文档会被截断并提示使用 pdf-ai-explorer 查看完整内容
2. 根据 schema 和业务指导，提取每个字段的值
3. 将标注 JSON 写入 `.xdev/labels/<doc_id>.json`

## 注意事项

- labels 的 key 必须与 schema.data 的 key 完全一致
- 如果文档中某字段信息缺失，标注为空字符串 ""
- 标注必须基于文档实际内容，不要臆测
- 一次完成标注，不要反复修改
- 数值类型字段（int/float）标注为数值，不要加引号

## 标注格式

根据 schema 的 type 决定标注 JSON 的格式：

- **object**（单条记录）：`{"字段1": "值1", "字段2": "值2"}`
- **list_of_objects**（多条记录）：`[{"字段1": "值1"}, {"字段1": "值2"}]`
  - 每篇文档中有多组同类信息时使用，如多个股东、多笔交易
  - 数组中每个元素的 key 必须与 schema.data 的 key 一致
"""


def build_label_message(
    doc_id: str,
    schema_json: str,
    business_guide: str,
    docjson_path: str,
) -> str:
    """构建标注任务消息

    Args:
        doc_id: 文档 ID
        schema_json: schema 定义 JSON 字符串
        business_guide: 业务指导文档内容
        docjson_path: docjson 文件路径（用于 pdf-ai-explorer）
    """
    import json
    try:
        schema = json.loads(schema_json)
        schema_type = schema.get("type", "object")
    except (json.JSONDecodeError, AttributeError):
        schema_type = "object"

    if schema_type == "list_of_objects":
        format_hint = """注意：schema type 为 `list_of_objects`，标注 JSON 必须是**数组**格式：
```
[{"字段1": "值1", "字段2": "值2"}, {"字段1": "值3", "字段2": "值4"}]
```
每篇文档中有多组同类信息，每组一个元素。"""
    else:
        format_hint = """注意：schema type 为 `object`，标注 JSON 为**对象**格式：
```
{"字段1": "值1", "字段2": "值2"}
```"""

    return f"""## 任务

为文档 `{doc_id}` 生成标注数据。

## Schema 定义

```json
{schema_json}
```

## 标注格式

{format_hint}

## 业务指导

{business_guide}

## 步骤

1. 运行 `xdev doc {doc_id}` 查看文档内容
   - 如果文档过长被截断，使用以下命令查看完整内容：
     ```
     pdf-ai-explorer outline {docjson_path}
     pdf-ai-explorer search <关键词> {docjson_path}
     pdf-ai-explorer read <节点ID> {docjson_path}
     ```
2. 根据上述 schema 和业务指导，提取每个字段的值
3. 将标注 JSON 写入 `.xdev/labels/{doc_id}.json`

请开始。"""
