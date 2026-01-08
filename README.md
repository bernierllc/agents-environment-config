# Agents Environment Configuration

Unified configuration repository for managing AI agent definitions and MCP (Model Context Protocol) settings across multiple AI tools: Claude, Cursor, Gemini, Qwen, Codex, and Claude Code Router.

**Note:** This repo is MacOSX specific, but nearly all of this translates to PC/Linux if you account for the nuances of your preferred Operating system.

## Repository Structure

```
agents-environment-config/
├── .claude/
│   ├── agents/          # Git submodule → bernierllc/agency-agents
│   ├── skills/          # Git submodule → bernierllc/skills
│   ├── statusline.sh    # Claude Code statusline script
│   └── statusline-command.sh  # Extended statusline with Claude-Flow integration
├── .claude-plugin/
│   └── marketplace.json # Claude Code plugin marketplace configuration
├── .cursor/
│   ├── commands/        # Cursor command wrappers for agents
│   ├── mcp.json         # Cursor MCP server configuration
│   └── rules/           # Cursor rules (global development standards)
├── .gemini/
│   └── settings.json    # Gemini MCP configuration
├── .qwen/
│   └── settings.json    # Qwen MCP configuration (same as Gemini)
├── .codex/
│   └── config.toml      # Codex MCP configuration (TOML format)
├── .claude-code-router/
│   └── config.json      # Claude Code Router configuration
├── docs/                # Documentation
│   └── ui-audit/        # UI audit documentation
├── plans/               # Planning documents
│   ├── cursor/          # Cursor-related planning docs
│   ├── gdocs-table-manipulation.plan.md
│   └── ui-audit-skill-command.plan.md
├── scripts/             # Utility scripts
│   ├── audit-project-rules.py
│   ├── generate-agent-files.py
│   ├── generate-removal-script-safe.py
│   ├── generate-removal-script.py
│   ├── remove-duplicate-rules.sh
│   └── verify-dry-run.py
├── .env.template        # Environment variable template
├── AGENTINFO.md         # Project-specific agent information template
├── AGENTS.md            # Generated agent instructions for Codex
├── GEMINI.md            # Generated agent instructions for Gemini CLI
├── QWEN.md              # Generated agent instructions for Qwen Code
├── CLAUDE.md            # Generated agent instructions for Claude Code
└── README.md            # This file
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config
```

### 2. Initialize Git Submodules

Both agents and skills are managed as git submodules:

```bash
git submodule update --init --recursive
```

This will clone:
- The `agency-agents` repository into `.claude/agents/`
- The `skills` repository into `.claude/skills/`

### 3. Configure Environment Variables

Copy the template and fill in your API keys:

```bash
cp .env.template .env
# Edit .env with your actual API keys
```

### 4. Create Symlinks

Create symlinks from your home directory configuration locations to this repository:

```bash
# Set the repository path (adjust as needed)
REPO_PATH="$HOME/path/to/agents-environment-config"

# Claude agents, skills, and statusline
mkdir -p ~/.claude
ln -s "$REPO_PATH/.claude/agents" ~/.claude/agents
ln -s "$REPO_PATH/.claude/skills" ~/.claude/skills
ln -s "$REPO_PATH/.claude/statusline.sh" ~/.claude/statusline.sh

# Cursor configuration
mkdir -p ~/.cursor
ln -s "$REPO_PATH/.cursor/commands" ~/.cursor/commands
ln -s "$REPO_PATH/.cursor/mcp.json" ~/.cursor/mcp.json

# Gemini configuration
mkdir -p ~/.gemini
ln -s "$REPO_PATH/.gemini/settings.json" ~/.gemini/settings.json

# Qwen configuration
mkdir -p ~/.qwen
ln -s "$REPO_PATH/.qwen/settings.json" ~/.qwen/settings.json

# Codex configuration
mkdir -p ~/.codex
ln -s "$REPO_PATH/.codex/config.toml" ~/.codex/config.toml

# Claude Code Router configuration
mkdir -p ~/.claude-code-router
ln -s "$REPO_PATH/.claude-code-router/config.json" ~/.claude-code-router/config.json
```

**Note:** Replace `$HOME/path/to/agents-environment-config` with the actual path to your cloned repository.

## Automated Agent and Skill Sync System

This repository includes an **automated sync system** that handles bidirectional synchronization between:
- `.claude/agents/` ↔ `bernierllc/agency-agents` (git submodule)
- `.claude/skills/` ↔ `bernierllc/skills` (git submodule)
- `.claude/` → `.cursor/commands/` (local sync with content replacement)

