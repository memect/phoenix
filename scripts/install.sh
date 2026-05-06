#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${EXTRACT_AGENT_HOME:-$HOME/.extract-agent}"
PPX_VENV="${EXTRACT_AGENT_PPX_VENV:-$INSTALL_ROOT/venvs/ppx}"
PPX_REPO="${EXTRACT_AGENT_PPX_REPO:-git+https://github.com/memect/memect-ppx.git}"
PPX_PYTHON="${EXTRACT_AGENT_PPX_PYTHON:-3.12}"

PATH_BLOCK_START="# >>> extract-agent >>>"
PATH_BLOCK_END="# <<< extract-agent <<<"

log() {
  printf '%s\n' "$*"
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

detect_shell_rc() {
  if [ -n "${EXTRACT_AGENT_SHELL_RC:-}" ]; then
    printf '%s\n' "$EXTRACT_AGENT_SHELL_RC"
    return
  fi

  case "$(basename "${SHELL:-}")" in
    zsh)
      printf '%s\n' "$HOME/.zshrc"
      ;;
    bash)
      printf '%s\n' "$HOME/.bashrc"
      ;;
    *)
      printf '%s\n' "$HOME/.profile"
      ;;
  esac
}

write_path_block() {
  local rc_file="$1"
  local uv_tool_bin_dir="$2"
  local ppx_bin_dir="$3"
  local tmp_file

  mkdir -p "$(dirname "$rc_file")"
  touch "$rc_file"
  tmp_file="$(mktemp)"

  awk -v start="$PATH_BLOCK_START" -v end="$PATH_BLOCK_END" '
    $0 == start { skip = 1; next }
    $0 == end { skip = 0; next }
    skip != 1 { print }
  ' "$rc_file" > "$tmp_file"

  {
    cat "$tmp_file"
    printf '\n%s\n' "$PATH_BLOCK_START"
    printf 'export PATH="%s:%s:$PATH"\n' "$uv_tool_bin_dir" "$ppx_bin_dir"
    printf '%s\n' "$PATH_BLOCK_END"
  } > "$rc_file"

  rm -f "$tmp_file"
}

verify_command() {
  local command_name="$1"

  command -v "$command_name" >/dev/null 2>&1 ||
    die "$command_name is not on PATH after installation"

  "$command_name" --help >/dev/null 2>&1 ||
    die "$command_name --help failed"
}

command -v uv >/dev/null 2>&1 ||
  die "uv is required. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"

UV_TOOL_BIN_DIR="$(uv tool dir --bin)"
PPX_BIN_DIR="$PPX_VENV/bin"
SHELL_RC="$(detect_shell_rc)"

log "Installing extract-agent with uv tool..."
uv tool install --force extract-agent

if [ ! -x "$PPX_VENV/bin/python" ]; then
  log "Creating ppx virtual environment at $PPX_VENV..."
  mkdir -p "$(dirname "$PPX_VENV")"
  uv venv "$PPX_VENV" --python "$PPX_PYTHON"
else
  log "Using existing ppx virtual environment at $PPX_VENV..."
fi

log "Installing memect-ppx into the ppx virtual environment..."
uv pip install \
  --python "$PPX_VENV/bin/python" \
  --upgrade \
  "$PPX_REPO" \
  onnxruntime \
  opencv-contrib-python

export PATH="$UV_TOOL_BIN_DIR:$PPX_BIN_DIR:$PATH"

log "Writing PATH to $SHELL_RC..."
write_path_block "$SHELL_RC" "$UV_TOOL_BIN_DIR" "$PPX_BIN_DIR"

log "Verifying commands..."
verify_command agentic-extract
verify_command xdev
verify_command ppx

log "Installed extract-agent and ppx."
log "Restart your shell, or run: source \"$SHELL_RC\""
