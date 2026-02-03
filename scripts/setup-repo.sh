#!/bin/bash
# Setup a new repository with agent files, directories, and optional Raycast scripts
#
# Usage:
#   ./scripts/setup-repo.sh                    # Interactive mode
#   ./scripts/setup-repo.sh <project-name>     # Direct mode
#   ./scripts/setup-repo.sh <path/to/project>  # Path mode
#
# This script copies agent configuration files to a target project directory.
# It creates necessary directories and optionally generates Raycast launcher scripts.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load environment variables
ENV_FILE="$REPO_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Set defaults
PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"
GITHUB_ORGS_STRING="${GITHUB_ORGS:-mbernier,bernierllc}"
IFS=',' read -ra GITHUB_ORGS_ARRAY <<< "$GITHUB_ORGS_STRING"

echo -e "${BLUE}=== Repository Setup ===${NC}"
echo -e "Template source: ${GREEN}$REPO_ROOT${NC}\n"

# Get project path
if [ -n "$1" ]; then
    INPUT="$1"
else
    echo -e "Enter project name or path:"
    echo -e "  - Project name (e.g., 'my-project') will clone/find in $PROJECTS_DIR"
    echo -e "  - Full path (e.g., '/path/to/project') will use that directory"
    echo ""
    read -p "Project: " INPUT
fi

if [ -z "$INPUT" ]; then
    echo -e "${RED}Error: No project specified${NC}"
    exit 1
fi

# Determine if input is a path or project name
if [[ "$INPUT" == /* ]] || [[ "$INPUT" == ~* ]]; then
    # Full path provided
    PROJECT_DIR="${INPUT/#\~/$HOME}"
    PROJECT_NAME=$(basename "$PROJECT_DIR")
else
    # Project name provided
    PROJECT_NAME="$INPUT"
    PROJECT_DIR="$PROJECTS_DIR/$PROJECT_NAME"
fi

# Convert to safe name for scripts
SAFE_NAME=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g')

echo -e "\nProject: ${GREEN}$PROJECT_NAME${NC}"
echo -e "Directory: ${GREEN}$PROJECT_DIR${NC}"

# Check if directory exists, try to clone if not
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "\n${YELLOW}Directory does not exist.${NC}"

    # Try cloning from GitHub
    CLONED=false
    for org in "${GITHUB_ORGS_ARRAY[@]}"; do
        echo -e "Trying to clone from ${BLUE}$org/$PROJECT_NAME${NC}..."
        if git clone "git@github.com:$org/$PROJECT_NAME.git" "$PROJECT_DIR" 2>/dev/null; then
            echo -e "${GREEN}✓ Cloned from $org/$PROJECT_NAME${NC}"
            CLONED=true
            break
        fi
    done

    if [ "$CLONED" = false ]; then
        read -p "Create new directory? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p "$PROJECT_DIR"
            echo -e "${GREEN}✓ Created directory${NC}"
        else
            echo -e "${RED}Aborted${NC}"
            exit 1
        fi
    fi
fi

# Create required directories
echo -e "\n${BLUE}Creating directories...${NC}"
mkdir -p "$PROJECT_DIR/.cursor/rules"
mkdir -p "$PROJECT_DIR/docs"
mkdir -p "$PROJECT_DIR/plans"
echo -e "${GREEN}✓ Created .cursor/rules/, docs/, plans/${NC}"

# Copy agent files (skip if exists)
echo -e "\n${BLUE}Copying agent files...${NC}"
AGENT_FILES=("AGENTINFO.md" "AGENTS.md" "CLAUDE.md" "GEMINI.md" "QWEN.md")

for file in "${AGENT_FILES[@]}"; do
    if [ -f "$REPO_ROOT/$file" ]; then
        if [ -f "$PROJECT_DIR/$file" ]; then
            echo -e "  ${YELLOW}⚠${NC} $file already exists (skipping)"
        else
            cp "$REPO_ROOT/$file" "$PROJECT_DIR/$file"
            echo -e "  ${GREEN}✓${NC} Copied $file"
        fi
    fi
done

# Copy CURSOR.mdc
CURSOR_SRC="$REPO_ROOT/.cursor/rules/CURSOR.mdc"
CURSOR_DST="$PROJECT_DIR/.cursor/rules/CURSOR.mdc"
if [ -f "$CURSOR_SRC" ]; then
    if [ -f "$CURSOR_DST" ]; then
        echo -e "  ${YELLOW}⚠${NC} CURSOR.mdc already exists (skipping)"
    else
        cp "$CURSOR_SRC" "$CURSOR_DST"
        echo -e "  ${GREEN}✓${NC} Copied CURSOR.mdc to .cursor/rules/"
    fi
fi

# Update .gitignore
echo -e "\n${BLUE}Updating .gitignore...${NC}"
GITIGNORE="$PROJECT_DIR/.gitignore"
[ ! -f "$GITIGNORE" ] && touch "$GITIGNORE"

PATTERNS=("AGENTINFO.md" "AGENTS.md" "CLAUDE.md" "GEMINI.md" "QWEN.md" ".cursor/rules" "/plans/")
for pattern in "${PATTERNS[@]}"; do
    if ! grep -Fxq "$pattern" "$GITIGNORE" 2>/dev/null; then
        echo "$pattern" >> "$GITIGNORE"
        echo -e "  ${GREEN}✓${NC} Added $pattern"
    fi
done

# Ask about Raycast scripts
echo ""
read -p "Create Raycast launcher scripts? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    RAYCAST_DIR="$REPO_ROOT/raycast_scripts"
    mkdir -p "$RAYCAST_DIR"

    # Create cursor script
    cat > "$RAYCAST_DIR/cursor-$SAFE_NAME.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title cursor $PROJECT_NAME
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open cursor $PROJECT_NAME project
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

cursor $PROJECT_DIR/

EOF

    # Create claude script
    cat > "$RAYCAST_DIR/claude-$SAFE_NAME.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title claude $PROJECT_NAME
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open claude $PROJECT_NAME project
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

osascript -e 'tell application "Terminal" to do script "cd $PROJECT_DIR/; claude --dangerously-skip-permissions"'

EOF

    # Create claude resume script
    cat > "$RAYCAST_DIR/claude-$SAFE_NAME-resume.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title claude $PROJECT_NAME resume
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open claude $PROJECT_NAME project resume
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

osascript -e 'tell application "Terminal" to do script "cd $PROJECT_DIR/; claude --dangerously-skip-permissions --resume"'

EOF

    chmod +x "$RAYCAST_DIR/cursor-$SAFE_NAME.sh" "$RAYCAST_DIR/claude-$SAFE_NAME.sh" "$RAYCAST_DIR/claude-$SAFE_NAME-resume.sh"
    echo -e "${GREEN}✓ Created Raycast scripts in $RAYCAST_DIR${NC}"
fi

# Summary
echo -e "\n${BLUE}=== Setup Complete ===${NC}"
echo -e "\nProject ready at: ${GREEN}$PROJECT_DIR${NC}"
echo -e "\nNext steps:"
echo -e "  1. ${YELLOW}Edit AGENTINFO.md${NC} with your project-specific info"
echo -e "  2. Review .cursor/rules/CURSOR.mdc for Cursor settings"
echo -e "  3. Start coding with your AI assistant!"
echo ""
