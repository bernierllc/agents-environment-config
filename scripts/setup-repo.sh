#!/bin/bash
# Setup a new repository with agent files, directories, and optional Raycast scripts
#
# Usage:
#   ./scripts/setup-repo.sh                    # Interactive mode
#   ./scripts/setup-repo.sh <project-name>     # Direct mode
#   ./scripts/setup-repo.sh <path/to/project>  # Path mode
#   ./scripts/setup-repo.sh --update-all       # Update all previously set up repos
#   ./scripts/setup-repo.sh --list             # List all tracked repos
#   ./scripts/setup-repo.sh --discover         # Discover repos from Raycast scripts
#   ./scripts/setup-repo.sh --discover --auto  # Discover and add without prompting
#
# This script copies agent configuration files to a target project directory.
# It creates necessary directories and optionally generates Raycast launcher scripts.
# All setups are logged to ~/.agents-environment-config/setup-repo-locations.txt

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source the AEC home initialization script
source "$SCRIPT_DIR/init-aec-home.sh"

# Source generated agent config (from agents.json)
source "$SCRIPT_DIR/_agent-config.sh"

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

# --- Helper Functions ---

list_logged_repos() {
    echo -e "${BLUE}=== Tracked Repositories ===${NC}\n"

    if [ ! -f "$AEC_SETUP_LOG" ] || [ ! -s "$AEC_SETUP_LOG" ]; then
        echo "No repositories have been set up yet."
        echo ""
        echo "Run: ./scripts/setup-repo.sh <project-name>"
        return
    fi

    echo -e "${CYAN}Timestamp                  | Version | Path${NC}"
    echo "---------------------------|---------|-----"

    while IFS='|' read -r timestamp version path; do
        if [ -d "$path" ]; then
            status="${GREEN}✓${NC}"
        else
            status="${RED}✗${NC}"
        fi
        printf "%s | %-7s | %s %b\n" "$timestamp" "$version" "$path" "$status"
    done < "$AEC_SETUP_LOG"

    echo ""
    echo -e "Legend: ${GREEN}✓${NC} = exists, ${RED}✗${NC} = directory not found"
    echo ""
    echo -e "Log file: ${CYAN}$AEC_SETUP_LOG${NC}"
}

needs_agent_rules_migration() {
    local project_dir="$1"

    # Check if any agent file still references .cursor/rules/ instead of .agent-rules/
    # Uses MIGRATION_FILES from sourced _agent-config.sh
    for file in "${MIGRATION_FILES[@]}"; do
        if [ -f "$project_dir/$file" ]; then
            if grep -q '\.cursor/rules.*\.mdc' "$project_dir/$file" 2>/dev/null; then
                return 0  # Needs migration
            fi
        fi
    done
    return 1  # Already migrated or no files
}

migrate_to_agent_rules() {
    local project_dir="$1"
    local dry_run="${2:-false}"
    local changes_made=0

    echo -e "\n${BLUE}Checking $project_dir for .agent-rules migration...${NC}"

    # Uses MIGRATION_FILES from sourced _agent-config.sh
    for file in "${MIGRATION_FILES[@]}"; do
        local filepath="$project_dir/$file"
        if [ -f "$filepath" ]; then
            if grep -q '\.cursor/rules.*\.mdc' "$filepath" 2>/dev/null; then
                if [ "$dry_run" = true ]; then
                    echo -e "  ${YELLOW}Would update${NC}: $file (references .cursor/rules/)"
                else
                    # Replace .cursor/rules/*.mdc with .agent-rules/*.md
                    sed -i.bak 's/\.cursor\/rules\/\([^`]*\)\.mdc/.agent-rules\/\1.md/g' "$filepath"
                    # Also update any "Read relevant `.cursor/rules" text
                    sed -i.bak 's/Read relevant `\.cursor\/rules/Read relevant `.agent-rules/g' "$filepath"
                    sed -i.bak 's/Rules are organized in `\.cursor\/rules/Rules are organized in `.agent-rules/g' "$filepath"
                    rm -f "$filepath.bak"
                    echo -e "  ${GREEN}✓${NC} Updated $file"
                fi
                changes_made=$((changes_made + 1))
            else
                echo -e "  ${GREEN}✓${NC} $file already uses .agent-rules/"
            fi
        fi
    done

    return $changes_made
}