### Key Features

- **Automatic Syncing**: Runs on `git push` and `git pull/merge`
- **Content Replacement**: Replaces `{{file:...}}` references with actual file content in Cursor commands
- **PR Creation**: Automatically creates pull requests for submodule changes
- **Bidirectional**: Pushes local changes and pulls remote changes
- **Deletion Handling**: Removes Cursor command files when source files are deleted
- **Skip Mechanism**: `SKIP_SYNC=1 git push` to bypass sync when needed

### Installation

1. **Install the git hooks:**
   ```bash
   bash scripts/install-git-hooks.sh
   ```

2. **The installer will validate:**
   - Python 3 is installed
   - GitHub CLI (`gh`) is installed
   - GitHub CLI is authenticated
   - Git submodules are initialized

### Usage

The sync system works automatically:

```bash
# Normal git operations trigger sync
git push        # Syncs to cursor, creates PRs for submodule changes
git pull        # Pulls submodule updates, syncs to cursor

# Skip sync if needed
SKIP_SYNC=1 git push

# Skip all hooks (not recommended)
git push --no-verify
```

For detailed documentation, see [`docs/agent-skill-sync-system.md`](./docs/agent-skill-sync-system.md).

## Git Submodule Workflow

### Understanding Git Submodules

A git submodule is a pointer to a specific commit in another repository. The parent repository (`agents-environment-config`) tracks which version of each submodule you're using.

**Important:** Changes made in submodule directories are tracked by the submodule's own git repository, not the parent repo.

This repository uses two submodules:
- `.claude/agents` → `bernierllc/agency-agents`
- `.claude/skills` → `bernierllc/skills`

**Note:** With the automated sync system installed, many of these manual steps are handled automatically!

### Making Changes to Skills

When you want to update skills:

1. **Navigate to the submodule directory:**
   ```bash
   cd .claude/skills
   ```

2. **Make your changes and commit:**
   ```bash
   # Edit skill files
   git add .
   git commit -m "Update skill definitions"
   ```

3. **Push changes to the submodule's remote:**
   ```bash
   git push origin <branch-name>
   ```
   This pushes to `bernierllc/skills`.

4. **Return to parent repo and update the submodule reference:**
   ```bash
   cd ../..
   git add .claude/skills
   git commit -m "Update skills submodule to latest version"
   git push
   ```

### Making Changes to Agents

When you want to update agent definitions:

1. **Navigate to the submodule directory:**
   ```bash
   cd .claude/agents
   ```

2. **Make your changes and commit:**
   ```bash
   # Edit agent files
   git add .
   git commit -m "Update agent definitions"
   ```

3. **Push changes to the submodule's remote:**
   ```bash
   git push origin <branch-name>
   ```
   This pushes to `bernierllc/agency-agents`, **NOT** to the original fork (`msitarzewski/agency-agents`).

4. **Return to parent repo and update the submodule reference:**
   ```bash
   cd ../..
   git add .claude/agents
   git commit -m "Update agents submodule to latest version"
   git push
   ```

### Updating Submodules from Remote

To pull the latest changes for a specific submodule:

```bash
# Update agents
git submodule update --remote .claude/agents

# Update skills
git submodule update --remote .claude/skills
```

Or to update all submodules:

```bash
git submodule update --init --recursive
```

### Cloning with Submodules

When cloning this repository for the first time:

```bash
git clone --recursive https://github.com/bernierllc/agents-environment-config.git
```

Or if already cloned:

```bash
git submodule update --init --recursive
```

## Tool-Specific Setup

### Claude Desktop

**Locations:**
- Agents: `~/.claude/agents/`
- Skills: `~/.claude/skills/`

Both are available via symlinks. If you prefer not to use symlinks:

```bash
cp -r .claude/agents/* ~/.claude/agents/
cp -r .claude/skills/* ~/.claude/skills/
```

**Note:** Using symlinks keeps agents and skills in sync automatically. Manual copying requires updates when content changes.

### Claude Code

#### Custom Statusline

