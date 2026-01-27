#!/bin/bash
# Simple setup script for agents-environment-config
# Creates symlinks from home directory to repository

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the repository root (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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

# Update submodules first
update_submodules

# Function to create symlink with safety checks
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
            # For config files, don't overwrite existing files (whether symlink or regular file)
            echo -e "  ${YELLOW}⚠${NC} $description already exists (preserving existing file)"
            return 0
        fi
        
        if [ -L "$target" ]; then
            # Check if it's already pointing to the right place
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
    
    # Create parent directory if needed
    mkdir -p "$(dirname "$target")"
    
    # Create symlink
    ln -s "$source" "$target"
    echo -e "  ${GREEN}✓${NC} $description"
    return 0
}


# Create symlinks
echo -e "${BLUE}Creating symlinks...${NC}\n"

# Claude configuration
# Create agents directory if it doesn't exist (users can add their own agents here)
mkdir -p "$HOME/.claude/agents"
create_symlink "$REPO_ROOT/.claude/agents" "$HOME/.claude/agents/agents-environment-config" "Claude agents (agents-environment-config)"
# Create skills directory if it doesn't exist (users can add their own skills here)
mkdir -p "$HOME/.claude/skills"
create_symlink "$REPO_ROOT/.claude/skills" "$HOME/.claude/skills/agents-environment-config" "Claude skills (agents-environment-config)"

# Claude statusline - prompt user if they want it
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

# Cursor configuration
# Create commands directory if it doesn't exist (users can add their own commands here)
mkdir -p "$HOME/.cursor/commands"
create_symlink "$REPO_ROOT/.cursor/commands" "$HOME/.cursor/commands/agents-environment-config" "Cursor commands (agents-environment-config)"
# Create rules directory if it doesn't exist (users can add their own rules here)
mkdir -p "$HOME/.cursor/rules"
create_symlink "$REPO_ROOT/.cursor/rules" "$HOME/.cursor/rules/agents-environment-config" "Cursor rules (agents-environment-config)"

echo ""
echo -e "${BLUE}=== Setup Complete ===${NC}\n"
echo -e "${GREEN}✓${NC} All symlinks created successfully!"
echo ""
echo -e "${BLUE}Directory Structure:${NC}"
echo "  • Agents from this repo: ~/.claude/agents/agents-environment-config/"
echo "  • Your custom agents: ~/.claude/agents/ (add your own .md files here)"
echo "  • Skills from this repo: ~/.claude/skills/agents-environment-config/"
echo "  • Your custom skills: ~/.claude/skills/ (add your own skill folders here)"
echo "  • Cursor commands from this repo: ~/.cursor/commands/agents-environment-config/"
echo "  • Your custom Cursor commands: ~/.cursor/commands/ (add your own .md files here)"
echo "  • Cursor rules from this repo: ~/.cursor/rules/agents-environment-config/"
echo "  • Your custom Cursor rules: ~/.cursor/rules/ (add your own .mdc files here)"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Copy .env.template to .env and fill in your API keys:"
echo "     cp $REPO_ROOT/.env.template $REPO_ROOT/.env"
echo ""
echo "  3. Restart your AI tools to load the new configuration"
echo ""
echo -e "${BLUE}To update later:${NC}"
echo "  cd $REPO_ROOT"
echo "  git pull"
echo "  git submodule update --remote --recursive"
echo ""