discover_from_scripts() {
    # Discover project paths from existing Raycast launcher scripts.
    # Args: $1=auto (true/false, default false)
    local auto_mode="${1:-false}"

    local raycast_dir="$REPO_ROOT/raycast_scripts"

    echo -e "${BLUE}=== Repo Discovery ===${NC}\n"

    if [ ! -d "$raycast_dir" ]; then
        echo -e "${RED}Raycast scripts directory not found: $raycast_dir${NC}"
        return 1
    fi

    echo -e "Scanning ${GREEN}$raycast_dir${NC} for project paths...\n"

    # Extract paths from scripts
    local -A discovered_paths  # associative array for dedup
    local script_count=0

    for script_file in "$raycast_dir"/*.sh; do
        [ -f "$script_file" ] || continue
        script_count=$((script_count + 1))

        # Pattern 1: Terminal launch - cd path; agent
        while IFS= read -r match; do
            if [ -n "$match" ]; then
                # Clean up: strip trailing / and whitespace
                local clean_path
                clean_path=$(echo "$match" | sed 's|/\?[[:space:]]*$||')
                # Expand ~ to HOME
                clean_path="${clean_path/#\~/$HOME}"
                # Resolve to absolute path if possible
                if [ -d "$clean_path" ]; then
                    clean_path="$(cd "$clean_path" && pwd)"
                fi
                discovered_paths["$clean_path"]=1
            fi
        done < <(grep -oP 'cd\s+\K[^;]+' "$script_file" 2>/dev/null)

        # Pattern 2: Direct launch - cursor path or code path
        while IFS= read -r match; do
            if [ -n "$match" ]; then
                local clean_path
                clean_path=$(echo "$match" | sed 's|/\?[[:space:]]*$||')
                clean_path="${clean_path/#\~/$HOME}"
                if [ -d "$clean_path" ]; then
                    clean_path="$(cd "$clean_path" && pwd)"
                fi
                discovered_paths["$clean_path"]=1
            fi
        done < <(grep -oP '^(?:cursor|code)\s+\K.+' "$script_file" 2>/dev/null)
    done

    local total_discovered=${#discovered_paths[@]}

    if [ "$total_discovered" -eq 0 ]; then
        echo -e "${YELLOW}No project paths found in Raycast scripts.${NC}"
        return 0
    fi

    echo -e "Found ${CYAN}$total_discovered${NC} unique paths from ${CYAN}$script_count${NC} Raycast scripts:\n"

    # Categorize paths
    local -a new_paths=()
    local -a tracked_paths=()
    local -a missing_paths=()

    for path in $(echo "${!discovered_paths[@]}" | tr ' ' '\n' | sort); do
        if aec_is_logged "$path"; then
            tracked_paths+=("$path")
            echo -e "  $path ${DIM:-}(already tracked)${NC}"
        elif [ ! -d "$path" ]; then
            missing_paths+=("$path")
            echo -e "  $path ${RED}(path not found)${NC}"
        else
            new_paths+=("$path")
            echo -e "  $path ${YELLOW}(not tracked)${NC}"
        fi
    done

    echo ""
    echo -e "Already tracked: ${GREEN}${#tracked_paths[@]}${NC}"
    echo -e "New paths to add: ${YELLOW}${#new_paths[@]}${NC}"
    if [ ${#missing_paths[@]} -gt 0 ]; then
        echo -e "Missing on disk: ${RED}${#missing_paths[@]}${NC}"
    fi

    if [ ${#new_paths[@]} -eq 0 ]; then
        echo -e "\n${GREEN}All discovered paths are already tracked. Nothing to do.${NC}"
        return 0
    fi

    echo ""

    if [ "$auto_mode" = true ]; then
        for path in "${new_paths[@]}"; do
            aec_log_setup "$path"
        done
        echo -e "${GREEN}✓ Added ${#new_paths[@]} path(s) to tracking log${NC}"
    else
        read -p "Add ${#new_paths[@]} new path(s) to tracking? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for path in "${new_paths[@]}"; do
                aec_log_setup "$path"
            done
            echo -e "${GREEN}✓ Added ${#new_paths[@]} path(s) to tracking log${NC}"
        else
            echo -e "${YELLOW}Cancelled${NC}"
        fi
    fi
}

clean_agentinfo_redundancy() {
    local project_dir="$1"
    local dry_run="${2:-false}"
    local filepath="$project_dir/AGENTINFO.md"

    if [ ! -f "$filepath" ]; then
        return 0
    fi

    # Check for redundant rule references that should be removed
    if grep -q 'Reference relevant.*rules.*files\|\.cursor/rules\|\.agent-rules' "$filepath" 2>/dev/null; then
        if [ "$dry_run" = true ]; then
            echo -e "  ${YELLOW}Would clean${NC}: AGENTINFO.md (has redundant rule references)"
            echo -e "    ${CYAN}Tip${NC}: Rule locations are in agent-specific files (CLAUDE.md, etc.)"
            echo -e "    ${CYAN}Savings${NC}: ~50-100 tokens per conversation"
        else
            echo -e "  ${YELLOW}⚠${NC} AGENTINFO.md may have redundant rule references"
            echo -e "    ${CYAN}Manual review recommended${NC}:"
            echo -e "    Remove lines referencing .cursor/rules/ or .agent-rules/"
            echo -e "    These are defined in agent-specific files (CLAUDE.md, etc.)"
        fi
        return 1
    fi
    return 0
}

update_single_repo() {
    local project_dir="$1"
    local dry_run="${2:-false}"

    if [ ! -d "$project_dir" ]; then
        echo -e "${RED}✗${NC} Directory not found: $project_dir"
        return 1
    fi

    local old_version=$(aec_get_version "$project_dir")
    echo -e "\n${BLUE}Updating: $project_dir${NC}"
    echo -e "  Logged version: ${old_version:-unknown} → Current: $AEC_VERSION"

    # Check for needed migrations
    if needs_agent_rules_migration "$project_dir"; then
        migrate_to_agent_rules "$project_dir" "$dry_run"
    fi

    clean_agentinfo_redundancy "$project_dir" "$dry_run"

    # Update the log with current version
    if [ "$dry_run" = false ]; then
        aec_log_setup "$project_dir"
    fi
}

update_all_repos() {
    local dry_run="${1:-false}"

    echo -e "${BLUE}=== Update All Tracked Repositories ===${NC}\n"

    if [ ! -f "$AEC_SETUP_LOG" ] || [ ! -s "$AEC_SETUP_LOG" ]; then
        echo "No repositories have been set up yet."
        return
    fi

    if [ "$dry_run" = true ]; then
        echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}\n"
    fi

    local total=0
    local updated=0
    local skipped=0

    while IFS='|' read -r timestamp version path; do
        total=$((total + 1))
        if [ -d "$path" ]; then
            update_single_repo "$path" "$dry_run"
            updated=$((updated + 1))
        else
            echo -e "${YELLOW}⚠${NC} Skipping (not found): $path"
            skipped=$((skipped + 1))
        fi
    done < "$AEC_SETUP_LOG"

    echo -e "\n${BLUE}=== Update Summary ===${NC}"
    echo -e "Total tracked: $total"
    echo -e "Updated: ${GREEN}$updated${NC}"
    echo -e "Skipped: ${YELLOW}$skipped${NC}"

    if [ "$dry_run" = true ]; then
        echo -e "\nRun without --dry-run to apply changes."
    fi
}

copy_fresh_agent_files() {
    local project_dir="$1"

    echo -e "\n${BLUE}Copying agent files...${NC}"
    # Uses AGENT_INSTRUCTION_FILES from sourced _agent-config.sh

    for file in "${AGENT_INSTRUCTION_FILES[@]}"; do
        if [ -f "$REPO_ROOT/$file" ]; then
            if [ -f "$project_dir/$file" ]; then
                echo -e "  ${YELLOW}⚠${NC} $file already exists (skipping)"
            else
                cp "$REPO_ROOT/$file" "$project_dir/$file"
                echo -e "  ${GREEN}✓${NC} Copied $file"
            fi
        fi
    done
}

# --- Main Script ---

# Handle special commands
case "${1:-}" in
    --list|-l)
        list_logged_repos
        exit 0
        ;;
    --update-all)
        update_all_repos false
        exit 0
        ;;
    --update-all-dry-run)
        update_all_repos true
        exit 0
        ;;
    --discover)
        # Check for --auto flag
        if [ "${2:-}" = "--auto" ]; then
            discover_from_scripts true
        else
            discover_from_scripts false
        fi
        exit 0
        ;;
    --help|-h)
        echo "Usage: $0 [options] [project-name-or-path]"
        echo ""
        echo "Options:"
        echo "  --list, -l           List all tracked repositories"
        echo "  --update-all         Update all tracked repositories"
        echo "  --update-all-dry-run Preview updates without making changes"
        echo "  --discover           Discover repos from Raycast scripts (interactive)"
        echo "  --discover --auto    Discover and add repos without prompting"
        echo "  --help, -h           Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                     # Interactive mode"
        echo "  $0 my-project          # Setup project in \$PROJECTS_DIR"
        echo "  $0 /path/to/project    # Setup at specific path"
        echo "  $0 --update-all        # Update all previously setup repos"
        echo "  $0 --discover          # Find repos from Raycast scripts"
        echo ""
        echo "Setup log: $AEC_SETUP_LOG"
        exit 0
        ;;
esac

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

# Check if this repo was previously set up
if aec_is_logged "$PROJECT_DIR"; then
    old_version=$(aec_get_version "$PROJECT_DIR")
    echo -e "\n${CYAN}This repository was previously set up (version: $old_version)${NC}"
    echo ""
    echo "Options:"
    echo "  1) Check for updates (recommended)"
    echo "  2) Fresh setup (overwrites existing files)"
    echo "  3) Cancel"
    echo ""
    read -p "Choice [1]: " -n 1 -r CHOICE
    echo

    case "${CHOICE:-1}" in
        1)
            update_single_repo "$PROJECT_DIR" false
            echo -e "\n${GREEN}✓ Update complete${NC}"
            exit 0
            ;;
        2)
            echo -e "${YELLOW}Proceeding with fresh setup...${NC}"
            ;;
        *)
            echo -e "${YELLOW}Cancelled${NC}"
            exit 0
            ;;
    esac
fi

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

# Copy agent files
copy_fresh_agent_files "$PROJECT_DIR"

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

# Uses GITIGNORE_AGENT_PATTERNS from sourced _agent-config.sh
for pattern in "${GITIGNORE_AGENT_PATTERNS[@]}"; do
    if ! grep -Fxq "$pattern" "$GITIGNORE" 2>/dev/null; then
        echo "$pattern" >> "$GITIGNORE"
        echo -e "  ${GREEN}✓${NC} Added $pattern"
    fi
done

# Log this setup (uses full absolute path)
ABS_PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
aec_log_setup "$ABS_PROJECT_DIR"
echo -e "\n${GREEN}✓${NC} Logged setup to $AEC_SETUP_LOG"

# --- Agent Detection & Raycast ---
# detect_installed_agents() and generate_raycast_launch_command() are
# sourced from _agent-config.sh (generated from agents.json).

generate_raycast_script() {
    # Generate a single Raycast launcher script.
    # Args: $1=agent_name $2=project_name $3=abs_project_path $4=safe_name $5=output_dir $6=is_resume(true/false)
    local agent="$1"
    local proj_name="$2"
    local proj_path="$3"
    local safe="$4"
    local out_dir="$5"
    local is_resume="${6:-false}"

    local title_suffix=""
    local desc_suffix=""
    local filename_suffix=""
    if [ "$is_resume" = true ]; then
        title_suffix=" resume"
        desc_suffix=" resume"
        filename_suffix="-resume"
    fi

    local script_path="$out_dir/${agent}-${safe}${filename_suffix}.sh"

    cat > "$script_path" << RAYEOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title ${agent} ${proj_name}${title_suffix}
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open ${agent} ${proj_name} project${desc_suffix}
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

RAYEOF

    # Append the launch command using generated function from _agent-config.sh
    local launch_cmd
    launch_cmd=$(generate_raycast_launch_command "$agent" "$proj_path" "$is_resume")
    echo "$launch_cmd" >> "$script_path"

    echo "" >> "$script_path"
    chmod +x "$script_path"
}

# Ask about Raycast scripts
echo ""
read -p "Create Raycast launcher scripts? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    detect_installed_agents

    if [ -z "$DETECTED_AGENTS" ]; then
        echo -e "${YELLOW}No supported agents detected on this machine.${NC}"
        echo -e "Supported agents: claude, cursor, gemini, qwen, codex"
        echo -e "Install an agent and re-run setup to generate Raycast scripts."
    else
        echo -e "\n${BLUE}Detected agents:${NC}"
        for agent in $DETECTED_AGENTS; do
            echo -e "  ${GREEN}✓${NC} $agent"
        done

        echo ""
        read -p "Generate Raycast scripts for these agents? (Y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            RAYCAST_DIR="$REPO_ROOT/raycast_scripts"
            mkdir -p "$RAYCAST_DIR"

            SCRIPT_COUNT=0
            for agent in $DETECTED_AGENTS; do
                # Generate the main script
                generate_raycast_script "$agent" "$PROJECT_NAME" "$ABS_PROJECT_DIR" "$SAFE_NAME" "$RAYCAST_DIR" false
                SCRIPT_COUNT=$((SCRIPT_COUNT + 1))

                # Generate resume variant if agent supports it (from _agent-config.sh)
                local has_resume_var="AGENT_${agent}_HAS_RESUME"
                if [ "${!has_resume_var}" = "true" ]; then
                    generate_raycast_script "$agent" "$PROJECT_NAME" "$ABS_PROJECT_DIR" "$SAFE_NAME" "$RAYCAST_DIR" true
                    SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
                fi
            done

            echo -e "${GREEN}✓ Created $SCRIPT_COUNT Raycast script(s) in $RAYCAST_DIR${NC}"
        else
            echo -e "${YELLOW}Skipped Raycast script generation.${NC}"
        fi
    fi
fi

# Summary
echo -e "\n${BLUE}=== Setup Complete ===${NC}"
echo -e "\nProject ready at: ${GREEN}$ABS_PROJECT_DIR${NC}"
echo -e "\nNext steps:"
echo -e "  1. ${YELLOW}Edit AGENTINFO.md${NC} with your project-specific info"
echo -e "  2. Review .cursor/rules/CURSOR.mdc for Cursor settings"
echo -e "  3. Start coding with your AI assistant!"
echo ""
echo -e "${CYAN}Future updates:${NC}"
echo -e "  Run ${GREEN}./scripts/setup-repo.sh --update-all${NC} to cascade updates to all tracked repos"
echo ""
