#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Setup Repository
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description Setup a new repository with default files, directories, and Raycast scripts
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

# Load environment variables from .env file if it exists
# Create a .env file in the repository root with:
# GITHUB_ORGS="mbernier,bernierllc,unicorn"
# PROJECTS_DIR="$HOME/projects"
# CUSTOM_DIRS="/unicorn"
SCRIPT_BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_BASE_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    # Source the .env file, exporting variables
    set -a
    source "$ENV_FILE"
    set +a
fi

# Set defaults if not provided in .env
PROJECTS_DIR="${PROJECTS_DIR:-$HOME/projects}"

# Parse GitHub orgs from environment variable (comma-separated)
# Default to mbernier,bernierllc,unicorn if not set
GITHUB_ORGS_STRING="${GITHUB_ORGS:-mbernier,bernierllc,unicorn}"
IFS=',' read -ra GITHUB_ORGS_ARRAY <<< "$GITHUB_ORGS_STRING"

# Parse custom directories from environment variable (comma-separated)
# Default to /unicorn if not set
CUSTOM_DIRS_STRING="${CUSTOM_DIRS:-/unicorn}"
IFS=',' read -ra CUSTOM_DIRS_ARRAY <<< "$CUSTOM_DIRS_STRING"

SCRIPT_DIR="$HOME/projects/raycast_scripts"
AGENTS_DIR="$HOME/projects/agents-environment-config"

# Prompt for setup type
SETUP_TYPE=$(osascript -e 'choose from list {"Repository", "File path"} with prompt "Select setup type:" default items {"Repository"}')

if [ -z "$SETUP_TYPE" ] || [ "$SETUP_TYPE" = "false" ]; then
    exit 0
fi

if [ "$SETUP_TYPE" = "Repository" ]; then
    # Prompt for project directory name
    PROJECT_NAME=$(osascript -e 'text returned of (display dialog "Enter repository name:" default answer "" buttons {"Cancel", "OK"} default button "OK")')
    
    if [ -z "$PROJECT_NAME" ]; then
        exit 0
    fi
    
    # Convert project name to a safe filename (replace spaces and special chars with hyphens)
    SAFE_NAME=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g')
    
    PROJECT_DIR="$PROJECTS_DIR/$PROJECT_NAME"
    
    # Build array of all possible project directories (custom dirs + projects dir)
    ALL_PROJECT_DIRS=("$PROJECT_DIR")
    for custom_dir in "${CUSTOM_DIRS_ARRAY[@]}"; do
        ALL_PROJECT_DIRS+=("$custom_dir/$PROJECT_NAME")
    done
    
    # Check if any directory already exists
    EXISTING_DIR=""
    for dir in "${ALL_PROJECT_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            EXISTING_DIR="$dir"
            break
        fi
    done
    
    if [ -n "$EXISTING_DIR" ]; then
        echo "Directory $EXISTING_DIR already exists. Using existing directory."
        PROJECT_DIR="$EXISTING_DIR"
    else
        # No directory exists, try to clone from GitHub
        echo "Directory $PROJECT_DIR does not exist. Attempting to clone from GitHub..."
        
        # Try cloning from each GitHub org in the array
        CLONED=false
        for org in "${GITHUB_ORGS_ARRAY[@]}"; do
            echo "Attempting to clone from $org's GitHub..."
            if git clone "git@github.com:$org/$PROJECT_NAME.git" "$PROJECT_DIR" 2>/dev/null; then
                echo "Successfully cloned from $org/$PROJECT_NAME"
                CLONED=true
                break
            fi
        done
        
        if [ "$CLONED" = false ]; then
            # Try cloning to custom directories
            for custom_dir in "${CUSTOM_DIRS_ARRAY[@]}"; do
                CUSTOM_PROJECT_DIR="$custom_dir/$PROJECT_NAME"
                for org in "${GITHUB_ORGS_ARRAY[@]}"; do
                    echo "Attempting to clone from $org's GitHub to $CUSTOM_PROJECT_DIR..."
                    if git clone "git@github.com:$org/$PROJECT_NAME.git" "$CUSTOM_PROJECT_DIR" 2>/dev/null; then
                        echo "Successfully cloned from $org/$PROJECT_NAME to $CUSTOM_PROJECT_DIR"
                        PROJECT_DIR="$CUSTOM_PROJECT_DIR"
                        CLONED=true
                        break 2
                    fi
                done
            done
            
            if [ "$CLONED" = false ]; then
                # Build error message with all orgs tried
                ORGS_LIST=$(IFS=', '; echo "${GITHUB_ORGS_ARRAY[*]}")
                CUSTOM_DIRS_LIST=$(IFS=', '; echo "${CUSTOM_DIRS_ARRAY[*]}")
                echo "Error: The git repo does not exist in any of the configured GitHub orgs ($ORGS_LIST) and the directory does not exist in any configured location ($PROJECTS_DIR, $CUSTOM_DIRS_LIST). Stopping here." >&2
                osascript -e "display dialog \"Error: The git repo does not exist in any of the configured GitHub orgs ($ORGS_LIST) and the directory does not exist in any configured location ($PROJECTS_DIR, $CUSTOM_DIRS_LIST). Stopping here.\" buttons {\"OK\"} default button \"OK\" with icon stop"
                exit 1
            fi
        fi
    fi
    
    # Use PROJECT_NAME for display purposes
    DISPLAY_NAME="$PROJECT_NAME"
