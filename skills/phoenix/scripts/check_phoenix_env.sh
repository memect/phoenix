#!/usr/bin/env bash
set -euo pipefail

INSTALL_URL="https://raw.githubusercontent.com/memect/phoenix/main/scripts/install.sh"
INSTALL=0

usage() {
  cat <<'EOF'
Usage: check_phoenix_env.sh [--install]

Checks whether Phoenix commands are available.

Options:
  --install  Install Phoenix with the official installer if commands are missing.
  -h, --help Show this help.
EOF
}

missing_commands() {
  local missing=0

  echo "Checking Phoenix commands..."
  for bin in agentic-extract xdev xdev-config ppx; do
    if command -v "$bin" >/dev/null 2>&1; then
      echo "ok: $bin -> $(command -v "$bin")"
    else
      echo "missing: $bin" >&2
      missing=1
    fi
  done

  return "$missing"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install)
      INSTALL=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if ! missing_commands; then
  if [ "$INSTALL" -ne 1 ]; then
    cat >&2 <<EOF

One or more Phoenix commands are missing.
To install Phoenix, run:
  curl -fsSL $INSTALL_URL | bash

Or rerun this script with:
  $0 --install
EOF
    exit 1
  fi

  echo
  echo "Installing Phoenix..."
  curl -fsSL "$INSTALL_URL" | bash

  echo
  echo "Rechecking Phoenix commands..."
  missing_commands
fi

echo
echo "Current model configuration:"
xdev-config --show
