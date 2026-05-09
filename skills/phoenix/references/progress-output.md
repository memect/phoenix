# Progress Output

`agentic-extract` emits progress events to stdout and writes the same coarse-grained run events to:

```text
<workspace>/.agent_state/events.jsonl
```

When waiting for a long run, do not only say that the process is running in the background. Show actual output or summarize recent events.

## Preferred: Foreground Run

Run `agentic-extract` in the foreground so stdout remains visible:

```bash
agentic-extract auto \
  --workspace ws \
  --pdfs-dir ./pdfs \
  --message '提取案件名称'
```

The CLI prints events such as:

```text
[run] started
[phase] prepare started
[phase] prepare completed (...)
[iter 1] started
[iter 1 | dev] started ...
[iter 1 | dev] heartbeat (...)
```

For agents using a terminal session, keep the session open and poll it periodically. Report the latest meaningful lines, especially iteration, step, decision, heartbeat, completion, and failures.

## If Already Backgrounded

Tail the workspace event file:

```bash
skills/phoenix/scripts/watch_phoenix_events.sh ws
```

Or directly:

```bash
tail -n 50 -f ws/.agent_state/events.jsonl
```

If the file does not exist yet, wait briefly and retry; early bootstrap may create `.agent_state/` after setup starts.

## Reporting Progress

Report concise live status:

- current iteration
- current step or agent
- latest decision/action
- heartbeat elapsed time
- token usage when present
- final status and summary when completed

Avoid inventing internal details not present in stdout or `events.jsonl`.

