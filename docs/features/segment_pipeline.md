# Segment Pipeline

## 概述

独立的文本切分 pipeline，将完整文档切分为语义块（chunks），作为后续 summary / enrich 等步骤的输入。

与 `segmented` extractor 后端不同，本 pipeline 是**独立触发**的，不依赖 plan/task 结构，直接将输入文件切分后输出 `chunks.json`。

## 数据流

```
输入文件（.txt / .json）
  │
  ▼
load_paragraphs()
  │  .txt → 按行读取非空段落
  │  .json → docjson 格式（tree.root.children[].data.textlines）
  ▼
build_sentences()
  │  pysbd 句子切分，生成 s1..sN 编号的 EvidenceItem
  ▼
detect_breakpoints() — 并发
  │  将句子分成滑动窗口（默认 window_size=500, overlap=50）
  │  所有窗口并发发给 LLM（默认 max_workers=32）
  │  收集各窗口断点，合并去重
  ▼
chunk_by_breakpoints()
  │  按断点切分为语义块
  ▼
chunks.json  +  breakpoints.json
```

## 并发策略

- 所有滑动窗口**同时**提交到 `ThreadPoolExecutor`，消除串行等待
- 断点结果无顺序依赖，可完全并行
- 对于西游记（52,749 句 → 118 窗口），并发耗时远低于串行

## 输出格式

### `chunks.json`

```json
[
  {
    "chunk_id": "chunk_0001",
    "sentences": [
      {"id": "s1", "text": "..."},
      {"id": "s2", "text": "..."}
    ]
  }
]
```

### `breakpoints.json`

```json
{
  "sentence_count": 52749,
  "breakpoint_count": 1873,
  "breakpoints": [11, 33, ...]
}
```

## 输入格式支持

| 格式 | 说明 |
|------|------|
| `.txt` | 按行读取，非空行为段落 |
| `.json` (docjson) | `tree.root.children[].data.textlines[].text`，经 `clean_text` / `is_noise_line` 过滤 |

## 断点规则

| 应该断开 | 不应该断开 |
|---------|-----------|
| 主体切换（A → B） | 同一事实的补充说明 |
| 事件切换 | 递进关系（并且、进而、从而） |
| 时间跳跃 | 因果链（因为→所以→导致） |
| 论述层级变化 | |

## CLI 用法

```bash
fact-extract segment \
  --input <file.txt 或 file.json> \
  --output-dir <output_dir> \
  --model openai/deepseek-v4-flash \
  --api-base https://api.deepseek.com/v1 \
  --api-key <key> \
  [--window-size 500] \
  [--overlap 50] \
  [--max-workers 32] \
  [--language zh]
```

输出 JSON：`{"chunks": "<output_dir>/chunks.json"}`

## 后续步骤

`chunks.json` 可作为以下命令的输入：

```bash
# 生成摘要
fact-extract summary --chunks <dir>/chunks.json ...

# 实体/关系/事件抽取
fact-extract enrich --chunks <dir>/chunks.json ...
```

## 依赖

- `pysbd>=0.3.4` — 句子边界检测
