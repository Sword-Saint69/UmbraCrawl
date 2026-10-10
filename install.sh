#!/usr/bin/env bash
# UmbraCrawl installer. Idempotent: safe to re-run.
# Usage:
#   ./install.sh              # venv + package + --help check
#   ./install.sh --dev        # also install test extra and run pytest
#   ./install.sh --skill      # also install the agent skill (OpenCode + Claude Code)
#   ./install.sh --help       # this message
# Env:
#   VENV=~/.local/share/umbracrawl/venv   # override venv location
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-$HOME/.local/share/umbracrawl/venv}"
DEV=0
SKILL=0

for arg in "$@"; do
  case "$arg" in
    --dev) DEV=1 ;;
    --skill) SKILL=1 ;;
    -h|--help)
      sed -n '2,11p' "$0"
      exit 0
      ;;
    *) echo "unknown flag: $arg (see --help)" >&2; exit 1 ;;
  esac
done

# 1. Prereq: python >= 3.10
if ! command -v python3 >/dev/null; then
  echo "error: python3 not found" >&2
  exit 1
fi
PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')"
if [ "$PY_OK" != "1" ]; then
  echo "error: python >= 3.10 required ($(python3 --version 2>&1))" >&2
  exit 1
fi

# 2. Venv
if [ ! -x "$VENV/bin/python" ]; then
  echo "creating venv at $VENV"
  python3 -m venv "$VENV"
fi

# 3. Package (editable)
"$VENV/bin/pip" install -e "$ROOT"

# 4. Optional dev extra + tests
if [ "$DEV" = "1" ]; then
  "$VENV/bin/pip" install -e "$ROOT[dev]"
  "$VENV/bin/python" -m pytest "$ROOT/tests" -q
fi

# 5. Optional skill
if [ "$SKILL" = "1" ]; then
  for dest in "$HOME/.config/opencode/skills" "$HOME/.claude/skills"; do
    mkdir -p "$dest"
    rm -rf "$dest/umbracrawl-research"
    cp -r "$ROOT/skills/umbracrawl-research" "$dest/"
    echo "skill -> $dest/umbracrawl-research"
  done
fi

# 6. Verify
"$VENV/bin/python" -m umbracrawl --help >/dev/null
echo "ok: installed. try: $VENV/bin/python -m umbracrawl \"research a book Dune by Frank Herbert\""
