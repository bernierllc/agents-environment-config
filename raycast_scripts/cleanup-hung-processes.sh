#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Cleanup Hung Processes
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🧹
# @raycast.packageName System Cleanup

# Documentation:
# @raycast.description Kills hung/unresponsive processes and runs Docker cleanup (calls scripts/cleanup-hung-processes.sh)
# @raycast.author Matt Bernier

# This Raycast script is a thin wrapper around scripts/cleanup-hung-processes.sh
# All logic is maintained in one place for consistency and reliability.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLEANUP_SCRIPT="$REPO_ROOT/scripts/cleanup-hung-processes.sh"

if [ ! -f "$CLEANUP_SCRIPT" ]; then
    echo "Error: cleanup script not found at $CLEANUP_SCRIPT"
    exit 1
fi

exec "$CLEANUP_SCRIPT"
