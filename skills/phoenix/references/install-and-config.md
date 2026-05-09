# Install and Configure

## Install

Before running Phoenix, check whether the package commands exist with the bundled script:

```bash
skills/phoenix/scripts/check_phoenix_env.sh
```

If any command is missing, install Phoenix. For ordinary users with PDF directories, use the script's install mode:

```bash
skills/phoenix/scripts/check_phoenix_env.sh --install
```

That runs the official installer:

```bash
curl -fsSL https://raw.githubusercontent.com/memect/phoenix/main/scripts/install.sh | bash
```

It installs:

- `agentic-extract`
- `xdev`
- `xdev-config`
- `pdf-ai-explorer`
- `ppx`

Restart the shell, or source the rc file printed by the installer.

If the user only needs Phoenix CLI commands and already has `ppx`, this is enough:

```bash
uv tool install extract-agent
```

Check again:

```bash
skills/phoenix/scripts/check_phoenix_env.sh
```

## Configure Models

Prefer the interactive wizard:

```bash
xdev-config
```

It writes:

- `~/.config/agentic-extract/config.json`
- `~/.config/xdev/config.json`

Verify:

```bash
xdev-config --show
```

The API key is masked in output, so `--show` is suitable for troubleshooting.

## Model Roles

- `llm`: used by `agentic-extract` for supervisor decisions, business analysis, and code generation. Prefer a strong reasoning/code model.
- `extract-llm`: used by xdev extraction tools from generated `program.py`. Prefer good extraction quality; it can be cheaper/faster than `llm`.
- `label-llm`: optional independent labeling model. If not configured, Phoenix falls back to `llm`.

For a first run, configure `llm` and `extract-llm`; skip independent `label-llm` unless needed.

## Model Name Prefixes

Prefer explicit provider prefixes:

```text
openai/gpt-4.1
openai/GLM-5
openai/deepseek-v4-flash
deepseek/deepseek-v4-pro
google/gemini-...
```

Rules:

- OpenAI-compatible endpoints should usually use `openai/<model>`, even when the model brand is not OpenAI.
- Official DeepSeek API should use `deepseek/<model>`.
- Google/Gemini should use `google/<model>` for xdev extract models.
- If uncertain, start with `openai/<model>` and verify with dry-run.

## Non-Interactive Setup

```bash
xdev-config \
  --llm-model openai/GLM-5 \
  --llm-api-base https://your-endpoint/v1 \
  --llm-api-key "$API_KEY" \
  --extract-model openai/deepseek-v4-flash \
  --extract-api-base https://your-endpoint/v1 \
  --extract-api-key "$API_KEY" \
  --yes
```

For CI:

```bash
xdev-config \
  --llm-model openai/GLM-5 \
  --llm-api-base https://your-endpoint/v1 \
  --llm-api-key "$API_KEY" \
  --extract-model openai/deepseek-v4-flash \
  --extract-api-base https://your-endpoint/v1 \
  --extract-api-key "$API_KEY" \
  --non-interactive \
  --yes
```

## Dry Run

After a workspace exists:

```bash
agentic-extract run \
  --workspace ws \
  --message '检查配置' \
  --dry-run
```
