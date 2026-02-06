#!/bin/bash
# Setup script for agents-environment-config
# Creates ~/.agent-tools/ structure and agent-specific symlinks

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the repository root (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source the AEC home initialization script (creates ~/.agents-environment-config/ if needed)
source "$SCRIPT_DIR/init-aec-home.sh"

echo -e "${BLUE}=== Agents Environment Config Setup ===${NC}\n"
echo -e "Repository location: ${GREEN}$REPO_ROOT${NC}\n"

# Function to update submodules to latest
update_submodules() {
    echo -e "${BLUE}Updating submodules to latest version...${NC}\n"

    # Check if we're in a git repository
    if [ ! -d "$REPO_ROOT/.git" ]; then
        echo -e "  ${YELLOW}⚠${NC} Not a git repository, skipping submodule update"
        return 0
    fi

    # Check if .gitmodules exists
    if [ ! -f "$REPO_ROOT/.gitmodules" ]; then
        echo -e "  ${YELLOW}⚠${NC} No .gitmodules file found, skipping submodule update"
        return 0
    fi

    # Initialize submodules if they don't exist
    echo -n "Initializing submodules... "
    cd "$REPO_ROOT"
    if ! git submodule update --init --recursive > /dev/null 2>&1; then
        echo -e "${RED}✗${NC} Error initializing submodules"
        return 1
    else
        echo -e "${GREEN}✓${NC} Submodules initialized"
    fi

    # Update each submodule to latest from remote
    echo -e "\nUpdating submodules to latest from remote:"

    # Update agents submodule
    if [ -d "$REPO_ROOT/.claude/agents" ]; then
        echo -n "  • Agents... "
        cd "$REPO_ROOT/.claude/agents"
        git fetch origin > /dev/null 2>&1
        if git checkout main > /dev/null 2>&1 && git pull origin main > /dev/null 2>&1; then
            AGENTS_COMMIT=$(git rev-parse --short HEAD)
            echo -e "${GREEN}✓${NC} Updated to $AGENTS_COMMIT"
        else
            echo -e "${YELLOW}⚠${NC} Could not update (may already be up to date)"
        fi
        cd "$REPO_ROOT"
    fi

    # Update skills submodule
    if [ -d "$REPO_ROOT/.claude/skills" ]; then
        echo -n "  • Skills... "
        cd "$REPO_ROOT/.claude/skills"
        git fetch origin > /dev/null 2>&1
        if git checkout main > /dev/null 2>&1 && git pull origin main > /dev/null 2>&1; then
            SKILLS_COMMIT=$(git rev-parse --short HEAD)
            echo -e "${GREEN}✓${NC} Updated to $SKILLS_COMMIT"
        else
            echo -e "${YELLOW}⚠${NC} Could not update (may already be up to date)"
        fi
        cd "$REPO_ROOT"
    fi

    echo ""
    return 0
}

# Function to create symlink with safety checks (for statusline only)
create_symlink() {
    local source="$1"
    local target="$2"
    local description="$3"
    local skip_if_exists="${4:-false}"

    # Check if source exists
    if [ ! -e "$source" ]; then
        echo -e "  ${YELLOW}⚠${NC} Skipping $description: source not found ($source)"
        return 1
    fi

    # Check if target already exists
    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ "$skip_if_exists" = "true" ]; then
            echo -e "  ${YELLOW}⚠${NC} $description already exists (preserving existing file)"
            return 0
        fi

        if [ -L "$target" ]; then
            local current_target=$(readlink "$target")
            if [ "$current_target" = "$source" ]; then
                echo -e "  ${GREEN}✓${NC} $description (already linked)"
                return 0
            else
                echo -e "  ${YELLOW}⚠${NC} $description already exists as symlink to different location"
                echo -e "     Current: $current_target"
                echo -e "     Desired: $source"
                read -p "     Replace? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo -e "     ${YELLOW}Skipped${NC}"
                    return 1
                fi
                rm "$target"
            fi
        else
            echo -e "  ${YELLOW}⚠${NC} $description already exists (not a symlink)"
            read -p "     Backup and replace? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo -e "     ${YELLOW}Skipped${NC}"
                return 1
            fi
            mv "$target" "${target}.backup.$(date +%Y%m%d_%H%M%S)"
        fi
    fi

    mkdir -p "$(dirname "$target")"
    ln -s "$source" "$target"
    echo -e "  ${GREEN}✓${NC} $description"
    return 0
}