This repository includes custom statusline scripts that provide a rich, color-coded status bar for Claude Code displaying model name, token usage, git branch, and project name. Thank you to (@leovanzyl on Youtube)[https://youtu.be/fiZfVTsPy-w?si=uPhizLFOiWOiC2km] for this tip!

**Example output:**

```
Opus 4.5 │ [█████████████░░░░░░░] │ 68% │ main │ my-project
```

The statusline shows:
- **Model Name** (blue) - Current Claude model
- **Progress Bar** (color-coded) - Visual token usage indicator
- **Token %** (cyan/yellow/red) - Percentage of context used (turns red at 90%+)
- **Git Branch** (green) - Current branch name
- **Project Name** (magenta) - From BrainGrid or directory name

**Setup Instructions:**

1. **Copy the statusline script to your Claude config directory:**

   ```bash
   cp .claude/statusline.sh ~/.claude/statusline.sh
   chmod +x ~/.claude/statusline.sh
   ```

2. **Update your `~/.claude/settings.json` to enable the statusline:**

   Add the following to your `settings.json` file (create it if it doesn't exist):

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "~/.claude/statusline.sh",
       "padding": 0
     }
   }
   ```

   **Note:** The `~` expands to your home directory (e.g., `/Users/yourname/.claude/statusline.sh`).

3. **Restart Claude Code** to see the new statusline.

**Alternative: Claude-Flow Statusline**

If you're using Claude-Flow for swarm orchestration, there's also `statusline-command.sh` which includes additional metrics:
- Swarm topology and agent count
- Memory and CPU usage
- Session state and task metrics
- Active task count and hooks status

To use it instead, copy `statusline-command.sh` and update the path in `settings.json`.

### Cursor

**Locations:**
- Commands: `~/.cursor/commands/`
- MCP Config: `~/.cursor/mcp.json`

Both are symlinked from this repository. After creating symlinks:

1. Update API keys in `.cursor/mcp.json` (or use environment variables)
2. Restart Cursor to load new configuration

### Gemini

**Location:** `~/.gemini/settings.json`

See [GEMINI.md](./GEMINI.md) for detailed setup instructions.

1. Create symlink: `ln -s <repo-path>/.gemini/settings.json ~/.gemini/settings.json`
2. Update API keys in the settings file
3. Restart Gemini

### Qwen

**Location:** `~/.qwen/settings.json`

See [QWEN.md](./QWEN.md) for detailed setup instructions.

1. Create symlink: `ln -s <repo-path>/.qwen/settings.json ~/.qwen/settings.json`
2. Update API keys in the settings file
3. Restart Qwen

### Codex

**Location:** `~/.codex/config.toml`

1. Create symlink: `ln -s <repo-path>/.codex/config.toml ~/.codex/config.toml`
2. Update API keys in the TOML configuration file
3. Restart Codex

### Claude Code Router

**Location:** `~/.claude-code-router/config.json`

1. Create symlink: `ln -s <repo-path>/.claude-code-router/config.json ~/.claude-code-router/config.json`
2. Update the `PORT` value in the configuration
3. Restart Claude Code Router

## Claude Code Plugin Marketplace

This repository includes a Claude Code plugin marketplace configuration at `.claude-plugin/marketplace.json` that enables Claude Code to discover and use agents and skills from multiple sources.

### Marketplace Structure

The marketplace configuration provides access to three plugin collections:

1. **bernier-agents** - Complete agency agent collection from `bernierllc/agency-agents`
   - All upstream agents from the original `msitarzewski/agency-agents` fork
   - Bernier-specific agents for development workflows, deployment, testing, and specialized tasks
   - Located in GitHub: `bernierllc/agency-agents`

2. **bernier-gdocs-skill** - Custom Google Docs skill from `bernierllc/skills`
   - Intelligent document synthesis and meeting notes merging
   - Professional content integration for Google Docs
   - Located in GitHub: `bernierllc/skills` at `document-skills/gdocs`

3. **anthropic-skills** - Official Anthropic skills from `anthropics/skills`
   - Document processing suite (Excel, Word, PowerPoint, PDF)
   - Design and development tools (canvas-design, algorithmic-art, etc.)
   - Testing utilities, MCP builders, and more
   - Located in GitHub: `anthropics/skills`

### Using the Marketplace

Claude Code automatically discovers marketplace configurations in the `.claude-plugin/` directory. The marketplace points to:

- **Git submodules**: Agents and skills are managed as git submodules at `.claude/agents/` and `.claude/skills/`
- **GitHub repositories**: Each plugin source is referenced by its GitHub repository URL
- **Mixed sources**: Combines bernierllc custom agents/skills with official Anthropic skills

### Installing Plugins from the Marketplace

To install plugins from this marketplace in Claude Code:

```bash
# Install all bernier agents
/plugin install bernier-agents@bernier-environment-config

