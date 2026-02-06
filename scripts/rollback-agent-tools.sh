#!/bin/bash
# Rollback script for ~/.agent-tools/ migration
# Restores symlinks from a backup created by migrate-to-agent-tools.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Target directories
AGENT_TOOLS_DIR="$HOME/.agent-tools"
CLAUDE_DIR="$HOME/.claude"
CURSOR_DIR="$HOME/.cursor"

# Check for backup directory argument
BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ]; then
    echo -e "${BLUE}=== Agent Tools Rollback ===${NC}\n"
    echo -e "${YELLOW}Usage: $0 <backup-directory>${NC}"
    echo ""
    echo "Available backups:"
    FOUND_BACKUPS=false
    for dir in "$HOME"/.agent-tools-backup-*; do
        if [ -d "$dir" ]; then
            FOUND_BACKUPS=true
            # Show timestamp and what's in the backup
            if [ -f "$dir/symlinks.txt" ]; then
                SYMLINK_COUNT=$(wc -l < "$dir/symlinks.txt" | tr -d ' ')
                echo "  $dir ($SYMLINK_COUNT symlinks recorded)"
            else
                echo "  $dir (no symlinks.txt found)"
            fi
        fi
    done
    if [ "$FOUND_BACKUPS" = false ]; then
        echo "  (no backups found)"
    fi
    echo ""
    echo "Example:"
    echo "  $0 ~/.agent-tools-backup-20250205_143022"
    exit 1
fi

# Verify backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}Error: Backup directory not found: $BACKUP_DIR${NC}"
    exit 1
fi

# Check for symlinks.txt
if [ ! -f "$BACKUP_DIR/symlinks.txt" ]; then
    echo -e "${RED}Error: No symlinks.txt found in backup directory${NC}"
    echo "This backup may be from an older version or corrupted."
    exit 1
fi

echo -e "${BLUE}=== Agent Tools Rollback ===${NC}\n"
echo -e "Backup source: ${GREEN}$BACKUP_DIR${NC}\n"

# Show what was backed up
echo -e "${BLUE}Backed up symlinks:${NC}"
cat "$BACKUP_DIR/symlinks.txt" | while read -r line; do
    echo "  $line"
done
echo ""

# Confirm
echo -e "${YELLOW}WARNING: This will:${NC}"
echo "  1. Remove current ~/.agent-tools/ directory"
echo "  2. Remove current agent symlinks (agents-environment-config)"
echo "  3. Restore the old symlinks from backup"
echo ""
echo -e "${BLUE}Note:${NC} Your custom content was never moved, so it's still in place."
echo ""
read -p "Continue with rollback? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Rollback cancelled${NC}"
    exit 0
fi

# --- Step 1: Remove new symlinks ---
echo -e "\n${BLUE}Step 1: Removing current symlinks...${NC}\n"

remove_symlink() {
    local path="$1"
    if [ -L "$path" ]; then
        rm "$path"
        echo -e "  ${GREEN}✓${NC} Removed: $path"
    elif [ -e "$path" ]; then
        echo -e "  ${YELLOW}⚠${NC} $path exists but is not a symlink - skipping"
    fi
}

# Claude symlinks
remove_symlink "$CLAUDE_DIR/agents/agents-environment-config"
remove_symlink "$CLAUDE_DIR/skills/agents-environment-config"

# Cursor symlinks
remove_symlink "$CURSOR_DIR/rules/agents-environment-config"
remove_symlink "$CURSOR_DIR/commands/agents-environment-config"

# ~/.agent-tools/ symlinks
remove_symlink "$AGENT_TOOLS_DIR/rules/agents-environment-config"
remove_symlink "$AGENT_TOOLS_DIR/agents/agents-environment-config"
remove_symlink "$AGENT_TOOLS_DIR/skills/agents-environment-config"
remove_symlink "$AGENT_TOOLS_DIR/commands/agents-environment-config"

# --- Step 2: Remove ~/.agent-tools/ ---
echo -e "\n${BLUE}Step 2: Removing ~/.agent-tools/...${NC}\n"

if [ -d "$AGENT_TOOLS_DIR" ]; then
    # Only remove if it's empty or only contains our structure
    if [ -f "$AGENT_TOOLS_DIR/.aec-managed" ]; then
        rm -rf "$AGENT_TOOLS_DIR"
        echo -e "  ${GREEN}✓${NC} Removed ~/.agent-tools/"
    else
        echo -e "  ${YELLOW}⚠${NC} ~/.agent-tools/ doesn't have .aec-managed marker - preserving"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} ~/.agent-tools/ not found"
fi

# --- Step 3: Restore old symlinks ---
echo -e "\n${BLUE}Step 3: Restoring old symlinks...${NC}\n"

while IFS= read -r line; do
    # Parse "path -> target" format
    symlink_path=$(echo "$line" | cut -d' ' -f1)
    symlink_target=$(echo "$line" | cut -d'>' -f2 | sed 's/^ //')

    if [ -n "$symlink_path" ] && [ -n "$symlink_target" ]; then
        # Create parent directory if needed
        mkdir -p "$(dirname "$symlink_path")"

        # Check if target exists
        if [ -e "$symlink_target" ]; then
            ln -s "$symlink_target" "$symlink_path"
            echo -e "  ${GREEN}✓${NC} Restored: $symlink_path → $symlink_target"
        else
            echo -e "  ${YELLOW}⚠${NC} Target doesn't exist, creating anyway: $symlink_path → $symlink_target"
            ln -s "$symlink_target" "$symlink_path"
        fi
    fi
done < "$BACKUP_DIR/symlinks.txt"

# --- Summary ---
echo -e "\n${BLUE}=== Rollback Complete ===${NC}\n"
echo -e "${GREEN}✓${NC} Restored old symlink structure"
echo ""
echo -e "${BLUE}Note:${NC} The backup directory has been preserved at:"
echo "  $BACKUP_DIR"
echo ""
echo "You can delete it manually if no longer needed:"
echo "  rm -rf \"$BACKUP_DIR\""
echo ""
echo -e "${BLUE}To re-run the migration:${NC}"
echo "  ./scripts/migrate-to-agent-tools.sh"
echo ""
