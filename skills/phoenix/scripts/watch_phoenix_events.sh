#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: watch_phoenix_events.sh <workspace> [lines]

Tails Phoenix agentic-extract progress events from:
  <workspace>/.agent_state/events.jsonl

Arguments:
  workspace  Phoenix workspace directory.
  lines      Number of existing lines to show before following. Default: 50.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  usage
  if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    exit 2
  fi
  exit 0
fi

WORKSPACE="$1"
LINES="${2:-50}"
EVENTS_FILE="$WORKSPACE/.agent_state/events.jsonl"

if [ ! -d "$WORKSPACE" ]; then
  echo "workspace does not exist: $WORKSPACE" >&2
  exit 1
fi

if [ ! -f "$EVENTS_FILE" ]; then
  echo "events file does not exist yet: $EVENTS_FILE" >&2
  echo "If agentic-extract just started, wait a few seconds and retry." >&2
  exit 1
fi

tail -n "$LINES" -f "$EVENTS_FILE"
