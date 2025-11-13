# Agents Environment Configuration

Unified configuration repository for managing AI agent definitions and MCP (Model Context Protocol) settings across multiple AI tools: Claude, Cursor, Gemini, Qwen, Codex, and Claude Code Router.

## Repository Structure

```
agents-environment-config/
├── .claude/
│   ├── agents/          # Git submodule → bernierllc/agency-agents
│   └── skills/          # Git submodule → bernierllc/skills
├── .cursor/
│   ├── commands/        # Cursor command wrappers for agents
│   └── mcp.json         # Cursor MCP server configuration
├── .gemini/
│   └── settings.json    # Gemini MCP configuration
├── .qwen/
│   └── settings.json    # Qwen MCP configuration (same as Gemini)
├── .codex/
│   └── config.toml      # Codex MCP configuration (TOML format)
├── .claude-code-router/
│   └── config.json      # Claude Code Router configuration
├── .env.template        # Environment variable template
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

# Claude agents and skills
mkdir -p ~/.claude
ln -s "$REPO_PATH/.claude/agents" ~/.claude/agents
ln -s "$REPO_PATH/.claude/skills" ~/.claude/skills

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

## Git Submodule Workflow

### Understanding Git Submodules

A git submodule is a pointer to a specific commit in another repository. The parent repository (`agents-environment-config`) tracks which version of each submodule you're using.

**Important:** Changes made in submodule directories are tracked by the submodule's own git repository, not the parent repo.

This repository uses two submodules:
- `.claude/agents` → `bernierllc/agency-agents`
- `.claude/skills` → `bernierllc/skills`

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

1. Make changes in `.claude/agents/` (the submodule)
2. Commit and push to `bernierllc/agency-agents`
3. Update submodule reference in parent repo

### Adding New Skills

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