else
    # File path option
    FILE_PATH=$(osascript -e "text returned of (display dialog \"Enter file path relative to $PROJECTS_DIR/ (e.g., EarnLearn/el_new_app):\" default answer \"\" buttons {\"Cancel\", \"OK\"} default button \"OK\")")
    
    if [ -z "$FILE_PATH" ]; then
        exit 0
    fi
    
    PROJECT_DIR="$PROJECTS_DIR/$FILE_PATH"
    
    # Verify the directory exists
    if [ ! -d "$PROJECT_DIR" ]; then
        echo "Error: Directory $PROJECT_DIR does not exist. Stopping here." >&2
        osascript -e "display dialog \"Error: Directory $PROJECT_DIR does not exist. Stopping here.\" buttons {\"OK\"} default button \"OK\" with icon stop"
        exit 1
    fi
    
    echo "Using existing directory: $PROJECT_DIR"
    
    # Extract the last part of the path for display name and safe name
    DISPLAY_NAME=$(basename "$FILE_PATH")
    SAFE_NAME=$(echo "$DISPLAY_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g')
fi

# Create required directories
mkdir -p "$PROJECT_DIR/.cursor/rules"
mkdir -p "$PROJECT_DIR/docs"
mkdir -p "$PROJECT_DIR/plans"

# Copy agent files from agents-environment-config (only if they don't exist)
AGENT_FILES=("AGENTINFO.md" "AGENTS.md" "CLAUDE.md" "GEMINI.md" "QWEN.md")

for file in "${AGENT_FILES[@]}"; do
    if [ -f "$AGENTS_DIR/$file" ]; then
        if [ -f "$PROJECT_DIR/$file" ]; then
            echo "Skipping $file - already exists in destination"
        else
            cp "$AGENTS_DIR/$file" "$PROJECT_DIR/$file"
            echo "Copied $file"
        fi
    else
        echo "Warning: $file not found in $AGENTS_DIR"
    fi
done

# Copy CURSOR.mdc to .cursor/rules/ directory (only if it doesn't exist)
CURSOR_RULES_FILE="$AGENTS_DIR/.cursor/rules/CURSOR.mdc"
CURSOR_DEST="$PROJECT_DIR/.cursor/rules/CURSOR.mdc"

if [ -f "$CURSOR_RULES_FILE" ]; then
    if [ -f "$CURSOR_DEST" ]; then
        echo "Skipping CURSOR.mdc - already exists in .cursor/rules/"
    else
        cp "$CURSOR_RULES_FILE" "$CURSOR_DEST"
        echo "Copied CURSOR.mdc to .cursor/rules/"
    fi
else
    echo "Warning: CURSOR.mdc not found in $AGENTS_DIR/.cursor/rules/"
fi

# Create or update .gitignore
GITIGNORE="$PROJECT_DIR/.gitignore"

if [ ! -f "$GITIGNORE" ]; then
    touch "$GITIGNORE"
    echo "Created .gitignore"
fi

# Function to check if a pattern exists in .gitignore
pattern_exists() {
    grep -Fxq "$1" "$GITIGNORE" 2>/dev/null
}

# Append patterns to .gitignore if they don't exist
GITIGNORE_PATTERNS=("AGENTINFO.md" "AGENTS.md" "CLAUDE.md" "GEMINI.md" "QWEN.md" ".cursor/rules" "/plans/")

for pattern in "${GITIGNORE_PATTERNS[@]}"; do
    if ! pattern_exists "$pattern"; then
        echo "$pattern" >> "$GITIGNORE"
        echo "Added $pattern to .gitignore"
    fi
done

# Create cursor script
cat > "$SCRIPT_DIR/cursor-$SAFE_NAME.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title cursor $DISPLAY_NAME
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open cursor $DISPLAY_NAME project
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

cursor $PROJECT_DIR/

EOF

# Create claude script
cat > "$SCRIPT_DIR/claude-$SAFE_NAME.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title claude $DISPLAY_NAME
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open claude $DISPLAY_NAME project
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

# Open a new Terminal window and run the claude command
osascript -e 'tell application "Terminal" to do script "cd $PROJECT_DIR/; claude --dangerously-skip-permissions"'

EOF

# Create claude resume script
cat > "$SCRIPT_DIR/claude-$SAFE_NAME-resume.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title claude $DISPLAY_NAME resume
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open claude $DISPLAY_NAME project resume
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

# Open a new Terminal window and run the claude command
osascript -e 'tell application "Terminal" to do script "cd $PROJECT_DIR/; claude --dangerously-skip-permissions --resume"'

EOF

# Make scripts executable
chmod +x "$SCRIPT_DIR/cursor-$SAFE_NAME.sh" "$SCRIPT_DIR/claude-$SAFE_NAME.sh" "$SCRIPT_DIR/claude-$SAFE_NAME-resume.sh"

# Show confirmation
osascript -e "display dialog \"Repository setup complete for $DISPLAY_NAME:\n\nDirectories created:\n- .cursor/rules/\n- docs/\n- plans/\n\nAgent files copied:\n- AGENTINFO.md\n- AGENTS.md\n- CLAUDE.md\n- GEMINI.md\n- QWEN.md\n\n.gitignore updated\n\nRaycast scripts created:\n- cursor-$SAFE_NAME.sh\n- claude-$SAFE_NAME.sh\n- claude-$SAFE_NAME-resume.sh\" buttons {\"OK\"} default button \"OK\""
