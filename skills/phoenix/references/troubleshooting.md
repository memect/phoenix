# Troubleshooting

## Commands Missing

Check:

```bash
skills/phoenix/scripts/check_phoenix_env.sh
```

If commands are missing, install the package with the full installer:

```bash
skills/phoenix/scripts/check_phoenix_env.sh --install
```

If only `agentic-extract`, `xdev`, and `xdev-config` are needed and `ppx` is already installed:

```bash
uv tool install extract-agent
```

## Model Configuration Missing

Run:

```bash
xdev-config
xdev-config --show
```

Confirm `llm` and `extract-llm` both have `model`, `api_base`, and masked `api_key`.

## Wrong Provider Prefix

If an OpenAI-compatible endpoint fails, try `openai/<model>` even for GLM or other compatible models.

Official DeepSeek should usually use `deepseek/<model>` for `llm`. xdev `extract-llm` supports `openai` and `google` provider types.

## PDF Parsing Fails

`agentic-extract auto --pdfs-dir` depends on local PDF parsing. Check:

```bash
ppx --help
```

If missing, rerun the full installer.

## Empty or Wrong PDF Directory

Verify the directory contains PDF files:

```bash
find ./pdfs -maxdepth 1 -type f -name '*.pdf'
```

Use an absolute path if the working directory is unclear.

## Workspace Has No Data

Check:

```bash
xdev list --workspace ws
```

If empty, create data through:

```bash
agentic-extract auto --workspace ws --pdfs-dir ./pdfs --message '...'
```

## program.py Fails

Run one document first:

```bash
xdev run --workspace ws --pdf ./pdfs/001.pdf
```

If the error is semantic extraction quality, continue agentic iteration with a focused message. If it is a Python exception, inspect `ws/program.py` and the traceback.
