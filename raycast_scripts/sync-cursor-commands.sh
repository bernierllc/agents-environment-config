#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Sync Cursor Commands
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🔄
# @raycast.description Compare .claude/agents and .claude/skills with .cursor/commands and generate sync prompt

# Documentation:
# @raycast.description Compare .claude/agents and .claude/skills with .cursor/commands and generate sync prompt
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

set -euo pipefail

REPO_DIR="$HOME/projects/agents-environment-config"
CLAUDE_AGENTS_DIR="$REPO_DIR/.claude/agents"
CLAUDE_SKILLS_DIR="$REPO_DIR/.claude/skills"
CURSOR_AGENTS_DIR="$REPO_DIR/.cursor/commands/agents"
CURSOR_SKILLS_DIR="$REPO_DIR/.cursor/commands/skills"

# Check if directories exist
if [[ ! -d "$CLAUDE_AGENTS_DIR" ]]; then
    echo "Error: $CLAUDE_AGENTS_DIR does not exist"
    exit 1
fi

if [[ ! -d "$CLAUDE_SKILLS_DIR" ]]; then
    echo "Error: $CLAUDE_SKILLS_DIR does not exist"
    exit 1
fi

# Create cursor directories if they don't exist
mkdir -p "$CURSOR_AGENTS_DIR"
mkdir -p "$CURSOR_SKILLS_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Cursor Commands Sync Analysis ===${NC}\n"

# Function to get relative path from base directory
get_relative_path() {
    local file_path="$1"
    local base_dir="$2"
    echo "${file_path#$base_dir/}"
}

# Function to convert .claude path to .cursor path
convert_agent_path() {
    local claude_path="$1"
    local relative_path=$(get_relative_path "$claude_path" "$CLAUDE_AGENTS_DIR")
    echo "$CURSOR_AGENTS_DIR/$relative_path"
}

convert_skill_path() {
    local claude_path="$1"
    # Get the parent directory of Skill.md
    local skill_parent_dir=$(dirname "$claude_path")
    # Get relative path from CLAUDE_SKILLS_DIR to the parent directory
    local relative_path=$(get_relative_path "$skill_parent_dir" "$CLAUDE_SKILLS_DIR")
    # Create the cursor file path
    echo "$CURSOR_SKILLS_DIR/${relative_path}.md"
}

# Find all agent files in .claude/agents
echo -e "${BLUE}Scanning .claude/agents...${NC}"
declare -a CLAUDE_AGENT_FILES
while IFS= read -r -d '' file; do
    CLAUDE_AGENT_FILES+=("$file")
done < <(find "$CLAUDE_AGENTS_DIR" -type f -name "*.md" ! -name "README.md" ! -name "CONTRIBUTING.md" ! -name "LICENSE" -print0 | sort -z)

# Find all skill files in .claude/skills (look for both Skill.md and SKILL.md)
echo -e "${BLUE}Scanning .claude/skills...${NC}"
declare -a CLAUDE_SKILL_FILES
while IFS= read -r -d '' file; do
    CLAUDE_SKILL_FILES+=("$file")
done < <(find "$CLAUDE_SKILLS_DIR" -type f \( -name "Skill.md" -o -name "SKILL.md" \) -print0 | sort -z)

# Find all existing cursor agent files
echo -e "${BLUE}Scanning .cursor/commands/agents...${NC}"
declare -a CURSOR_AGENT_FILES
while IFS= read -r -d '' file; do
    CURSOR_AGENT_FILES+=("$file")
done < <(find "$CURSOR_AGENTS_DIR" -type f -name "*.md" -print0 | sort -z)

# Find all existing cursor skill files
echo -e "${BLUE}Scanning .cursor/commands/skills...${NC}"
declare -a CURSOR_SKILL_FILES
while IFS= read -r -d '' file; do
    CURSOR_SKILL_FILES+=("$file")
done < <(find "$CURSOR_SKILLS_DIR" -type f -name "*.md" -print0 | sort -z)

# Compare agents
echo -e "\n${BLUE}=== AGENTS COMPARISON ===${NC}\n"

declare -a MISSING_AGENTS
declare -a EXTRA_AGENTS

for claude_file in "${CLAUDE_AGENT_FILES[@]}"; do
    relative_path=$(get_relative_path "$claude_file" "$CLAUDE_AGENTS_DIR")
    cursor_file="$CURSOR_AGENTS_DIR/$relative_path"
    
    if [[ ! -f "$cursor_file" ]]; then
        MISSING_AGENTS+=("$relative_path")
        echo -e "${RED}❌ MISSING:${NC} $relative_path"
    fi
done