# Install the gdocs skill
/plugin install bernier-gdocs-skill@bernier-environment-config

# Install official Anthropic skills
/plugin install anthropic-skills@bernier-environment-config
```

### Marketplace Updates

When agents or skills are updated in their respective repositories:

1. **Update the submodule:**
   ```bash
   # For agents
   git submodule update --remote .claude/agents

   # For skills
   git submodule update --remote .claude/skills
   ```

2. **Commit the submodule update:**
   ```bash
   git add .claude/agents .claude/skills
   git commit -m "Update agents and skills submodules"
   git push
   ```

3. **Claude Code will automatically detect the updates** when you pull the latest changes

### Marketplace File Location

The marketplace configuration is stored at:
```
.claude-plugin/marketplace.json
```

This file defines:
- Plugin names and descriptions
- Source repositories (GitHub URLs)
- Specific agents and skills included in each plugin
- Plugin categories and keywords

### Customizing the Marketplace

To add new plugins or modify existing ones:

1. Edit `.claude-plugin/marketplace.json`
2. Add or update plugin entries following the existing structure
3. Commit changes to this repository
4. Claude Code will discover the updated marketplace on next load

For more information about plugin marketplaces, see the [Claude Code Plugin Marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces).

## Environment Variables

All API keys and sensitive configuration should be stored in `.env` (not committed to git). The `.env.template` file lists all required variables:

- `CONTEXT7_API_KEY`
- `STRIPE_SECRET_KEY`
- `BROWSERBASE_API_KEY`
- `BROWSERBASE_PROJECT_ID`
- `POSTHOG_AUTH_HEADER`
- `OPENAI_API_KEY`
- `PACKAGES_API_AUTH_TOKEN`
- `CLAUDE_CODE_ROUTER_PORT`

## Troubleshooting

### Symlinks Not Working

Verify symlinks are correctly created:

```bash
ls -la ~/.claude/agents
ls -la ~/.cursor/commands
ls -la ~/.cursor/mcp.json
```

If you see broken symlinks, recreate them using the commands in the Quick Start section.

### Submodule Not Initialized

If `.claude/agents` or `.claude/skills` is empty:

```bash
git submodule update --init --recursive
```

### Configuration Not Loading

1. **Verify file paths:** Ensure symlinks point to correct locations
2. **Check permissions:** Configuration files should be readable
3. **Restart application:** Most tools require restart to load new config
4. **Check logs:** Look for MCP connection errors in application logs

### API Keys Not Working

1. Verify API keys are correctly entered (no extra spaces)
2. Check that environment variables are exported if using them
3. Ensure API keys haven't expired or been revoked
4. Verify the correct format for each service (some require "Bearer " prefix)

## Generated Agent Instruction Files

This repository includes automatically generated agent instruction files (`AGENTS.md`, `GEMINI.md`, `QWEN.md`, `CLAUDE.md`) that incorporate rules from `.cursor/rules/`. These files can be committed to git repositories so that anyone cloning a project will have consistent coding standards even without access to the global agents-environment-config setup.

### Using Agent Files in Projects

To use these agent files in your projects:

1. **Copy the relevant file(s) to your project root:**
   ```bash
   cp AGENTS.md /path/to/your-project/
   cp CLAUDE.md /path/to/your-project/
   ```

2. **Replace the content in `AGENTINFO.md`** with your project-specific information:
   - This file is a template - replace all content with your project-specific standards
   - Include project structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, documentation
   - The agent files contain instructions for maintaining `AGENTINFO.md` - follow those guidelines

3. **The agent files automatically reference `AGENTINFO.md`:**
   - Each agent file points to `AGENTINFO.md` as the canonical source for project-specific info
   - Global rules remain in the agent files (from `.cursor/rules/`)
   - Project-specific info goes ONLY in `AGENTINFO.md` - do NOT duplicate it in agent files or `.cursor/rules/`
   - Each agent will automatically discover and use the appropriate file:
     - Codex looks for `AGENTS.md`
     - Gemini CLI looks for `GEMINI.md`
     - Qwen Code looks for `QWEN.md`
     - Claude Code looks for `CLAUDE.md`

4. **Maintain the pattern:**
   - When project-specific processes change, update `AGENTINFO.md` immediately
   - Do NOT edit agent files or `.cursor/rules/` for project-specific info - keep it in `AGENTINFO.md`
   - The agent files contain global rules and maintenance instructions - they will guide you to update `AGENTINFO.md`

### Regenerating Agent Files

When rules in `.cursor/rules/` are updated, regenerate the agent files:

```bash
python3 scripts/generate-agent-files.py
```

This will update all four agent instruction files with the latest rules.

## Maintaining This Repository

### Adding New Agents

With the automated sync system:

1. **Edit files** in `.claude/agents/`
2. **Commit locally** (don't push to submodule manually)
3. **Push to main repo**: The sync system will:
   - Create a PR to `bernierllc/agency-agents`
   - Sync to `.cursor/commands/agents/` with content replacement
   - Update submodule reference

**Manual method** (if sync is disabled):
1. Make changes in `.claude/agents/` (the submodule)
2. Commit and push to `bernierllc/agency-agents`
3. Update submodule reference in parent repo

### Adding New Skills

With the automated sync system:

1. **Edit files** in `.claude/skills/`
2. **Commit locally** (don't push to submodule manually)
3. **Push to main repo**: The sync system will:
   - Create a PR to `bernierllc/skills`
   - Sync to `.cursor/commands/skills/` with content replacement
   - Update submodule reference

**Manual method** (if sync is disabled):
1. Make changes in `.claude/skills/` (the submodule)
2. Commit and push to `bernierllc/skills`
3. Update submodule reference in parent repo

### Adding New MCP Servers

1. Add server configuration to all relevant config files:
   - `.cursor/mcp.json`
   - `.gemini/settings.json`
   - `.qwen/settings.json`
   - `.codex/config.toml`

2. Add corresponding environment variable to `.env.template`

3. Update documentation

### Updating Cursor Commands

Cursor commands are in `.cursor/commands/`. These wrap the agent definitions for use in Cursor. To add a new command:

1. Create new `.md` file in `.cursor/commands/`
2. Follow the existing pattern with frontmatter and agent reference
3. Commit to this repository

### Documentation Directory (`docs/`)

The `docs/` directory contains project documentation:

- `docs/agent-skill-sync-system.md` - **Automated sync system documentation**
  - Installation and setup guide
  - Usage instructions and examples
  - Configuration reference
  - Troubleshooting guide
  
- `docs/ui-audit/` - Documentation for UI audit workflows and processes
  - `README.md` - Overview of UI audit functionality
  - `workflow.md` - UI audit workflow documentation

### Planning Directory (`plans/`)

The `plans/` directory contains planning documents and task tracking:

- `plans/cursor/` - Cursor-related planning documents
  - Architecture and consolidation planning
  - Project rules audit documentation
- `plans/*.plan.md` - Feature and improvement planning documents

### Scripts Directory (`scripts/`)

The `scripts/` directory contains utility scripts for repository maintenance:

- **Agent and Skill Sync:**
  - `sync-agents-skills.py` - Core sync script for bidirectional agent/skill synchronization
  - `sync-config.json` - Configuration for sync system (submodules, paths, PR settings)
  - `install-git-hooks.sh` - Installs git hooks and validates environment
  - `git-hooks/pre-push` - Pre-push hook for syncing and creating PRs
  - `git-hooks/post-merge` - Post-merge hook for pulling submodule changes
  
- **Agent File Generation:**
  - `generate-agent-files.py` - Generates agent instruction files from `.cursor/rules/`
  
- **Rule Management:**
  - `audit-project-rules.py` - Audits project-specific rules
  - `generate-removal-script*.py` - Scripts for removing duplicate rules
  - `remove-duplicate-rules.sh` - Shell script for rule cleanup
  - `verify-dry-run.py` - Verification utilities

## Security Notes

- **Never commit `.env` file** - It contains sensitive API keys
- **Use placeholders in config files** - Replace with actual keys during setup
- **Review API key permissions** - Use least-privilege access
- **Rotate keys regularly** - Update keys periodically for security

## Contributing

When making changes:

1. Update agent definitions in the submodule (`agency-agents`)
2. Test changes across all tools
3. Update documentation if needed
4. Commit with clear messages
5. Push to `bernierllc/agents-environment-config`

## License

This repository maintains the same license as the `agency-agents` submodule (MIT License).

## Related Repositories

- [agency-agents](https://github.com/bernierllc/agency-agents) - The agent definitions repository (submodule)
- [skills](https://github.com/bernierllc/skills) - The skills repository (submodule)
- [Original agency-agents fork](https://github.com/msitarzewski/agency-agents) - The original repository this was forked from
- [Anthropic skills](https://github.com/anthropics/skills) - Official Anthropic skills repository (referenced in marketplace)