# --- Helper: Detect old directory structure ---
has_old_structure() {
    # Check for old-style symlinks that point directly to the repo
    # (not through ~/.agent-tools/)
    local old_found=false

    # Old structure: ~/.claude/agents/agents-environment-config → repo/.claude/agents
    if [ -L "$HOME/.claude/agents/agents-environment-config" ]; then
        local target=$(readlink "$HOME/.claude/agents/agents-environment-config")
        # Old structure points to repo, new structure points to ~/.agent-tools/
        if [[ "$target" != *".agent-tools"* ]] && [[ "$target" == *"agents-environment-config"* || "$target" == *".claude/agents"* ]]; then
            old_found=true
        fi
    fi

    # Old structure: ~/.claude/skills/agents-environment-config → repo/.claude/skills
    if [ -L "$HOME/.claude/skills/agents-environment-config" ]; then
        local target=$(readlink "$HOME/.claude/skills/agents-environment-config")
        if [[ "$target" != *".agent-tools"* ]] && [[ "$target" == *"agents-environment-config"* || "$target" == *".claude/skills"* ]]; then
            old_found=true
        fi
    fi

    # Old structure: ~/.cursor/commands/agents-environment-config → repo/.cursor/commands
    if [ -L "$HOME/.cursor/commands/agents-environment-config" ]; then
        local target=$(readlink "$HOME/.cursor/commands/agents-environment-config")
        if [[ "$target" != *".agent-tools"* ]] && [[ "$target" == *"agents-environment-config"* || "$target" == *".cursor/commands"* ]]; then
            old_found=true
        fi
    fi

    $old_found
}

has_new_structure() {
    # New structure has the .aec-managed marker file
    [ -f "$HOME/.agent-tools/.aec-managed" ]
}

