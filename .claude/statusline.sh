#!/bin/bash
# Claude Code Status Line
# Displays: Model Name | Progress Bar | Token % | Rate Limits | Git Branch | Project Name

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

# Extract context window info from Claude Code's JSON input
CONTEXT_PERCENTAGE=$(echo "$INPUT" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)
CONTEXT_WINDOW_SIZE=$(echo "$INPUT" | jq -r '.context_window.context_window_size // empty' 2>/dev/null)

# Fallback: parse transcript if context_window fields aren't available
if [ -z "$CONTEXT_PERCENTAGE" ]; then
	CURRENT_TOKENS=0
	if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
		CURRENT_TOKENS=$(tail -n 100 "$TRANSCRIPT_PATH" 2>/dev/null | \
			jq -s 'map(select(.type == "assistant" and .message.usage and (.isSidechain // false) == false)) |
			       last | .message.usage |
			       (.input_tokens // 0) + (.output_tokens // 0) +
			       (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)' 2>/dev/null || echo "0")
	fi
	# Use 80% of context window as budget threshold, default to 200K if unknown
	BUDGET_TOKENS=$(( ${CONTEXT_WINDOW_SIZE:-200000} * 80 / 100 ))
fi

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
if [ -n "$CONTEXT_PERCENTAGE" ]; then
	PERCENTAGE=$CONTEXT_PERCENTAGE
else
	PERCENTAGE=0
	if [ "$BUDGET_TOKENS" != "0" ]; then
		PERCENTAGE=$((CURRENT_TOKENS * 100 / BUDGET_TOKENS))
	fi
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

# 4. Rate Limits (5-hour and 7-day, only shown when available)
RATE_SECTION=""
FIVE_HOUR_PCT=$(echo "$INPUT" | jq -r '.rate_limits.five_hour.used_percentage // empty' 2>/dev/null)
SEVEN_DAY_PCT=$(echo "$INPUT" | jq -r '.rate_limits.seven_day.used_percentage // empty' 2>/dev/null)

rate_color() {
	local pct="${1:-0}"
	local int_pct
	int_pct=$(printf "%.0f" "$pct" 2>/dev/null || echo "0")
	if [ "$int_pct" -ge 80 ]; then
		echo "$RED"
	elif [ "$int_pct" -ge 50 ]; then
		echo "$YELLOW"
	else
		echo "$GREEN"
	fi
}

if [ -n "$FIVE_HOUR_PCT" ] || [ -n "$SEVEN_DAY_PCT" ]; then
	RATE_PARTS=""
	if [ -n "$FIVE_HOUR_PCT" ]; then
		PCT_INT=$(printf "%.0f" "$FIVE_HOUR_PCT" 2>/dev/null || echo "0")
		COLOR=$(rate_color "$FIVE_HOUR_PCT")
		FIVE_HOUR_RESETS=$(echo "$INPUT" | jq -r '.rate_limits.five_hour.resets_at // empty' 2>/dev/null)
		FIVE_HOUR_LABEL="5h:${PCT_INT}%"
		if [ -n "$FIVE_HOUR_RESETS" ]; then
			NOW=$(date +%s)
			DIFF=$(( FIVE_HOUR_RESETS - NOW ))
			if [ "$DIFF" -gt 0 ]; then
				HRS=$(( DIFF / 3600 ))
				MINS=$(( (DIFF % 3600) / 60 ))
				if [ "$HRS" -gt 0 ]; then
					FIVE_HOUR_LABEL="${FIVE_HOUR_LABEL} (resets in ${HRS}h ${MINS}m)"
				else
					FIVE_HOUR_LABEL="${FIVE_HOUR_LABEL} (resets in ${MINS}m)"
				fi
			fi
		fi
		RATE_PARTS="${COLOR}${FIVE_HOUR_LABEL}${RESET}"
	fi
	if [ -n "$SEVEN_DAY_PCT" ]; then
		PCT_INT=$(printf "%.0f" "$SEVEN_DAY_PCT" 2>/dev/null || echo "0")
		COLOR=$(rate_color "$SEVEN_DAY_PCT")
		PART="${COLOR}7d:${PCT_INT}%${RESET}"
		if [ -n "$RATE_PARTS" ]; then
			RATE_PARTS="${RATE_PARTS} ${PART}"
		else
			RATE_PARTS="${PART}"
		fi
	fi
	RATE_SECTION="${RATE_PARTS}"
fi

# 5. Git Branch
BRANCH_SECTION=""
if [ -n "$BRANCH" ]; then
	BRANCH_SECTION="${GREEN}${BRANCH}${RESET}"
fi

# 6. Project Name
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

if [ -n "$RATE_SECTION" ]; then
	if [ -n "$STATUS_LINE" ]; then STATUS_LINE="${STATUS_LINE}${SEP}"; fi
	STATUS_LINE="${STATUS_LINE}${RATE_SECTION}"
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
