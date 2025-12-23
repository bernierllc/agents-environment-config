#!/bin/bash
# Install git hooks for agent/skill sync system

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the repository root
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_SOURCE_DIR="$REPO_ROOT/scripts/git-hooks"
HOOKS_TARGET_DIR="$REPO_ROOT/.git/hooks"

echo -e "${BLUE}=== Installing Git Hooks for Agent/Skill Sync ===${NC}\n"

# Validation counters
ERRORS=0
WARNINGS=0

# Check if .git directory exists
if [ ! -d "$REPO_ROOT/.git" ]; then
    echo -e "${RED}✗ Error: .git directory not found${NC}"
    echo "  This script must be run from a git repository"
    exit 1
fi

# Check Python 3
echo -n "Checking Python 3... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓${NC} Found: $PYTHON_VERSION"
else
    echo -e "${RED}✗ Not found${NC}"
    echo -e "  ${YELLOW}Warning: Python 3 is required for sync operations${NC}"
    echo "  Install from: https://www.python.org/downloads/"
    ((WARNINGS++))
fi

# Check GitHub CLI
echo -n "Checking GitHub CLI... "
if command -v gh &> /dev/null; then
    GH_VERSION=$(gh --version | head -n 1)
    echo -e "${GREEN}✓${NC} Found: $GH_VERSION"
    
    # Check if authenticated
    echo -n "Checking GitHub CLI authentication... "
    if gh auth status &> /dev/null; then
        GH_USER=$(gh api user --jq .login 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✓${NC} Authenticated as: $GH_USER"
    else
        echo -e "${YELLOW}⚠${NC} Not authenticated"
        echo "  Run: gh auth login"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠${NC} Not found"
    echo "  ${YELLOW}Warning: GitHub CLI required for PR creation${NC}"
    echo "  Install from: https://cli.github.com/"
    ((WARNINGS++))
fi

# Check submodules
echo -n "Checking submodules... "
CLAUDE_AGENTS_DIR="$REPO_ROOT/.claude/agents"
CLAUDE_SKILLS_DIR="$REPO_ROOT/.claude/skills"

if [ -d "$CLAUDE_AGENTS_DIR" ] && [ -d "$CLAUDE_SKILLS_DIR" ]; then
    echo -e "${GREEN}✓${NC} Initialized"
    
    # Check if submodules are on detached HEAD
    echo -n "Checking agents submodule branch... "
    cd "$CLAUDE_AGENTS_DIR"
    if git symbolic-ref -q HEAD &> /dev/null; then
        AGENTS_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        echo -e "${GREEN}✓${NC} On branch: $AGENTS_BRANCH"
    else
        echo -e "${YELLOW}⚠${NC} Detached HEAD"
        echo "  Run: cd .claude/agents && git checkout main"
        ((WARNINGS++))
    fi
    
    echo -n "Checking skills submodule branch... "
    cd "$CLAUDE_SKILLS_DIR"
    if git symbolic-ref -q HEAD &> /dev/null; then
        SKILLS_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        echo -e "${GREEN}✓${NC} On branch: $SKILLS_BRANCH"
    else
        echo -e "${YELLOW}⚠${NC} Detached HEAD"
        echo "  Run: cd .claude/skills && git checkout main"
        ((WARNINGS++))
    fi
    
    cd "$REPO_ROOT"
else
    echo -e "${RED}✗ Not initialized${NC}"
    echo "  Run: git submodule update --init --recursive"
    ((ERRORS++))
fi

echo ""

# Install hooks
if [ $ERRORS -eq 0 ]; then
    echo -e "${BLUE}Installing git hooks...${NC}"
    
    # Ensure hooks directory exists
    mkdir -p "$HOOKS_TARGET_DIR"
    
    # Install pre-push hook
    if [ -f "$HOOKS_SOURCE_DIR/pre-push" ]; then
        cp "$HOOKS_SOURCE_DIR/pre-push" "$HOOKS_TARGET_DIR/pre-push"
        chmod +x "$HOOKS_TARGET_DIR/pre-push"
        echo -e "  ${GREEN}✓${NC} Installed pre-push hook"
    else
        echo -e "  ${RED}✗${NC} pre-push hook not found"
        ((ERRORS++))
    fi
    
    # Install post-merge hook
    if [ -f "$HOOKS_SOURCE_DIR/post-merge" ]; then
        cp "$HOOKS_SOURCE_DIR/post-merge" "$HOOKS_TARGET_DIR/post-merge"
        chmod +x "$HOOKS_TARGET_DIR/post-merge"
        echo -e "  ${GREEN}✓${NC} Installed post-merge hook"
    else
        echo -e "  ${RED}✗${NC} post-merge hook not found"
        ((ERRORS++))
    fi
else
    echo -e "${RED}Skipping hook installation due to errors${NC}"
fi

echo ""
echo -e "${BLUE}=== Installation Summary ===${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ Git hooks installed successfully${NC}"
else
    echo -e "${RED}✗ Installation completed with $ERRORS error(s)${NC}"
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS warning(s) - some features may not work${NC}"
fi

echo ""
echo -e "${BLUE}Usage:${NC}"
echo "  • Sync will run automatically on git push and git pull/merge"
echo "  • Skip sync: SKIP_SYNC=1 git push"
echo "  • Skip all hooks: git push --no-verify"
echo ""
echo -e "${BLUE}Troubleshooting:${NC}"
echo "  • Submodules not initialized: git submodule update --init --recursive"
echo "  • GitHub CLI not authenticated: gh auth login"
echo "  • Submodule on detached HEAD: cd .claude/agents && git checkout main"
echo ""

if [ $ERRORS -eq 0 ]; then
    exit 0
else
    exit 1
fi