# --- Helper: Detect user content in old locations ---
detect_user_content() {
    # Find files/directories that are NOT our symlinks
    # Returns a list of user content found
    local user_content=()

    # Check ~/.claude/agents/ for user content
    if [ -d "$HOME/.claude/agents" ]; then
        for item in "$HOME/.claude/agents"/*; do
            if [ -e "$item" ]; then
                local name=$(basename "$item")
                if [ "$name" != "agents-environment-config" ]; then
                    user_content+=("~/.claude/agents/$name")
                fi
            fi
        done
    fi

    # Check ~/.claude/skills/ for user content
    if [ -d "$HOME/.claude/skills" ]; then
        for item in "$HOME/.claude/skills"/*; do
            if [ -e "$item" ]; then
                local name=$(basename "$item")
                if [ "$name" != "agents-environment-config" ]; then
                    user_content+=("~/.claude/skills/$name")
                fi
            fi
        done
    fi

    # Check ~/.cursor/rules/ for user content
    if [ -d "$HOME/.cursor/rules" ]; then
        for item in "$HOME/.cursor/rules"/*; do
            if [ -e "$item" ]; then
                local name=$(basename "$item")
                if [ "$name" != "agents-environment-config" ]; then
                    user_content+=("~/.cursor/rules/$name")
                fi
            fi
        done
    fi

    # Check ~/.cursor/commands/ for user content
    if [ -d "$HOME/.cursor/commands" ]; then
        for item in "$HOME/.cursor/commands"/*; do
            if [ -e "$item" ]; then
                local name=$(basename "$item")
                if [ "$name" != "agents-environment-config" ]; then
                    user_content+=("~/.cursor/commands/$name")
                fi
            fi
        done
    fi

    # Return the array (print each item on a line)
    printf '%s\n' "${user_content[@]}"
}

# --- Step 0: Check for existing setup and migration needs ---
echo -e "${BLUE}Checking existing setup...${NC}\n"

if has_new_structure; then
    echo -e "  ${GREEN}✓${NC} New ~/.agent-tools/ structure detected"
    echo -e "  Running setup to update symlinks...\n"
elif has_old_structure; then
    echo -e "  ${YELLOW}⚠${NC} Old directory structure detected!"
    echo ""

    # Detect user content
    USER_CONTENT=$(detect_user_content)

    echo -e "  ${BLUE}What changed:${NC}"
    echo ""
    echo -e "  ${YELLOW}OLD STRUCTURE (your current setup):${NC}"
    echo "    ~/.claude/agents/agents-environment-config → repo/.claude/agents/"
    echo "    ~/.claude/skills/agents-environment-config → repo/.claude/skills/"
    echo "    ~/.cursor/rules/agents-environment-config  → repo/.cursor/rules/"
    echo "    ~/.cursor/commands/agents-environment-config → repo/.cursor/commands/"
    echo "    (Your custom files lived alongside the symlinks)"
    echo ""
    echo -e "  ${GREEN}NEW STRUCTURE (recommended):${NC}"
    echo "    ~/.agent-tools/                    ← NEW centralized directory"
    echo "    ├── rules/agents-environment-config/   → repo/.agent-rules/ (no frontmatter)"
    echo "    ├── agents/agents-environment-config/  → repo/.claude/agents/"
    echo "    ├── skills/agents-environment-config/  → repo/.claude/skills/"
    echo "    ├── commands/agents-environment-config/ → repo/.cursor/commands/"
    echo "    └── [YOUR custom files go here too]"
    echo ""
    echo "    Agent-specific symlinks then point to ~/.agent-tools/"
    echo ""

    # Show user content if any found
    if [ -n "$USER_CONTENT" ]; then
        echo -e "  ${YELLOW}Your custom content detected:${NC}"
        echo "$USER_CONTENT" | while read -r item; do
            if [ -n "$item" ]; then
                echo "    • $item"
            fi
        done
        echo ""
        echo -e "  ${GREEN}Your files will stay in place${NC} - agents will still find them."
        echo "  Only our symlinks are reorganized."
        echo ""
    fi

    echo -e "  ${BLUE}Benefits of migrating:${NC}"
    echo "    • All your tools in one place (~/.agent-tools/)"
    echo "    • Easy to add your own rules/agents/skills alongside ours"
    echo "    • Agent-agnostic rules (no Cursor frontmatter waste)"
    echo "    • Other agents (Gemini, Codex, Qwen) can use ~/.agent-tools/rules/"
    echo ""

    read -p "  Do you want to migrate to the new structure? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo ""
        echo -e "  ${BLUE}Running migration...${NC}\n"
        if [ -f "$SCRIPT_DIR/migrate-to-agent-tools.sh" ]; then
            "$SCRIPT_DIR/migrate-to-agent-tools.sh"
            echo ""
            echo -e "${GREEN}Migration complete!${NC}"
            echo ""
            exit 0
        else
            echo -e "  ${RED}✗${NC} migrate-to-agent-tools.sh not found"
            echo "     Please run: ./scripts/migrate-to-agent-tools.sh manually"
            exit 1
        fi
    else
        # User declined migration - show warning about what will break
        echo ""
        echo -e "  ${RED}════════════════════════════════════════════════════════════════${NC}"
        echo -e "  ${RED}                    IMPORTANT WARNING                           ${NC}"
        echo -e "  ${RED}════════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "  Without migrating, the following may stop working:"
        echo ""
        echo -e "  ${YELLOW}1. Agent rules have moved:${NC}"
        echo "     OLD: repo/.cursor/rules/ (referenced by CLAUDE.md, AGENTS.md, etc.)"
        echo "     NEW: repo/.agent-rules/ (no Cursor frontmatter)"
        echo ""
        echo "     The agent instruction files (CLAUDE.md, AGENTS.md, GEMINI.md, QWEN.md)"
        echo "     now reference .agent-rules/*.md instead of .cursor/rules/*.mdc"
        echo ""
        echo -e "  ${YELLOW}2. Your symlinks point to the old locations:${NC}"
        echo "     Agents using the new repo version expect ~/.agent-tools/"
        echo ""
        echo -e "  ${BLUE}Your options:${NC}"
        echo ""
        echo "  A) Run the migration later:"
        echo "     ./scripts/migrate-to-agent-tools.sh"
        echo ""
        echo "  B) Roll back the repo to an older version:"
        echo "     git log --oneline  # find the commit before this change"
        echo "     git checkout <commit-hash>"
        echo ""
        echo "  C) Continue without changes (not recommended):"
        echo "     Your agents may not find rules/skills/commands correctly."
        echo ""
        echo -e "  ${RED}════════════════════════════════════════════════════════════════${NC}"
        echo ""
        read -p "  Press Enter to exit, or type 'continue' to proceed anyway: " -r
        if [ "$REPLY" != "continue" ]; then
            echo ""
            echo -e "  ${YELLOW}Setup cancelled.${NC} Run ./scripts/setup.sh when ready to migrate."
            exit 1
        fi
        echo ""
        echo -e "  ${YELLOW}Continuing without migration (at your own risk)...${NC}\n"
    fi
else
    echo -e "  ${GREEN}✓${NC} Fresh install detected"
    echo ""
fi

# --- Step 1: Update submodules ---
update_submodules

# --- Step 2: Generate .agent-rules/ directory ---
echo -e "${BLUE}Generating .agent-rules/ directory...${NC}\n"

if [ -f "$SCRIPT_DIR/generate-agent-rules.py" ]; then
    if python3 "$SCRIPT_DIR/generate-agent-rules.py" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Generated .agent-rules/ (stripped frontmatter versions)"
    else
        echo -e "  ${YELLOW}⚠${NC} Could not generate .agent-rules/"
        echo "     Run manually: python3 scripts/generate-agent-rules.py"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} generate-agent-rules.py not found"
fi

# --- Step 3: Setup ~/.agent-tools/ structure ---
echo -e "\n${BLUE}Setting up ~/.agent-tools/ structure...${NC}\n"

if [ -f "$SCRIPT_DIR/setup-agent-tools.sh" ]; then
    "$SCRIPT_DIR/setup-agent-tools.sh"
else
    echo -e "  ${RED}✗${NC} setup-agent-tools.sh not found"
    echo "     Please run: ./scripts/setup-agent-tools.sh manually"
fi

# --- Step 4: Claude statusline (optional) ---
if [ ! -f "$HOME/.claude/statusline.sh" ] && [ ! -f "$HOME/.claude/statusline-command.sh" ]; then
    echo ""
    echo -e "${BLUE}Claude Code Statusline${NC}"
    echo -e "This repository includes a fancy statusline for Claude Code that shows:"
    echo -e "  • Model name, token usage, git branch, and project name"
    echo -e "  • Color-coded progress bars and visual indicators"
    echo ""
    read -p "Would you like to install the Claude Code statusline? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_symlink "$REPO_ROOT/.claude/statusline.sh" "$HOME/.claude/statusline.sh" "Claude statusline script"
        create_symlink "$REPO_ROOT/.claude/statusline-command.sh" "$HOME/.claude/statusline-command.sh" "Claude statusline command script"
        echo ""
        echo -e "${BLUE}Statusline installed!${NC} To use it, add this to your ~/.claude/settings.json:"
        echo -e "${GREEN}{${NC}"
        echo -e "${GREEN}  \"statusLine\": {${NC}"
        echo -e "${GREEN}    \"type\": \"command\",${NC}"
        echo -e "${GREEN}    \"command\": \"~/.claude/statusline.sh\",${NC}"
        echo -e "${GREEN}    \"padding\": 0${NC}"
        echo -e "${GREEN}  }${NC}"
        echo -e "${GREEN}}${NC}"
        echo ""
    else
        echo -e "  ${YELLOW}Skipped${NC} statusline installation"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Claude statusline files already exist (skipping)"
fi

# --- Summary ---
echo ""
echo -e "${BLUE}=== Setup Complete ===${NC}\n"
echo -e "${GREEN}✓${NC} All components installed successfully!"
echo ""
echo -e "${BLUE}Directory Structure:${NC}"
echo "  ~/.agent-tools/                     # Centralized agent tools"
echo "  ├── rules/                          # Rules for all agents"
echo "  │   ├── agents-environment-config/  # From this repo (no frontmatter)"
echo "  │   └── [your rules here]"
echo "  ├── agents/"
echo "  │   ├── agents-environment-config/"
echo "  │   └── [your agents here]"
echo "  ├── skills/"
echo "  │   ├── agents-environment-config/"
echo "  │   └── [your skills here]"
echo "  └── commands/"
echo "      ├── agents-environment-config/"
echo "      └── [your commands here]"
echo ""
echo -e "${BLUE}Agent-Specific:${NC}"
echo "  ~/.claude/agents/  → ~/.agent-tools/agents/"
echo "  ~/.claude/skills/  → ~/.agent-tools/skills/"
echo "  ~/.cursor/rules/   → repo/.cursor/rules/ (with Cursor frontmatter)"
echo "  ~/.cursor/commands/ → ~/.agent-tools/commands/"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Copy .env.template to .env and fill in your API keys:"
echo "     cp $REPO_ROOT/.env.template $REPO_ROOT/.env"
echo ""
echo "  2. Restart your AI tools to load the new configuration"
echo ""
echo -e "${BLUE}For other agents (Gemini, Codex, Qwen):${NC}"
echo "  Point them to ~/.agent-tools/rules/ (no Cursor frontmatter)"
echo ""
echo -e "${BLUE}To update later:${NC}"
echo "  cd $REPO_ROOT"
echo "  git pull"
echo "  git submodule update --remote --recursive"
echo "  python3 scripts/generate-agent-rules.py"
echo ""
