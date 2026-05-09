---
name: phoenix
version: 0.4.2
title: Phoenix
user-invocable: true
description: >
  Use Phoenix for agentic document extraction from PDFs. Covers the full user
  workflow: install the tool, configure models with xdev-config, put PDFs in a
  directory, describe what fields to extract, run agentic-extract auto/run, and
  inspect or evaluate results with xdev. Also triggers on: Phoenix,
  extract-agent, agentic-extract, xdev, xdev-config, 文档结构化提取, PDF提取,
  自动提取, 自动生成提取程序, 配置模型, 查看提取效果, 评估准确率.
metadata:
  openclaw:
    requires:
      bins:
        - agentic-extract
        - xdev
        - xdev-config
        - ppx
    homepage: https://github.com/memect/phoenix
---

# Phoenix

Use this skill when the user wants to extract structured data from PDFs with Phoenix.

The normal user path is:

1. Install Phoenix.
2. Configure models with `xdev-config`.
3. Put PDFs in a directory.
4. Run `agentic-extract auto` with a natural-language extraction request.
5. Use `xdev` to inspect one document or evaluate the workspace.
6. Feed result problems back into `agentic-extract run`.

## Quick Start

First check whether the package commands exist with the bundled script:

```bash
skills/phoenix/scripts/check_phoenix_env.sh
```

If any command is missing, install Phoenix before continuing. For PDF-directory workflows, prefer the project installer because it installs both Phoenix commands and `ppx`. The script can do this when installation is intended:

```bash
skills/phoenix/scripts/check_phoenix_env.sh --install
```

Configure models:

```bash
xdev-config
xdev-config --show
```

Run from a PDF directory:

```bash
agentic-extract auto \
  --workspace ws \
  --pdfs-dir ./pdfs \
  --message '提取合同编号、甲方、乙方、金额、签署日期'
```

Inspect output:

```bash
xdev list --workspace ws
xdev run --workspace ws --pdf ./pdfs/001.pdf
xdev evaluate --workspace ws
```

Continue improving:

```bash
agentic-extract run \
  --workspace ws \
  --message '金额字段有漏提，继续修正并评估'
```

When waiting for a long `agentic-extract` run, show real progress output. Prefer running the command in the foreground and polling stdout. If the run is already backgrounded, tail the event stream:

```bash
skills/phoenix/scripts/watch_phoenix_events.sh ws
```

## Command Roles

- `agentic-extract auto`: first run from PDFs; prepares data and starts the agent loop.
- `agentic-extract run`: continue iterating an existing workspace.
- `xdev-config`: configure `llm`, `extract-llm`, and optional `label-llm`.
- `xdev run`: see actual extraction output on one PDF or DocJSON.
- `xdev evaluate`: evaluate current `program.py` against labels.
- `xdev list` / `xdev doc`: inspect workspace documents.

## Model Setup

Always guide ordinary users through `xdev-config`; avoid hand-editing JSON.

Phoenix uses:

- `llm`: main agent model for analysis, code generation, and iteration.
- `extract-llm`: extraction model used by generated `program.py` through xdev tools.
- `label-llm`: optional independent labeling model; can be skipped at first.

Read `references/install-and-config.md` when installing, configuring models, choosing provider prefixes, or troubleshooting API setup.

## References

- Read `references/install-and-config.md` for install, `xdev-config`, model roles, and provider prefixes.
- Read `references/run-and-iterate.md` for `agentic-extract auto/run`, budgets, and feedback loops.
- Read `references/progress-output.md` when waiting for long runs or reporting progress.
- Read `references/inspect-and-evaluate.md` for `xdev list/run/doc/evaluate` and result reporting.
- Read `references/workspace-files.md` when explaining workspace outputs.
- Read `references/troubleshooting.md` when commands, model calls, PDF parsing, or workspace data fail.
