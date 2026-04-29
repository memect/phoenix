# Segmented Extractor Backend

## 背景

fact-extract 当前的 evidence 切分基于 docjson 段落结构 + 字符数打包（`bundle_evidence`），不考虑语义边界。`segmented` 后端通过句子级切分 → LLM 断点检测 → 按语义边界分块 → 逐块摘要，提升事实提取的精准度。

## 数据流

```
evidence_items (段落级, e1~e8)
  │
  ▼
_build_sentence_evidence()
  │  section 段落 → pysbd 拆句，table 保留整体
  │  重新编号 e1~eN
  ▼
sentence_items (句子级, e1~eN)
  │
  ▼
_detect_breakpoints_single_window()
  │  全量句子发给 LLM，返回语义断点索引
  │  保存 → segmented_breakpoints.json
  ▼
_chunk_by_breakpoints()
  │  按断点切分为语义块
  ▼
ThreadPoolExecutor (max_workers=32)
  │  每个 chunk 并发调用 LLM：仅返回 {"summary": "..."}
  │  实时保存 → segmented_summaries.json
  ▼
组装 manifest
  │  每个 chunk = 一条 fact
  │  summary: LLM 返回的摘要
  │  source_ids: 该 chunk 包含的所有句子级 e_id
  ▼
_materialize_part_outputs()
  │  写 sources/e1.txt ~ eN.txt (句子级源文本)
  │  写 sources/e1.json ~ eN.json (元数据)
  ▼
manifest.part.json
```

**一个 chunk 对应一条 fact**，断点检测决定了事实的粒度。

## 核心组件

### 句子切分 — `_text.py`

`split_sentences_pysbd(text, language="zh")` 使用 `pysbd` 库进行句子级切分，支持中文。空文本返回 `[]`，无法切分时返回 `[text]`。

### 断点检测 — `extractor.py`

- `_detect_breakpoints_single_window()`: 全量句子一次性发给 LLM 检测语义断点，容错处理（LLM 调用失败则无断点）

**断点规则（给 LLM 的指令）：**

| 应该断开 | 不应该断开 |
|---------|-----------|
| 主体切换 | 同一事实的补充说明 |
| 事件切换 | 递进关系 |
| 时间跳跃 | 因果链 |
| 论述层级变化 | |

### 逐块摘要 — `extractor.py`

每个语义块并发调用 LLM，仅返回一句话摘要。source_ids 由该 chunk 包含的句子 e_id 直接确定，无需 LLM 返回。

### 中间结果文件

保存在 `parts/<book_id>/<task_id>/` 下：

- `segmented_breakpoints.json` — 句子列表 + 断点索引
- `segmented_summaries.json` — 各 chunk 的摘要（实时增量保存）

## 容错处理

- 空 evidence → 直接返回空
- LLM 断点调用失败 → catch exception，无断点（全部作为一个块）
- LLM 返回越界/非整数索引 → 静默丢弃
- 无断点 → 全部句子作为一个块
- chunk 摘要调用失败 → 该 chunk 跳过（不生成 fact）

## 使用方式

```bash
# 全量执行
uv run fact-extract run --extractor-backend segmented \
    --model <model> --api-base <url> --api-key <key> \
    <pdf_path> <facts_dir>

# 批量任务
uv run fact-extract run-workers --extractor-backend segmented \
    --plan <plan.json> --max-workers 4 --all \
    --model <model> --api-base <url> --api-key <key> \
    --facts-dir <facts_dir>

# 单任务
uv run fact-extract extract-task --extractor-backend segmented \
    --plan <plan.json> --task-id <id> \
    --model <model> --api-base <url> --api-key <key> \
    --facts-dir <facts_dir>
```

## 依赖

- `pysbd>=0.3.4` — 句子边界检测库
