---
name: fact-extract
description: 当用户说“提取事实 / 提取 fact / 从 PDF 抽事实”时激活。按确定性流程检查安装与配置后，默认直接用 fact-extract run 全流程提取。
---

# fact-extract

## 触发

当用户表达以下意图时，直接使用本 skill：
- “提取事实”
- “提取 fact”
- “从 PDF 抽取事实”
- “跑 fact-extract”

## 规则

- 默认命令必须是 `fact-extract run`。
- 不要先执行无关流程，如 `xdev run`、`agentic-extract run`。
- 先检查安装与配置，再执行提取。
- 提取阶段并发默认32。
- 提取后端默认 `llm-once`（等价于 `llm --max-chunk-chars 0`，单次调用不分 bundle）。
- 默认开启反思校对（提取后二次校对），`--no-reflect` 可关闭。
- `--section-mode auto` 开启 LLM 全书段落分段（断点续跑、自动重试），`--no-section-strict` 允许跳过失败分组。

## 安装

```bash
uv tool install extract-agent
```

验证：

```bash
fact-extract --help
```

## 配置

`fact-extract` 支持环境变量：

```bash
export FACT_EXTRACT_MODEL="<MODEL>"
export FACT_EXTRACT_API_BASE="<API_BASE>"
export FACT_EXTRACT_API_KEY="<YOUR_API_KEY>"
```

若未设置环境变量，执行时必须显式传：
- `--model`
- `--api-base`
- `--api-key`

## 默认执行

已配置环境变量时：

```bash
fact-extract run \
  --pdf "<PDF_PATH>" \
  --planner-backend agentic \
  --extractor-backend llm-once \
  --max-workers 32 \
  --facts-dir "<FACTS_DIR>"
```

未配置环境变量时：

```bash
fact-extract run \
  --pdf "<PDF_PATH>" \
  --planner-backend agentic \
  --extractor-backend llm-once \
  --model "<MODEL>" \
  --api-base "<API_BASE>" \
  --api-key "<YOUR_API_KEY>" \
  --max-workers 32 \
  --facts-dir "<FACTS_DIR>"
```

## 执行前检查

1. 检查命令可用  
   `fact-extract --help`
2. 检查 PDF 路径存在
3. 检查模型配置齐全

## 执行后检查

执行后至少检查：

```bash
jq 'length' "<FACTS_DIR>/manifest.json"
ls "<FACTS_DIR>/sources" | head
ls "<FACTS_DIR>/plans"
```

判定标准：
- `manifest.json` 存在且事实数 > 0
- `sources/` 下有证据文件
- `plans/<book_id>.json` 存在

## 失败重跑

`llm-once` 出现部分任务失败时，从 extract 阶段续跑

```bash
fact-extract run \
  --from extract \
  --plan "<FACTS_DIR>/plans/<BOOK_ID>.json" \
  --extractor-backend llm-once \
  --max-workers 32 \
  --facts-dir "<FACTS_DIR>"
```

若无环境变量，补充 `--model --api-base --api-key`。

## 输出目录

`<FACTS_DIR>/`：
- `plans/<book_id>.json`：计划与任务状态
- `parts/<book_id>/<task_id>/`：分片中间产物
- `manifest.json`：最终事实清单
- `sources/*.txt + *.json`：最终证据（evidence 粒度，json 含完整属性）
- `sections/<book_id>.json`：段落分段结果（`--auto-section` 时生成）
- `logs/agents/<book_id>/`：planner/worker 对话与流日志（流日志包含 `tool_use/tool_result`）

## 任务状态

- 本轮将执行的任务会先置为 `pending`
- 执行结束后更新为 `done` 或 `failed`（并记录 `attempts/fact_count/source_count/error`）
- `run-workers` 默认仅执行非 `done` 任务；`--all` 会重跑全部任务并先置 `pending`

## 证据契约

- Evidence 按段落粒度生成，使用简短 ID（`e1`, `e2`, ...）
- 表格以 HTML `<table>` 格式作为一条 evidence
- 模型返回 `evidence_refs`（如 `["e1", "e3"]`）
- 系统通过 evidence registry 查表还原页码，绑定 `source_ids`
- `source.txt` 存 evidence 文本（段落或表格 HTML）
- `source.json` 包含完整属性：`{"evidence_id":"e1","doc":"...","group":N,"paragraph_index":0,"kind":"section"}`

## 关系提取（enrich）

`fact-extract enrich` 是事实提取的后处理阶段，对已提取的事实进行结构化知识抽取。

### 什么时候用

事实提取完成后（`manifest.json` 和 `sources/` 已生成），需要从事实中提取实体、属性、关系、事件时使用。

### CLI

```bash
fact-extract enrich \
  --manifest <FACTS_DIR>/manifest.json \
  --batch-size 10 \
  --max-workers 32
```

`--batch-size`（默认 10）控制每次 LLM 调用包含的事实数。支持断点续跑，checkpoint 按 fact 级别保存，batch_size 可随时更改。

### 输出

- 中间产物：`<FACTS_DIR>/enriched/<fact_id>.json`
- 最终输出：`<FACTS_DIR>/manifest.enriched.json`

每条事实会被扩充四个字段：

```json
{
  "id": "fact_0001",
  "summary": "孙悟空大闹天宫，打败十万天兵",
  "source_ids": ["e0001"],
  "entities": [
    {"name": "孙悟空", "type": "人物"},
    {"name": "天宫", "type": "地点"}
  ],
  "attributes": [
    {"entity": "孙悟空", "attr": "能力", "value": "七十二变"}
  ],
  "relations": [
    {"subject": "孙悟空", "predicate": "大闹", "object": "天宫"},
    {"subject": "孙悟空", "predicate": "打败", "object": "十万天兵"}
  ],
  "events": [
    {"action": "大闹天宫", "agent": "孙悟空", "patient": "天兵天将", "location": "天宫", "time": null}
  ]
}
```

### 典型流程

```bash
# 1. 事实提取
fact-extract run --pdf book.pdf --facts-dir facts

# 2. 关系提取
fact-extract enrich --manifest facts/manifest.json

# 3. 查看结果
jq '.[0] | {summary, entities, relations}' facts/manifest.enriched.json
```
