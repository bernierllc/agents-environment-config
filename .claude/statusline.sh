#!/bin/bash
# Claude Code Status Line
# Displays: Model Name | Progress Bar | Token % | Git Branch | Project Name

# Exit on pipeline failures
set -o pipefail

# ANSI color codes
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
BLUE='\033[34m'
MAGENTA='\033[35m'
RESET='\033[0m'

# Read stdin JSON from Claude Code
INPUT=$(cat)

# Extract workspace info from JSON
CURRENT_DIR=$(echo "$INPUT" | jq -r '.workspace.current_dir // .cwd // empty')
MODEL_NAME=$(echo "$INPUT" | jq -r '.model.display_name // .model.name // .model.id // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')

# Parse transcript JSONL file for actual token usage
CURRENT_TOKENS=0
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
	CURRENT_TOKENS=$(tail -n 100 "$TRANSCRIPT_PATH" 2>/dev/null | \
		jq -s 'map(select(.type == "assistant" and .message.usage and (.isSidechain // false) == false)) |
		       last | .message.usage |
		       (.input_tokens // 0) + (.output_tokens // 0) +
		       (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)' 2>/dev/null || echo "0")
fi

# Use 160K tokens as threshold (80% of 200K context limit)
BUDGET_TOKENS=160000

# Get git root directory
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)

# Get git branch
BRANCH=""
if [ -n "$GIT_ROOT" ]; then
	BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

# Get project name from BrainGrid
PROJECT_NAME=""
if [ -n "$GIT_ROOT" ] && [ -f "$GIT_ROOT/.braingrid/project.json" ]; then
	PROJECT_NAME=$(jq -r '.name // empty' "$GIT_ROOT/.braingrid/project.json" 2>/dev/null)
fi

# If no BrainGrid project, use directory name
if [ -z "$PROJECT_NAME" ] && [ -n "$CURRENT_DIR" ]; then
	PROJECT_NAME=$(basename "$CURRENT_DIR")
fi

# Calculate token usage percentage
PERCENTAGE=0
if [ "$BUDGET_TOKENS" != "0" ]; then
	PERCENTAGE=$((CURRENT_TOKENS * 100 / BUDGET_TOKENS))
fi

# Choose color based on percentage
if [ "$PERCENTAGE" -ge 90 ]; then
	TOKEN_COLOR="$RED"
elif [ "$PERCENTAGE" -ge 80 ]; then
	TOKEN_COLOR="$YELLOW"
else
	TOKEN_COLOR="$CYAN"
fi

# Create progress bar (20 characters wide)
BAR_WIDTH=20
FILLED=$((PERCENTAGE * BAR_WIDTH / 100))
EMPTY=$((BAR_WIDTH - FILLED))

PROGRESS_BAR="["
for ((i=0; i<FILLED; i++)); do PROGRESS_BAR="${PROGRESS_BAR}█"; done
for ((i=0; i<EMPTY; i++)); do PROGRESS_BAR="${PROGRESS_BAR}░"; done
PROGRESS_BAR="${PROGRESS_BAR}]"

# Build status line components
# 1. Model Name
MODEL_SECTION=""
if [ -n "$MODEL_NAME" ]; then
	MODEL_SECTION="${BLUE}${MODEL_NAME}${RESET}"
fi

# 2. Progress Bar
PROGRESS_SECTION="${TOKEN_COLOR}${PROGRESS_BAR}${RESET}"

# 3. Token Percentage
TOKEN_SECTION="${TOKEN_COLOR}${PERCENTAGE}%${RESET}"

# 4. Git Branch
BRANCH_SECTION=""
if [ -n "$BRANCH" ]; then
	BRANCH_SECTION="${GREEN}${BRANCH}${RESET}"
fi

# 5. Project Name
PROJECT_SECTION=""
if [ -n "$PROJECT_NAME" ]; then
	PROJECT_SECTION="${MAGENTA}${PROJECT_NAME}${RESET}"
fi

# Combine all sections with separators
STATUS_LINE=""
SEP=" ${CYAN}│${RESET} "

if [ -n "$MODEL_SECTION" ]; then
	STATUS_LINE="${MODEL_SECTION}"
fi

if [ -n "$PROGRESS_SECTION" ]; then
	if [ -n "$STATUS_LINE" ]; then STATUS_LINE="${STATUS_LINE}${SEP}"; fi
	STATUS_LINE="${STATUS_LINE}${PROGRESS_SECTION}"
fi

if [ -n "$TOKEN_SECTION" ]; then
	if [ -n "$STATUS_LINE" ]; then STATUS_LINE="${STATUS_LINE}${SEP}"; fi
	STATUS_LINE="${STATUS_LINE}${TOKEN_SECTION}"
fi

if [ -n "$BRANCH_SECTION" ]; then
	if [ -n "$STATUS_LINE" ]; then STATUS_LINE="${STATUS_LINE}${SEP}"; fi
	STATUS_LINE="${STATUS_LINE}${BRANCH_SECTION}"
fi

if [ -n "$PROJECT_SECTION" ]; then
	if [ -n "$STATUS_LINE" ]; then STATUS_LINE="${STATUS_LINE}${SEP}"; fi
	STATUS_LINE="${STATUS_LINE}${PROJECT_SECTION}"
fi

# Output the status line
printf "%b\n" "$STATUS_LINE"

