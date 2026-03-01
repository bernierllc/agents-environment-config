#!/bin/bash
# Setup a new repository with agent files, directories, and optional Raycast scripts
#
# Usage:
#   ./scripts/setup-repo.sh                    # Interactive mode
#   ./scripts/setup-repo.sh <project-name>     # Direct mode
#   ./scripts/setup-repo.sh <path/to/project>  # Path mode
#   ./scripts/setup-repo.sh --update-all       # Update all previously set up repos
#   ./scripts/setup-repo.sh --list             # List all tracked repos
#   ./scripts/setup-repo.sh --discover         # Discover repos from Raycast scripts
#   ./scripts/setup-repo.sh --discover --auto  # Discover and add without prompting
#
# This is a thin wrapper around the Python CLI (aec).
# All logic is maintained in aec/commands/repo.py for consistency.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Map legacy flags to CLI commands
case "${1:-}" in
    --update-all)
        python3 -m aec repo update --all
        ;;
    --list)
        python3 -m aec repo list
        ;;
    --discover)
        shift
        python3 -m aec discover "$@"
        ;;
    *)
        python3 -m aec repo setup "$@"
        ;;
esac
