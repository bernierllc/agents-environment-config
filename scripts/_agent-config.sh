#!/bin/bash
# AUTO-GENERATED from agents.json - DO NOT EDIT
# Regenerate with: python3 scripts/generate-agent-config.py

# --- Agent names ---
AGENT_NAMES=("claude" "cursor" "gemini" "qwen" "codex")

# --- Instruction files to copy during repo setup ---
AGENT_INSTRUCTION_FILES=("AGENTINFO.md" "CLAUDE.md" "GEMINI.md" "QWEN.md" "AGENTS.md")

# --- Files that need .agent-rules migration checks ---
MIGRATION_FILES=("CLAUDE.md" "GEMINI.md" "QWEN.md" "AGENTS.md")

# --- Patterns to add to .gitignore ---
GITIGNORE_AGENT_PATTERNS=("AGENTINFO.md" "CLAUDE.md" "GEMINI.md" "QWEN.md" "AGENTS.md" ".cursor/rules" "/plans/")

# --- Per-agent configuration (bash 3 compatible, no associative arrays) ---

# Claude Code
AGENT_claude_DISPLAY_NAME="Claude Code"
AGENT_claude_COMMANDS="claude"
AGENT_claude_ALT_PATHS="$HOME/.claude"
AGENT_claude_TERMINAL_LAUNCH="true"
AGENT_claude_LAUNCH_ARGS="--dangerously-skip-permissions"
AGENT_claude_HAS_RESUME="true"
AGENT_claude_RESUME_ARGS="--dangerously-skip-permissions --resume"

# Cursor
AGENT_cursor_DISPLAY_NAME="Cursor"
AGENT_cursor_COMMANDS="cursor"
AGENT_cursor_ALT_PATHS="/Applications/Cursor.app"
AGENT_cursor_TERMINAL_LAUNCH="false"
AGENT_cursor_LAUNCH_TEMPLATE="cursor {path}/"
AGENT_cursor_HAS_RESUME="false"

# Gemini CLI
AGENT_gemini_DISPLAY_NAME="Gemini CLI"
AGENT_gemini_COMMANDS="gemini"
AGENT_gemini_ALT_PATHS=""
AGENT_gemini_TERMINAL_LAUNCH="true"
AGENT_gemini_LAUNCH_ARGS="--yolo"
AGENT_gemini_HAS_RESUME="true"
AGENT_gemini_RESUME_ARGS="--yolo --resume"

# Qwen Code
AGENT_qwen_DISPLAY_NAME="Qwen Code"
AGENT_qwen_COMMANDS="qwen"
AGENT_qwen_ALT_PATHS=""
AGENT_qwen_TERMINAL_LAUNCH="true"
AGENT_qwen_LAUNCH_ARGS="--yolo"
AGENT_qwen_HAS_RESUME="true"
AGENT_qwen_RESUME_ARGS="--yolo --continue"

# Codex
AGENT_codex_DISPLAY_NAME="Codex"
AGENT_codex_COMMANDS="codex"
AGENT_codex_ALT_PATHS=""
AGENT_codex_TERMINAL_LAUNCH="true"
AGENT_codex_LAUNCH_ARGS="--dangerously-bypass-approvals-and-sandbox"
AGENT_codex_HAS_RESUME="true"
AGENT_codex_RESUME_ARGS="resume --last"

# --- Generated agent detection function ---
detect_installed_agents() {
    # Detect which supported agents are installed on this machine.
    # Sets DETECTED_AGENTS as a space-separated list of agent names.
    DETECTED_AGENTS=""

    # Claude Code
    if command -v claude &>/dev/null || [ -d "$HOME/.claude" ]; then
        DETECTED_AGENTS="$DETECTED_AGENTS claude"
    fi

    # Cursor
    if command -v cursor &>/dev/null || [ -d "/Applications/Cursor.app" ]; then
        DETECTED_AGENTS="$DETECTED_AGENTS cursor"
    fi

    # Gemini CLI
    if command -v gemini &>/dev/null; then
        DETECTED_AGENTS="$DETECTED_AGENTS gemini"
    fi

    # Qwen Code
    if command -v qwen &>/dev/null; then
        DETECTED_AGENTS="$DETECTED_AGENTS qwen"
    fi

    # Codex
    if command -v codex &>/dev/null; then
        DETECTED_AGENTS="$DETECTED_AGENTS codex"
    fi

    # Trim leading whitespace
    DETECTED_AGENTS="$(echo "$DETECTED_AGENTS" | xargs)"
}

# --- Generated Raycast launch command function ---
generate_raycast_launch_command() {
    # Generate the launch command portion of a Raycast script.
    # Args: $1=agent_name $2=project_path $3=is_resume(true/false)
    local agent="$1"
    local proj_path="$2"
    local is_resume="${3:-false}"

    case "$agent" in
        claude)
            if [ "$is_resume" = true ]; then
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; claude --dangerously-skip-permissions --resume\"'"
            else
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; claude --dangerously-skip-permissions\"'"
            fi
            ;;
        cursor)
            echo "cursor ${proj_path}/"
            ;;
        gemini)
            if [ "$is_resume" = true ]; then
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; gemini --yolo --resume\"'"
            else
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; gemini --yolo\"'"
            fi
            ;;
        qwen)
            if [ "$is_resume" = true ]; then
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; qwen --yolo --continue\"'"
            else
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; qwen --yolo\"'"
            fi
            ;;
        codex)
            if [ "$is_resume" = true ]; then
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; codex resume --last\"'"
            else
                echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; codex --dangerously-bypass-approvals-and-sandbox\"'"
            fi
            ;;
    esac
}