# Check for extra cursor agent files (not in claude)
for cursor_file in "${CURSOR_AGENT_FILES[@]}"; do
    relative_path=$(get_relative_path "$cursor_file" "$CURSOR_AGENTS_DIR")
    claude_file="$CLAUDE_AGENTS_DIR/$relative_path"
    
    # Skip bernier directory (project-specific commands)
    if [[ "$relative_path" == bernier/* ]]; then
        continue
    fi
    
    if [[ ! -f "$claude_file" ]]; then
        EXTRA_AGENTS+=("$relative_path")
        echo -e "${YELLOW}⚠️  EXTRA:${NC} $relative_path (not in .claude/agents)"
    fi
done

# Compare skills
echo -e "\n${BLUE}=== SKILLS COMPARISON ===${NC}\n"

declare -a MISSING_SKILLS
declare -a MISSING_SKILL_PATHS
declare -a EXTRA_SKILLS

for claude_file in "${CLAUDE_SKILL_FILES[@]}"; do
    cursor_file=$(convert_skill_path "$claude_file")
    relative_path=$(get_relative_path "$cursor_file" "$CURSOR_SKILLS_DIR")
    
    if [[ ! -f "$cursor_file" ]]; then
        MISSING_SKILLS+=("$relative_path")
        MISSING_SKILL_PATHS+=("$claude_file")
        echo -e "${RED}❌ MISSING:${NC} $relative_path"
    fi
done

# Check for extra cursor skill files (not in claude)
for cursor_file in "${CURSOR_SKILL_FILES[@]}"; do
    relative_path=$(get_relative_path "$cursor_file" "$CURSOR_SKILLS_DIR")
    # Convert cursor path back to potential claude skill path
    # .cursor/commands/skills/algorithmic-art.md -> .claude/skills/algorithmic-art/Skill.md or SKILL.md
    # .cursor/commands/skills/document-skills/docx.md -> .claude/skills/document-skills/docx/Skill.md or SKILL.md
    
    # Try to find the corresponding Skill.md file
    potential_claude_dir="$CLAUDE_SKILLS_DIR/$relative_path"
    potential_claude_dir="${potential_claude_dir%.md}"  # Remove .md extension
    
    # Check if directory exists and contains Skill.md or SKILL.md
    if [[ ! -d "$potential_claude_dir" ]] || [[ ! -f "$potential_claude_dir/Skill.md" && ! -f "$potential_claude_dir/SKILL.md" ]]; then
        EXTRA_SKILLS+=("$relative_path")
        echo -e "${YELLOW}⚠️  EXTRA:${NC} $relative_path (not in .claude/skills)"
    fi
done

# Generate summary
echo -e "\n${BLUE}=== SUMMARY ===${NC}\n"
echo -e "Missing agents: ${#MISSING_AGENTS[@]}"
echo -e "Extra agents: ${#EXTRA_AGENTS[@]}"
echo -e "Missing skills: ${#MISSING_SKILLS[@]}"
echo -e "Extra skills: ${#EXTRA_SKILLS[@]}"

# Generate prompt content
PROMPT_CONTENT="Please sync the Cursor commands directory with the Claude agents and skills directories.

"

if [[ ${#MISSING_AGENTS[@]} -gt 0 ]]; then
    PROMPT_CONTENT+="
## CREATE MISSING AGENT COMMANDS

The following agent files exist in \`.claude/agents/\` but are missing from \`.cursor/commands/agents/\`:
"
    for agent in "${MISSING_AGENTS[@]}"; do
        PROMPT_CONTENT+="- \`$agent\`
"
    done
    PROMPT_CONTENT+="
For each missing agent file, create a corresponding command file in \`.cursor/commands/agents/\` following this pattern:

1. Use the same directory structure as in \`.claude/agents/\`
2. The command file should have frontmatter with:
   - \`name\`: A descriptive name for the command
   - \`description\`: Brief description
   - \`tags\`: Relevant tags
3. Include \`{{selection}}\` placeholder
4. Reference the source agent with: \`{{file:~/.claude/agents/PATH_TO_AGENT.md}}\`

Example structure:
\`\`\`
---
name: \"Agent Name\"
description: \"Agent description\"
tags: [\"tag1\", \"tag2\"]
---

You are a command inside Cursor. [Brief description]

{{selection}}

---

## Source Agent (converted)

{{file:~/.claude/agents/PATH_TO_AGENT.md}}
\`\`\`
"
fi

if [[ ${#MISSING_SKILLS[@]} -gt 0 ]]; then
    PROMPT_CONTENT+="
## CREATE MISSING SKILL COMMANDS

The following skill files exist in \`.claude/skills/\` but are missing from \`.cursor/commands/skills/\`:
"
    for i in "${!MISSING_SKILLS[@]}"; do
        skill_path="${MISSING_SKILLS[$i]}"
        claude_file="${MISSING_SKILL_PATHS[$i]}"
        claude_relative=$(get_relative_path "$claude_file" "$CLAUDE_SKILLS_DIR")
        PROMPT_CONTENT+="- \`$skill_path\` (from \`.claude/skills/$claude_relative\`)
"
    done
    PROMPT_CONTENT+="
For each missing skill, create a command file in \`.cursor/commands/skills/\` following this pattern:

1. The file path should mirror the directory structure up to the parent of \`Skill.md\`
   - Example: \`.claude/skills/algorithmic-art/Skill.md\` -> \`.cursor/commands/skills/algorithmic-art.md\`
   - Example: \`.claude/skills/document-skills/docx/Skill.md\` -> \`.cursor/commands/skills/document-skills/docx.md\`
2. Read the \`Skill.md\` or \`SKILL.md\` file from the skill directory
3. The command file should have frontmatter with:
   - \`name\`: Skill name
   - \`description\`: Brief description from the skill
   - \`tags\`: Relevant tags (include \"skill\")
4. Include \`{{selection}}\` placeholder
5. Reference the source skill with: \`{{file:~/.claude/skills/PATH_TO_SKILL.md}}\`

Example structure:
\`\`\`
---
name: \"Skill Name\"
description: \"Skill description\"
tags: [\"skill\", \"tag1\", \"tag2\"]
---

You are a skill command inside Cursor. [Brief description]

{{selection}}

---

## Source Skill (converted)

{{file:~/.claude/skills/PATH_TO_SKILL.md}}
\`\`\`
"
fi

if [[ ${#EXTRA_AGENTS[@]} -gt 0 ]]; then
    PROMPT_CONTENT+="
## REMOVE EXTRA AGENT COMMANDS

The following command files exist in \`.cursor/commands/agents/\` but the corresponding agent files are missing from \`.claude/agents/\`:
"
    for agent in "${EXTRA_AGENTS[@]}"; do
        PROMPT_CONTENT+="- \`$agent\`
"
    done
    PROMPT_CONTENT+="
Please remove these files as they reference agents that no longer exist.
"
fi

if [[ ${#EXTRA_SKILLS[@]} -gt 0 ]]; then
    PROMPT_CONTENT+="
## REMOVE EXTRA SKILL COMMANDS

The following command files exist in \`.cursor/commands/skills/\` but the corresponding skill files are missing from \`.claude/skills/\`:
"
    for skill_path in "${EXTRA_SKILLS[@]}"; do
        PROMPT_CONTENT+="- \`$skill_path\`
"
    done
    PROMPT_CONTENT+="
Please remove these files as they reference skills that no longer exist.
"
fi

# Display prompt
echo -e "\n${GREEN}=== CURSOR SYNC PROMPT ===${NC}\n"
echo "Copy the following prompt and paste it into Cursor:"
echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}\n"
echo "$PROMPT_CONTENT"
echo -e "${YELLOW}─────────────────────────────────────────────────────────────${NC}\n"

# Save prompt to file
PROMPT_FILE="$REPO_DIR/plans/cursor/sync-commands-prompt.md"
mkdir -p "$(dirname "$PROMPT_FILE")"

{
    echo "# Cursor Commands Sync Prompt"
    echo ""
    echo "Generated: $(date)"
    echo ""
    echo "## Summary"
    echo ""
    echo "- Missing agents: ${#MISSING_AGENTS[@]}"
    echo "- Extra agents: ${#EXTRA_AGENTS[@]}"
    echo "- Missing skills: ${#MISSING_SKILLS[@]}"
    echo "- Extra skills: ${#EXTRA_SKILLS[@]}"
    echo ""
    echo "---"
    echo ""
    echo "$PROMPT_CONTENT"
} > "$PROMPT_FILE"

echo -e "${GREEN}✓ Prompt saved to: $PROMPT_FILE${NC}\n"

# Automatically send to Claude CLI if available
if command -v claude &> /dev/null; then
    echo -e "${BLUE}Sending prompt to Claude CLI...${NC}\n"
    # Open a new Terminal window and run the claude command using the saved prompt file
    # First send the prompt with --print, then continue interactively
    osascript -e "tell application \"Terminal\" to do script \"cd $REPO_DIR/; claude --dangerously-skip-permissions --print \\\"\$(cat plans/cursor/sync-commands-prompt.md | sed '1,/^---$/d')\\\"; claude --dangerously-skip-permissions --continue\""
    echo -e "${GREEN}✓ Claude CLI command sent to Terminal (will continue interactively)${NC}\n"
else
    echo -e "${YELLOW}Note: Claude CLI not found.${NC}"
    echo -e "${YELLOW}To send manually, run:${NC}"
    echo -e "${YELLOW}cd $REPO_DIR && claude --dangerously-skip-permissions --print \"\$(cat plans/cursor/sync-commands-prompt.md | sed '1,/^---$/d')\" && claude --dangerously-skip-permissions --continue${NC}\n"
fi

