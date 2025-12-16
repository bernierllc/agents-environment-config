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

# Prompt for setup type
SETUP_TYPE=$(osascript -e 'choose from list {"Repository", "File path"} with prompt "Select setup type:" default items {"Repository"}')

if [ -z "$SETUP_TYPE" ] || [ "$SETUP_TYPE" = "false" ]; then
    exit 0
fi

SCRIPT_DIR="$HOME/projects/raycast_scripts"
AGENTS_DIR="$HOME/projects/agents-environment-config"

if [ "$SETUP_TYPE" = "Repository" ]; then
    # Prompt for project directory name
    PROJECT_NAME=$(osascript -e 'text returned of (display dialog "Enter repository name:" default answer "" buttons {"Cancel", "OK"} default button "OK")')
    
    if [ -z "$PROJECT_NAME" ]; then
        exit 0
    fi
    
    # Convert project name to a safe filename (replace spaces and special chars with hyphens)
    SAFE_NAME=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g')
    
    PROJECT_DIR="$HOME/projects/$PROJECT_NAME"
    UNICORN_DIR="/unicorn/$PROJECT_NAME"
    
    # Check if directory exists, if not try to clone from GitHub
    if [ ! -d "$PROJECT_DIR" ] && [ ! -d "$UNICORN_DIR" ]; then
        echo "Directory $PROJECT_DIR and $UNICORN_DIR do not exist. Attempting to clone from GitHub..."
        
        # Try cloning from mbernier's GitHub
        echo "Attempting to clone from mbernier's GitHub..."
        if git clone "git@github.com:mbernier/$PROJECT_NAME.git" "$PROJECT_DIR" 2>/dev/null; then
            echo "Successfully cloned from mbernier/$PROJECT_NAME"
        else
            # Try cloning from bernierllc's GitHub
            echo "Attempting to clone from bernierllc's GitHub..."
            if git clone "git@github.com:bernierllc/$PROJECT_NAME.git" "$PROJECT_DIR" 2>/dev/null; then
                echo "Successfully cloned from bernierllc/$PROJECT_NAME"
            else
                # Check if unicorn directory exists first
                if [ -d "$UNICORN_DIR" ]; then
                    echo "Unicorn directory $UNICORN_DIR already exists. Using existing directory."
                    PROJECT_DIR="$UNICORN_DIR"
                else
                    # Try cloning from unicorn's GitHub
                    echo "Attempting to clone from unicorn's GitHub..."
                    if git clone "git@github.com:unicorn/$PROJECT_NAME.git" "$UNICORN_DIR" 2>/dev/null; then
                        echo "Successfully cloned from unicorn/$PROJECT_NAME"
                        PROJECT_DIR="$UNICORN_DIR"
                    else
                        echo "Error: The git repo does not exist in mbernier, bernierllc, or unicorn's github repos and the directory does not exist. Stopping here." >&2
                        osascript -e "display dialog \"Error: The git repo does not exist in mbernier, bernierllc, or unicorn's github repos and the directory does not exist. Stopping here.\" buttons {\"OK\"} default button \"OK\" with icon stop"
                        exit 1
                    fi
                fi
            fi
        fi
    elif [ -d "$UNICORN_DIR" ]; then
        echo "Unicorn directory $UNICORN_DIR already exists. Using existing directory."
        PROJECT_DIR="$UNICORN_DIR"
    else
        echo "Directory $PROJECT_DIR already exists. Skipping git clone."
    fi
    
    # Use PROJECT_NAME for display purposes
    DISPLAY_NAME="$PROJECT_NAME"
else
    # File path option
    FILE_PATH=$(osascript -e 'text returned of (display dialog "Enter file path relative to ~/projects/ (e.g., EarnLearn/el_new_app):" default answer "" buttons {"Cancel", "OK"} default button "OK")')
    
    if [ -z "$FILE_PATH" ]; then
        exit 0
    fi
    
    PROJECT_DIR="$HOME/projects/$FILE_PATH"
    
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
