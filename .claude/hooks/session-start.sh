#!/bin/bash
# SessionStart hook for Claude Code on the web.
# Ensures dev + signing-test dependencies are installed so the test suite
# (including the aec[org-configs] crypto tests) runs in remote sessions.
set -euo pipefail

# Only do heavy setup in remote (Claude Code on the web) sessions; local
# developers manage their own environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

LOG="/tmp/aec-session-start.log"

# Catalog/skills/agents live in git submodules; init them if possible.
git submodule update --init --recursive >"$LOG" 2>&1 || true

# Editable install with all test deps: typer, typing_extensions, PyYAML,
# pytest stack (dev) plus pinned pynacl (org-configs) for the signing tests.
if {
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev,org-configs]"
} >>"$LOG" 2>&1; then
  echo "aec: dev + org-configs dependencies installed"
else
  echo "aec: dependency install FAILED (see $LOG)"
  tail -n 20 "$LOG"
  exit 1
fi
