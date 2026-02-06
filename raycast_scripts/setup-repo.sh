#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Setup Repository
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🤖
# @raycast.argument1 { "type": "text", "placeholder": "Project name or path", "optional": true }

# Documentation:
# @raycast.description Setup a new repository with agent files (calls scripts/setup-repo.sh)
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

# This Raycast script is a thin wrapper around scripts/setup-repo.sh
# All logic is maintained in one place for consistency.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# If no argument provided, prompt with osascript
if [ -z "$1" ]; then
    # Prompt for setup type
    SETUP_TYPE=$(osascript -e 'choose from list {"Repository name", "Full path"} with prompt "Select input type:" default items {"Repository name"}' 2>/dev/null)

    if [ -z "$SETUP_TYPE" ] || [ "$SETUP_TYPE" = "false" ]; then
        echo "Cancelled"
        exit 0
    fi

    if [ "$SETUP_TYPE" = "Repository name" ]; then
        INPUT=$(osascript -e 'text returned of (display dialog "Enter repository name:" default answer "" buttons {"Cancel", "OK"} default button "OK")' 2>/dev/null)
    else
        INPUT=$(osascript -e 'text returned of (display dialog "Enter full path to project:" default answer "" buttons {"Cancel", "OK"} default button "OK")' 2>/dev/null)
    fi

    if [ -z "$INPUT" ]; then
        echo "Cancelled"
        exit 0
    fi
else
    INPUT="$1"
fi

# Run the main setup script
# Use 'yes' to auto-confirm prompts in non-interactive mode, but 'n' for Raycast scripts question
echo -e "n" | "$REPO_ROOT/scripts/setup-repo.sh" "$INPUT"

# Show completion dialog
PROJECT_NAME=$(basename "$INPUT")
osascript -e "display notification \"Repository setup complete for $PROJECT_NAME\" with title \"Setup Complete\" sound name \"Glass\"" 2>/dev/null || true
