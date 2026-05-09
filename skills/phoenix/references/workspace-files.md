# Workspace Files

Important Phoenix workspace paths:

```text
ws/
  business_guide.md
  program.py
  tests/
  docs/
  .xdev/
    schema.json
    data/
    labels/
  .agent_state/
    current.json
    events.jsonl
    iterations/
```

## Meaning

- `program.py`: current extraction implementation. `xdev run` executes this.
- `business_guide.md`: field definitions and business rules distilled by the agent.
- `.xdev/schema.json`: structured output schema.
- `.xdev/data/`: imported document data.
- `.xdev/labels/`: labels used by evaluation.
- `.agent_state/`: agentic-extract runtime state and event history.

For ordinary use, prefer asking `agentic-extract run --message '...'` to revise `program.py`. Manual edits are appropriate when the user explicitly wants to patch extraction code or inspect a bug.

