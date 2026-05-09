# Inspect and Evaluate

## List Documents

```bash
xdev list --workspace ws
```

Use this to find document IDs and confirm data exists.

## Run One PDF

```bash
xdev run --workspace ws --pdf ./pdfs/001.pdf
```

This is the most useful command for seeing current extractor output on a concrete file.

## Run One DocJSON

```bash
xdev run --workspace ws --docjson ./docs/doc.json
```

`--docjson` auto-detects canonical DocJSON and PPX DocJSON.

## Read Document Text

```bash
xdev doc <doc_id> --workspace ws
```

If output is truncated or the document is too long, use `pdf-ai-explorer` directly on the DocJSON path shown by xdev.

## Evaluate

```bash
xdev evaluate --workspace ws
```

If the local CLI uses `eval` instead of `evaluate`, follow the command help:

```bash
xdev --help
```

Look for:

- overall accuracy
- field-level accuracy
- low-performing fields
- examples where prediction differs from label

Convert findings into a direct next iteration message:

```bash
agentic-extract run \
  --workspace ws \
  --message '评估显示签署日期和金额字段准确率低。请检查错误样本，修正 program.py，并重新评估。'
```

## What to Report

When reporting results, include:

- command run
- PDF or doc ID
- extracted JSON or concise field summary
- obvious missing or incorrect fields
- whether another `agentic-extract run --message '...'` iteration is suggested

