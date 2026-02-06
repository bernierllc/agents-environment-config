#!/bin/bash
# Initialize the ~/.agents-environment-config/ directory
# This script is sourced by setup.sh, setup-repo.sh, and raycast setup-repo.sh
# to ensure consistent initialization of our home directory structure.
#
# Usage: source this file, then use AEC_HOME_DIR and AEC_SETUP_LOG variables
#
# Variables exported:
#   AEC_HOME_DIR     - Path to ~/.agents-environment-config/
#   AEC_SETUP_LOG    - Path to setup-repo-locations.txt
#   AEC_VERSION      - Current version of agents-environment-config

# Directory and file paths
AEC_HOME_DIR="$HOME/.agents-environment-config"
AEC_SETUP_LOG="$AEC_HOME_DIR/setup-repo-locations.txt"
AEC_README="$AEC_HOME_DIR/README.md"

# Current version (update this when making breaking changes)
AEC_VERSION="2.0.0"

# Initialize the directory structure
init_aec_home() {
    # Step 1: Create directory if it doesn't exist
    if [ ! -d "$AEC_HOME_DIR" ]; then
        mkdir -p "$AEC_HOME_DIR"
    fi

    # Step 2: Create README.md if it doesn't exist
    if [ ! -f "$AEC_README" ]; then
        cat > "$AEC_README" << 'READMEEOF'
# Why is this directory here?

This directory (`~/.agents-environment-config/`) was created by the [agents-environment-config](https://github.com/bernierllc/agents-environment-config) repository scripts.

## Purpose

This directory stores local state and configuration for the agents-environment-config tooling:

| File | Purpose |
|------|---------|
| `setup-repo-locations.txt` | Tracks which project directories have been set up with agent files |
| `README.md` | This file - explains the directory's purpose |

## What is agents-environment-config?

It's a repository that provides:
- Shared rules and standards for AI coding agents (Claude, Cursor, Codex, Gemini, Qwen)
- Setup scripts for configuring new projects with agent files
- Migration tools for keeping agent configurations up to date

## Why track setup locations?

When you run `setup-repo.sh` to configure a project with agent files, the script records the project path here. This allows:

1. **Cascading updates** - When agent file formats change, run `setup-repo.sh --update-all` to update all your projects at once
2. **Re-run detection** - If you run setup on a project that's already configured, the script can offer to check for updates instead of re-copying files
3. **Inventory** - Run `setup-repo.sh --list` to see all projects you've configured

## Can I delete this directory?

Yes, but:
- You'll lose the list of configured projects
- The directory will be recreated next time you run any agents-environment-config script
- Your actual projects are not affected

## Questions?

See the [agents-environment-config repository](https://github.com/bernierllc/agents-environment-config) for documentation.
READMEEOF
    fi

    # Step 3: Create setup-repo-locations.txt if it doesn't exist
    if [ ! -f "$AEC_SETUP_LOG" ]; then
        touch "$AEC_SETUP_LOG"
    fi
}

# Log a project setup to the locations file
# Usage: aec_log_setup "/full/path/to/project"
aec_log_setup() {
    local project_dir="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Ensure directory is initialized
    init_aec_home

    # Get absolute path
    local abs_path
    if [[ "$project_dir" == /* ]]; then
        abs_path="$project_dir"
    else
        abs_path="$(cd "$project_dir" 2>/dev/null && pwd)" || abs_path="$project_dir"
    fi

    # Remove existing entry for this path (if any)
    if [ -f "$AEC_SETUP_LOG" ] && [ -s "$AEC_SETUP_LOG" ]; then
        grep -v "|$abs_path$" "$AEC_SETUP_LOG" > "$AEC_SETUP_LOG.tmp" 2>/dev/null || true
        mv "$AEC_SETUP_LOG.tmp" "$AEC_SETUP_LOG"
    fi

    # Add new entry: timestamp|version|path (path last for easier grep)
    echo "$timestamp|$AEC_VERSION|$abs_path" >> "$AEC_SETUP_LOG"
}

# Check if a project is already in the log
# Usage: if aec_is_logged "/full/path/to/project"; then ...
aec_is_logged() {
    local project_dir="$1"

    if [ ! -f "$AEC_SETUP_LOG" ] || [ ! -s "$AEC_SETUP_LOG" ]; then
        return 1
    fi

    # Get absolute path
    local abs_path
    if [[ "$project_dir" == /* ]]; then
        abs_path="$project_dir"
    else
        abs_path="$(cd "$project_dir" 2>/dev/null && pwd)" || abs_path="$project_dir"
    fi

    grep -q "|$abs_path$" "$AEC_SETUP_LOG" 2>/dev/null
    return $?
}

# Get the logged version for a project
# Usage: version=$(aec_get_version "/full/path/to/project")
aec_get_version() {
    local project_dir="$1"

    if [ ! -f "$AEC_SETUP_LOG" ]; then
        return
    fi

    # Get absolute path
    local abs_path
    if [[ "$project_dir" == /* ]]; then
        abs_path="$project_dir"
    else
        abs_path="$(cd "$project_dir" 2>/dev/null && pwd)" || abs_path="$project_dir"
    fi

    grep "|$abs_path$" "$AEC_SETUP_LOG" 2>/dev/null | tail -1 | cut -d'|' -f2
}

# List all logged projects
# Usage: aec_list_projects
aec_list_projects() {
    if [ ! -f "$AEC_SETUP_LOG" ] || [ ! -s "$AEC_SETUP_LOG" ]; then
        echo "No repositories have been set up yet."
        return
    fi

    while IFS='|' read -r timestamp version path; do
        if [ -d "$path" ]; then
            status="exists"
        else
            status="not found"
        fi
        echo "$timestamp|$version|$path|$status"
    done < "$AEC_SETUP_LOG"
}

# Auto-initialize when sourced
init_aec_home
