#!/bin/bash
# Setup script for ~/.agent-tools/ directory structure
# Creates a centralized location for agent rules, skills, and commands
# with symlinks to agent-specific directories (Claude, Cursor, etc.)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Target directories
AGENT_TOOLS_DIR="$HOME/.agent-tools"
CLAUDE_DIR="$HOME/.claude"
CURSOR_DIR="$HOME/.cursor"

echo -e "${BLUE}=== Agent Tools Setup ===${NC}\n"
echo -e "Repository: ${GREEN}$REPO_ROOT${NC}"
echo -e "Target: ${GREEN}$AGENT_TOOLS_DIR${NC}\n"

# --- Helper Functions ---

is_claude_installed() {
    command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ]
}

is_cursor_installed() {
    [ -d "$HOME/.cursor" ] && [ -d "$HOME/.cursor/extensions" ] || \
    [ -d "/Applications/Cursor.app" ] || \
    command -v cursor >/dev/null 2>&1
}

create_symlink() {
    local source="$1"
    local target="$2"
    local description="$3"

    # Check if source exists
    if [ ! -e "$source" ]; then
        echo -e "  ${YELLOW}⚠${NC} Skipping $description: source not found ($source)"
        return 1
    fi

    # Check if target already exists
    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ -L "$target" ]; then
            local current_target=$(readlink "$target")
            if [ "$current_target" = "$source" ]; then
                echo -e "  ${GREEN}✓${NC} $description (already linked)"
                return 0
            else
                # Remove old symlink, create new one
                rm "$target"
            fi
        else
            # Not a symlink - this is user content, don't touch it
            echo -e "  ${YELLOW}⚠${NC} $description: target exists and is not a symlink (preserving)"
            return 1
        fi
    fi

    # Create parent directory if needed
    mkdir -p "$(dirname "$target")"

    # Create symlink
    ln -s "$source" "$target"
    echo -e "  ${GREEN}✓${NC} $description"
    return 0
}

# --- Step 1: Create ~/.agent-tools/ structure ---
echo -e "${BLUE}Creating ~/.agent-tools/ structure...${NC}\n"

mkdir -p "$AGENT_TOOLS_DIR"/{rules,agents,skills,commands}

# Create marker file to identify this as a managed directory
echo "# This directory is managed by agents-environment-config" > "$AGENT_TOOLS_DIR/.aec-managed"
echo "# Created: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$AGENT_TOOLS_DIR/.aec-managed"
echo "# Source: $REPO_ROOT" >> "$AGENT_TOOLS_DIR/.aec-managed"

echo -e "  ${GREEN}✓${NC} Created ~/.agent-tools/ directory structure"
echo -e "  ${GREEN}✓${NC} Created .aec-managed marker file"

# --- Step 2: Create repo symlinks in ~/.agent-tools/ ---
echo -e "\n${BLUE}Creating repo symlinks in ~/.agent-tools/...${NC}\n"

# Rules: link to .agent-rules/ (stripped frontmatter for non-Cursor agents)
create_symlink "$REPO_ROOT/.agent-rules" "$AGENT_TOOLS_DIR/rules/agents-environment-config" "Rules (agents-environment-config)"

# Agents: link to .claude/agents/
create_symlink "$REPO_ROOT/.claude/agents" "$AGENT_TOOLS_DIR/agents/agents-environment-config" "Agents (agents-environment-config)"

# Skills: link to .claude/skills/
create_symlink "$REPO_ROOT/.claude/skills" "$AGENT_TOOLS_DIR/skills/agents-environment-config" "Skills (agents-environment-config)"

# Commands: link to .cursor/commands/
create_symlink "$REPO_ROOT/.cursor/commands" "$AGENT_TOOLS_DIR/commands/agents-environment-config" "Commands (agents-environment-config)"

# --- Step 3: Configure Claude-specific symlinks ---
echo -e "\n${BLUE}Configuring agent-specific symlinks...${NC}\n"

if is_claude_installed; then
    echo -e "Claude Code detected - configuring..."
    mkdir -p "$CLAUDE_DIR"/{agents,skills}

    # Claude gets symlinks to ~/.agent-tools/
    create_symlink "$AGENT_TOOLS_DIR/agents/agents-environment-config" "$CLAUDE_DIR/agents/agents-environment-config" "Claude agents"
    create_symlink "$AGENT_TOOLS_DIR/skills/agents-environment-config" "$CLAUDE_DIR/skills/agents-environment-config" "Claude skills"
else
    echo -e "  ${YELLOW}⚠${NC} Claude Code not detected - skipping Claude symlinks"
    echo -e "     (Install later and re-run this script)"
fi

# --- Step 4: Configure Cursor-specific symlinks ---
if is_cursor_installed; then
    echo -e "\nCursor detected - configuring..."
    mkdir -p "$CURSOR_DIR/rules"

    # Cursor gets DIRECT link to .cursor/rules/ (keeps frontmatter)
    # This is different from other agents which use .agent-rules/
    create_symlink "$REPO_ROOT/.cursor/rules" "$CURSOR_DIR/rules/agents-environment-config" "Cursor rules (with frontmatter)"

    # NOTE: ~/.cursor/commands/ is documented but NOT WORKING in Cursor
    # See: https://forum.cursor.com/t/commands-are-not-detected-in-the-global-cursor-directory/150967
    echo -e "  ${YELLOW}ℹ${NC} Cursor global commands not supported (known Cursor bug)"
else
    echo -e "  ${YELLOW}⚠${NC} Cursor not detected - skipping Cursor symlinks"
    echo -e "     (Install later and re-run this script)"
fi

# --- Summary ---
echo -e "\n${BLUE}=== Setup Complete ===${NC}\n"
echo -e "${GREEN}✓${NC} ~/.agent-tools/ directory structure created"
echo ""
echo -e "${BLUE}Directory Structure:${NC}"
echo "  ~/.agent-tools/"
echo "  ├── .aec-managed              # Marker file"
echo "  ├── rules/"
echo "  │   ├── agents-environment-config/ → repo/.agent-rules/"
echo "  │   └── [your rules here]"
echo "  ├── agents/"
echo "  │   ├── agents-environment-config/ → repo/.claude/agents/"
echo "  │   └── [your agents here]"
echo "  ├── skills/"
echo "  │   ├── agents-environment-config/ → repo/.claude/skills/"
echo "  │   └── [your skills here]"
echo "  └── commands/"
echo "      ├── agents-environment-config/ → repo/.cursor/commands/"
echo "      └── [your commands here]"
echo ""
echo -e "${BLUE}Agent-Specific Symlinks:${NC}"

if is_claude_installed; then
    echo "  ~/.claude/agents/agents-environment-config → ~/.agent-tools/agents/agents-environment-config"
    echo "  ~/.claude/skills/agents-environment-config → ~/.agent-tools/skills/agents-environment-config"
fi

if is_cursor_installed; then
    echo "  ~/.cursor/rules/agents-environment-config → repo/.cursor/rules/ (with frontmatter)"
    echo "  ~/.cursor/commands/agents-environment-config → ~/.agent-tools/commands/agents-environment-config"
fi

echo ""
echo -e "${BLUE}Usage:${NC}"
echo "  • Add your own rules to ~/.agent-tools/rules/"
echo "  • Add your own agents to ~/.agent-tools/agents/"
echo "  • Add your own skills to ~/.agent-tools/skills/"
echo "  • Add your own commands to ~/.agent-tools/commands/"
echo ""
echo -e "${BLUE}For other agents (Gemini, Codex, Qwen):${NC}"
echo "  Use ~/.agent-tools/rules/ directly (no Cursor frontmatter)"
echo ""
