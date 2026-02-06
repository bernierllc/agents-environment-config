#!/bin/bash
# Migration script for existing users to the new ~/.agent-tools/ structure
# Safely backs up existing symlinks, preserves user content IN PLACE, and creates new symlinks
#
# IMPORTANT: User content is NOT moved - it stays in agent-specific directories
# where the agents can find it. Only our symlinks are reorganized.

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

# Timestamp for backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/.agent-tools-backup-$TIMESTAMP"

# Flags
DRY_RUN=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--verbose]"
            echo ""
            echo "Migrates existing agent configurations to the new ~/.agent-tools/ structure."
            echo ""
            echo "Options:"
            echo "  --dry-run   Preview changes without making them"
            echo "  --verbose   Show detailed output"
            echo "  --help      Show this help message"
            echo ""
            echo "IMPORTANT: User content is NOT moved - it stays where agents can find it."
            echo "Only the agents-environment-config symlinks are reorganized."
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Agent Tools Migration ===${NC}\n"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}\n"
fi

echo -e "Repository: ${GREEN}$REPO_ROOT${NC}"
echo -e "Target: ${GREEN}$AGENT_TOOLS_DIR${NC}"
echo -e "Backup: ${GREEN}$BACKUP_DIR${NC}\n"

# --- Helper Functions ---

is_our_symlink() {
    # Check if a symlink points to something in agents-environment-config
    local path="$1"
    if [ -L "$path" ]; then
        local target=$(readlink "$path")
        if [[ "$target" == *"agents-environment-config"* ]] || \
           [[ "$target" == *".agent-tools"* ]]; then
            return 0
        fi
    fi
    return 1
}

backup_symlink() {
    local path="$1"
    local backup_target="$BACKUP_DIR/symlinks.txt"

    if [ ! -L "$path" ]; then
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${BLUE}[DRY RUN]${NC} Would record symlink: $path"
        return 0
    fi

    mkdir -p "$BACKUP_DIR"
    local target=$(readlink "$path")
    echo "$path -> $target" >> "$backup_target"
    echo -e "  ${GREEN}✓${NC} Recorded symlink: $path"
}

remove_symlink() {
    local path="$1"
    local description="$2"

    if [ ! -L "$path" ]; then
        return 1
    fi

    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${BLUE}[DRY RUN]${NC} Would remove symlink: $path"
        return 0
    fi

    rm "$path"
    echo -e "  ${GREEN}✓${NC} Removed: $description ($path)"
}

create_dir() {
    local path="$1"

    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${BLUE}[DRY RUN]${NC} Would create: $path"
        return 0
    fi

    mkdir -p "$path"
}

create_symlink() {
    local source="$1"
    local target="$2"
    local description="$3"

    if [ ! -e "$source" ]; then
        echo -e "  ${YELLOW}⚠${NC} Skipping $description: source not found ($source)"
        return 1
    fi

    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${BLUE}[DRY RUN]${NC} Would symlink: $target → $source"
        return 0
    fi

    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ -L "$target" ]; then
            rm "$target"
        else
            echo -e "  ${YELLOW}⚠${NC} $target exists and is not a symlink - skipping"
            return 1
        fi
    fi

    mkdir -p "$(dirname "$target")"
    ln -s "$source" "$target"
    echo -e "  ${GREEN}✓${NC} $description"
}

