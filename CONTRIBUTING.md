# Contributing

Thanks for helping improve Phoenix.

## Development Setup

```bash
git clone https://github.com/memect/phoenix.git
cd phoenix
uv sync
```

Configure models before running agent workflows:

```bash
xdev-config
```

## Common Checks

Run focused tests for the area you changed:

```bash
uv run pytest tests/agentic_extract
uv run pytest tests/xdev
uv run pytest tests/code_executor
```

For formatting and static checks, prefer the existing project tools:

```bash
uv run ruff check src tests
```

## Pull Requests

- Keep changes scoped and explain the user-visible behavior.
- Update `README.md` or files under `docs/` when behavior or commands change.
- Add or update tests for code changes.
- Do not commit secrets, local workspaces, logs, `.env` files, or generated `dist/` artifacts.

## Release Notes

Maintainers should update `docs/CHANGELOG.md` for release-facing changes and follow
`docs/release_process.md`.
