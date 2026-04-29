# CLI Dependencies

Status: active
Audience: maintainers
Last verified: 2026-04-27
Source of truth:
- `pyproject.toml`
- `src/extract_agent_common/workspace.py`

## Python Tools

These are installed by `uv sync` and used during development:

| Tool | Package | Purpose |
|------|---------|---------|
| `ruff` | `ruff>=0.8.0` | linting and formatting checks |
| `pytest` | `pytest>=9.0.1`, `pytest-cov>=4.0.0` | tests |
| `mypy` | `mypy>=1.0.0` | optional type checks |
| `tree-sitter` | `tree-sitter>=0.24.0`, `tree-sitter-python>=0.23.0` | Python code parsing |

## Console Scripts

`pyproject.toml` exposes only these user-facing commands:

| Command | Entrypoint | Purpose |
|---------|------------|---------|
| `tree-sitter-cli` | `tree_sitter_cli:app` | inspect Python code structure |
| `xdev` | `xdev.cli:cli` | data import, document viewing, extraction, evaluation |
| `xdev-config` | `xdev.config_cli:cli` | configure xdev and agentic-extract |
| `agentic-extract` | `agentic_extract.cli:cli` | agentic extraction workflow |
| `pdf-ai-explorer` | `pdf_ai_explorer.cli:app` | explore DocJSON/PDF content |

`code-executor`, `evaluation-engine`, `evaluator`, `extract-dev`,
`simple-workflow`, and `agentscope-agent` are not exported as console scripts.
Use `xdev` and `agentic-extract` for current workflows.

## System Tools

| Tool | macOS | Linux | Purpose |
|------|-------|-------|---------|
| `git` | `brew install git` | `apt install git` | workspace initialization and local history |

`src/extract_agent_common/workspace.py` uses `git init` when creating a
workspace. The call is best-effort: if `git` is unavailable, workspace creation
continues and logs a warning.