detect_user_content() {
    # Find user content (not our symlinks) in agent directories
    local user_content=()

    for dir in "$CLAUDE_DIR/agents" "$CLAUDE_DIR/skills" "$CURSOR_DIR/rules" "$CURSOR_DIR/commands"; do
        if [ -d "$dir" ]; then
            for item in "$dir"/*; do
                if [ -e "$item" ] && ! is_our_symlink "$item"; then
                    user_content+=("$item")
                fi
            done
        fi
    done

    printf '%s\n' "${user_content[@]}"
}

# --- Step 1: Check if migration is already complete ---
echo -e "${BLUE}Step 1: Checking migration status...${NC}\n"

if [ -f "$AGENT_TOOLS_DIR/.aec-managed" ]; then
    echo -e "  ${GREEN}✓${NC} Migration marker found - structure already exists"
    echo ""
    read -p "Re-run migration to update symlinks? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "\n${YELLOW}Migration skipped${NC}"
        exit 0
    fi
else
    echo -e "  ${YELLOW}!${NC} Migration marker not found - proceeding with migration"
fi

# --- Step 2: Check for user content ---
echo -e "\n${BLUE}Step 2: Checking for user content...${NC}\n"

USER_CONTENT=$(detect_user_content)
if [ -n "$USER_CONTENT" ]; then
    echo -e "  ${GREEN}✓${NC} Found user content (will NOT be moved):"
    echo "$USER_CONTENT" | while read -r item; do
        if [ -n "$item" ]; then
            echo "    • $item"
        fi
    done
    echo ""
    echo -e "  ${BLUE}Note:${NC} Your content stays where agents can find it."
    echo "  Only our agents-environment-config symlinks are reorganized."
else
    echo -e "  ${GREEN}✓${NC} No user content found (only our symlinks)"
fi

# --- Step 3: Backup existing symlinks ---
echo -e "\n${BLUE}Step 3: Recording existing symlinks for backup...${NC}\n"

if [ "$DRY_RUN" = false ]; then
    mkdir -p "$BACKUP_DIR"
fi

# Record old symlinks
for symlink in \
    "$CLAUDE_DIR/agents/agents-environment-config" \
    "$CLAUDE_DIR/skills/agents-environment-config" \
    "$CURSOR_DIR/rules/agents-environment-config" \
    "$CURSOR_DIR/commands/agents-environment-config"; do
    if [ -L "$symlink" ]; then
        backup_symlink "$symlink"
    fi
done

if [ "$DRY_RUN" = false ] && [ -f "$BACKUP_DIR/symlinks.txt" ]; then
    echo -e "  ${GREEN}✓${NC} Symlink backup saved to: $BACKUP_DIR/symlinks.txt"
fi

# --- Step 4: Create ~/.agent-tools/ structure ---
echo -e "\n${BLUE}Step 4: Creating ~/.agent-tools/ structure...${NC}\n"

create_dir "$AGENT_TOOLS_DIR/rules"
create_dir "$AGENT_TOOLS_DIR/agents"
create_dir "$AGENT_TOOLS_DIR/skills"
create_dir "$AGENT_TOOLS_DIR/commands"

# Create marker file
if [ "$DRY_RUN" = false ]; then
    cat > "$AGENT_TOOLS_DIR/.aec-managed" << EOF
# This directory is managed by agents-environment-config
# Created: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Source: $REPO_ROOT
# Migrated from existing setup
#
# STRUCTURE:
# - Our content: ~/.agent-tools/*/agents-environment-config/
# - Your content: stays in ~/.claude/, ~/.cursor/ (where agents find it)
EOF
    echo -e "  ${GREEN}✓${NC} Created .aec-managed marker file"
fi

# --- Step 5: Remove old symlinks ---
echo -e "\n${BLUE}Step 5: Removing old symlinks...${NC}\n"

# Remove old Claude symlinks
remove_symlink "$CLAUDE_DIR/agents/agents-environment-config" "Claude agents"
remove_symlink "$CLAUDE_DIR/skills/agents-environment-config" "Claude skills"

# Remove old Cursor symlinks
remove_symlink "$CURSOR_DIR/rules/agents-environment-config" "Cursor rules"
remove_symlink "$CURSOR_DIR/commands/agents-environment-config" "Cursor commands"

# --- Step 6: Create new symlinks ---
echo -e "\n${BLUE}Step 6: Creating new symlinks...${NC}\n"

# Repo symlinks in ~/.agent-tools/
echo "Creating repo symlinks in ~/.agent-tools/..."
create_symlink "$REPO_ROOT/.agent-rules" "$AGENT_TOOLS_DIR/rules/agents-environment-config" "Rules → repo/.agent-rules/"
create_symlink "$REPO_ROOT/.claude/agents" "$AGENT_TOOLS_DIR/agents/agents-environment-config" "Agents → repo/.claude/agents/"
create_symlink "$REPO_ROOT/.claude/skills" "$AGENT_TOOLS_DIR/skills/agents-environment-config" "Skills → repo/.claude/skills/"
create_symlink "$REPO_ROOT/.cursor/commands" "$AGENT_TOOLS_DIR/commands/agents-environment-config" "Commands → repo/.cursor/commands/"

# Agent-specific symlinks
echo ""
echo "Creating agent-specific symlinks..."

# Claude symlinks (point to ~/.agent-tools/)
if [ -d "$CLAUDE_DIR" ] || [ "$DRY_RUN" = true ]; then
    create_dir "$CLAUDE_DIR/agents"
    create_dir "$CLAUDE_DIR/skills"
    create_symlink "$AGENT_TOOLS_DIR/agents/agents-environment-config" "$CLAUDE_DIR/agents/agents-environment-config" "~/.claude/agents/agents-environment-config"
    create_symlink "$AGENT_TOOLS_DIR/skills/agents-environment-config" "$CLAUDE_DIR/skills/agents-environment-config" "~/.claude/skills/agents-environment-config"
fi

# Cursor symlinks (rules direct to repo for frontmatter, commands via ~/.agent-tools/)
if [ -d "$CURSOR_DIR" ] || [ "$DRY_RUN" = true ]; then
    create_dir "$CURSOR_DIR/rules"
    create_dir "$CURSOR_DIR/commands"
    create_symlink "$REPO_ROOT/.cursor/rules" "$CURSOR_DIR/rules/agents-environment-config" "~/.cursor/rules/agents-environment-config (with frontmatter)"
    create_symlink "$AGENT_TOOLS_DIR/commands/agents-environment-config" "$CURSOR_DIR/commands/agents-environment-config" "~/.cursor/commands/agents-environment-config"
fi

# --- Step 7: Verify ---
echo -e "\n${BLUE}Step 7: Verification...${NC}\n"

VERIFICATION_ERRORS=0

check_symlink() {
    local path="$1"
    local description="$2"

    if [ "$DRY_RUN" = true ]; then
        return 0
    fi

    if [ ! -L "$path" ]; then
        echo -e "  ${RED}✗${NC} $description: not a symlink"
        VERIFICATION_ERRORS=$((VERIFICATION_ERRORS + 1))
        return 1
    fi

    # Check if symlink target exists
    if [ ! -e "$path" ]; then
        echo -e "  ${YELLOW}⚠${NC} $description: symlink target doesn't exist"
        return 1
    fi

    echo -e "  ${GREEN}✓${NC} $description"
}

if [ "$DRY_RUN" = false ]; then
    check_symlink "$AGENT_TOOLS_DIR/rules/agents-environment-config" "~/.agent-tools/rules/agents-environment-config"
    check_symlink "$AGENT_TOOLS_DIR/agents/agents-environment-config" "~/.agent-tools/agents/agents-environment-config"
    check_symlink "$AGENT_TOOLS_DIR/skills/agents-environment-config" "~/.agent-tools/skills/agents-environment-config"
    check_symlink "$AGENT_TOOLS_DIR/commands/agents-environment-config" "~/.agent-tools/commands/agents-environment-config"
fi

# --- Summary ---
echo -e "\n${BLUE}=== Migration Summary ===${NC}\n"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN COMPLETE - No changes were made${NC}"
    echo ""
    echo "Run without --dry-run to apply changes."
else
    if [ $VERIFICATION_ERRORS -eq 0 ]; then
        echo -e "${GREEN}✓ Migration completed successfully${NC}"
    else
        echo -e "${YELLOW}⚠ Migration completed with $VERIFICATION_ERRORS warning(s)${NC}"
    fi

    echo ""
    echo -e "Symlink backup: ${GREEN}$BACKUP_DIR/symlinks.txt${NC}"
    echo ""
    echo -e "${BLUE}What changed:${NC}"
    echo "  • Created ~/.agent-tools/ with repo symlinks"
    echo "  • Updated agent-specific symlinks to point through ~/.agent-tools/"
    echo "  • Cursor rules still point directly to repo (keeps frontmatter)"
    echo ""
    echo -e "${BLUE}Your content:${NC}"
    echo "  • Stayed in place (NOT moved)"
    echo "  • ~/.claude/agents/, ~/.claude/skills/ - your agents/skills"
    echo "  • ~/.cursor/rules/, ~/.cursor/commands/ - your rules/commands"
    echo ""
    echo -e "${BLUE}To rollback:${NC}"
    echo "  ./scripts/rollback-agent-tools.sh $BACKUP_DIR"
fi

echo ""
