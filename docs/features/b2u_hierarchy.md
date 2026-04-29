# B2U — 自底向上层级聚合

## 概述

将 `summaries.json`（flat list of chunk summaries）递归聚合为树形层级结构 `hierarchy.b2u.json`。

前置步骤：`segment → summary → b2u`

## 数据流

```
summaries.json (1874 items)
  │
  ▼  round 1: LLM 并发分组
343 groups (每组含若干 chunks)
  │
  ▼  round 2
57 groups
  │
  ▼  round 3~7 ...
1 root
  │
  ▼
hierarchy.b2u.json (树形嵌套)
```

## 递归策略

每一轮：
1. 当前层 items 的 summaries 交给 LLM
2. LLM 将**相邻** items 聚合为 groups + 生成 group summary
3. 输出的 groups 作为下一轮输入
4. 直到只剩 1 个 root 节点

轮内通过滑动窗口并发（默认 window_size=200, overlap=20, max_workers=32），轮间串行。

## 分组规则（给 LLM 的指令）

- 只能合并**相邻**片段（保持文本线性顺序）
- 每个片段恰好属于一个组
- 每个组至少 2 个片段
- 为每个组写一句话摘要（≤50 字）

## 输出格式

```json
{
  "type": "group",
  "group_id": "root",
  "summary": "全书概述",
  "children": [
    {
      "type": "group",
      "group_id": "g1_001",
      "summary": "第一部分",
      "children": [
        {
          "type": "group",
          "group_id": "g2_001_001",
          "summary": "子主题",
          "children": [
            {"type": "chunk", "chunk_id": "chunk_0001"},
            {"type": "chunk", "chunk_id": "chunk_0002"}
          ]
        }
      ]
    }
  ]
}
```

- chunk 叶子只存 `chunk_id` 引用（详细内容在 `chunks.json`）
- group_id 编码层级：`g{depth}_{path}`

## 容错处理

- LLM 分组失败 → 整个窗口作为一个 group
- 返回越界/格式错误 → 静默处理
- 某轮无法减少 group 数量 → 强制合并为一个 group（防止无限循环）
- 重叠窗口合并：前窗优先，后窗只取未覆盖部分，自动填补 gap

## CLI 用法

```bash
fact-extract b2u \
  --summaries <dir>/summaries.json \
  --model openai/deepseek-v4-flash \
  --api-base https://api.deepseek.com/v1 \
  --api-key <key> \
  [--window-size 200] \
  [--overlap 20] \
  [--max-workers 32]
```

输出：`{"output": "<dir>/hierarchy.b2u.json"}`

## 完整 pipeline

```bash
# 1. 切分
fact-extract segment --input book.json --output-dir out/ ...

# 2. 摘要
fact-extract summary --chunks out/chunks.json ...

# 3. 层级聚合
fact-extract b2u --summaries out/summaries.json ...

# 输出文件
out/chunks.json          # 语义块（flat list）
out/summaries.json       # 块摘要（flat list）
out/hierarchy.b2u.json   # 层级树
```
