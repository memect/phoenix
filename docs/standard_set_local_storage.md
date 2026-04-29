# 标准集本地存储格式

本文档描述 `extract-dev` 和 `evaluation-engine` 下载标准集后的本地存储结构。

## 目录结构

```
.cache/{set_id_without_hyphens}/
├── docjson/                          # 文档 DocJSON 文件
│   ├── {document_id}.json
│   └── ...
├── schema.json                       # Schema 定义
└── standard_for_evaluate/            # 标准集数据
    ├── train.json                    # 训练集
    ├── test.json                     # 测试集
    └── info.txt                      # 数据统计
```

**说明**：
- `set_id_without_hyphens`：标准集 ID 去掉连字符，如 `eb38831e-7a45-4f26-8574-62043ff187f0` → `eb38831e7a454f26857462043ff187f0`
- 默认缓存目录为 `.cache/`，可通过参数配置

## 文件格式

### schema.json

Schema 定义文件，描述需要提取的字段。

```json
{
    "type": "list_of_objects",
    "data": {
        "字段名1": "str",
        "字段名2": "str"
    }
}
```

**字段说明**：
- `type`：Schema 类型
  - `"object"` - 单对象（每个文档提取一条记录）
  - `"list_of_objects"` - 对象列表（每个文档提取多条记录）
- `data`：字段定义，键为字段名，值为字段类型（目前只支持 `"str"`）

### train.json / test.json

标准集数据文件，JSON 数组格式。

```json
[
    {
        "id": "943e39e8-d69a-cbed-4cca-3503472310d2",
        "document_id": "943e39e8-d69a-cbed-4cca-3503472310d2",
        "labels": [
            {
                "字段名1": "值1",
                "字段名2": "值2"
            }
        ],
        "markdown": null,
        "md_link": "http://...",
        "pdf_link": "http://...",
        "docjson_link": "http://...",
        "filename": "文档标题"
    }
]
```

**字段说明**：
- `id`：标准集条目 ID（用于 `--standard-entry-ids` 参数）
- `document_id`：原始文档 ID（与 docjson 文件名对应）
- `labels`：标准答案
  - 当 schema type 为 `"object"` 时，为单个对象
  - 当 schema type 为 `"list_of_objects"` 时，为对象数组
- `markdown`：文档 Markdown 内容（可选，通常为 null，从 docjson 读取）
- `md_link`、`pdf_link`、`docjson_link`：远程文件链接
- `filename`：文档文件名/标题

### info.txt

数据统计文件，记录训练集和测试集的数量。

```
train: 33
test: 16
```

### docjson/{document_id}.json

文档的 DocJSON 格式文件，包含文档的结构化内容（文本、表格等）。

文件名为 `{document_id}.json`，其中 `document_id` 去掉连字符。

## ID 说明

系统中存在两种 ID：

| ID 类型 | 字段名 | 说明 | 用途 |
|---------|--------|------|------|
| 标准集条目 ID | `id` | 标准集中每条记录的唯一标识 | `--standard-entry-ids` 参数、评估报告中的文档 ID |
| 原始文档 ID | `document_id` | 原始文档的唯一标识 | docjson 文件名、远程文件链接 |

**注意**：在大多数情况下，这两个 ID 是相同的。但在某些场景下（如同一文档有多个标准条目）可能不同。

## 相关命令

```bash
# 下载标准集（自动缓存）
extract-dev list

# 使用缓存的数据
extract-dev train
extract-dev test

# 指定标准集条目评估
extract-dev train --standard-entry-ids "id1,id2,id3"
```
