# Agents Environment Configuration

Unified configuration repository for managing AI agent definitions across multiple AI tools: Claude, Cursor, Gemini, Qwen, and Codex.

## Quick Setup (2 Steps)

### 1. Clone the Repository

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config
```

### 2. Run the Setup Script

```bash
./scripts/setup.sh
```

That's it! The setup script will:
- Automatically detect where you cloned the repo
- Initialize and update git submodules to the latest version
- Create all necessary symlinks to your home directory
- Handle existing files gracefully (asks before overwriting)

## Updating

To get the latest changes:

```bash
cd agents-environment-config
git pull
git submodule update --remote --recursive
```

Your symlinks will automatically point to the updated files. The submodule update pulls the latest agents and skills from their respective repositories.

### About Submodules

This repository uses git submodules for agents and skills:
- **Agents**: `bernierllc/agency-agents` repository
- **Skills**: `bernierllc/skills` repository

The setup script automatically initializes and updates these submodules to the latest version. When you run `./scripts/setup.sh`, it will:
1. Initialize the submodules if they haven't been cloned yet
2. Fetch the latest changes from the remote repositories
3. Update each submodule to the latest commit on their `main` branch

This ensures you always have the most up-to-date agents and skills available.

## Configuration

You can create a `.env` file from the template:

```bash
cp .env.template .env
# Edit .env with your API keys
```

## What Gets Symlinked

The setup script creates symlinks from the repository to your home directory:

- `~/.claude/agents/agents-environment-config` → repository `.claude/agents`
- `~/.claude/skills/agents-environment-config` → repository `.claude/skills`
- `~/.claude/statusline.sh` → repository `.claude/statusline.sh`
- `~/.cursor/commands/agents-environment-config` → repository `.cursor/commands`
- `~/.cursor/rules/agents-environment-config` → repository `.cursor/rules`

**Note:** 
- Agents, skills, Cursor commands, and Cursor rules are **symlinked** into subdirectories (`agents-environment-config`) so you can add your own custom content in the parent directories without conflicts.
- Statusline files are optional and you'll be prompted during setup if you want to install them.

## Repository Structure

```
agents-environment-config/
├── .claude/
│   ├── agents/          # Agent definitions (git submodule)
│   ├── skills/          # Skill definitions (git submodule)
│   └── statusline.sh    # Claude Code statusline script
├── .cursor/
│   ├── commands/        # Cursor command wrappers
│   └── rules/           # Cursor rules (global development standards)
├── scripts/
│   └── setup.sh         # Setup script (run this!)
└── README.md            # This file
```

## Tool-Specific Setup

### Claude Desktop / Claude Code

**Locations:**
- Agents from this repo: `~/.claude/agents/agents-environment-config/` (symlinked)
- Your custom agents: `~/.claude/agents/` (add your own `.md` files here)
- Skills from this repo: `~/.claude/skills/agents-environment-config/` (symlinked)
- Your custom skills: `~/.claude/skills/` (add your own skill folders here)

Claude will discover agents and skills from both locations automatically.

#### Custom Statusline

This repository includes custom statusline scripts for Claude Code. During setup, you'll be prompted if you want to install them.

If you choose to install:

1. The setup script will symlink the statusline files to `~/.claude/`
2. Update your `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
  }
}
```

3. Restart Claude Code

**Note:** If you already have statusline files, the setup script will skip installing them to preserve your existing configuration.

### Cursor

**Locations:**
- Commands from this repo: `~/.cursor/commands/agents-environment-config/` (symlinked)
- Your custom commands: `~/.cursor/commands/` (add your own `.md` files here)
- Rules from this repo: `~/.cursor/rules/agents-environment-config/` (symlinked)
- Your custom rules: `~/.cursor/rules/` (add your own `.mdc` files here)

Cursor will discover commands and rules from both locations automatically.

After setup:
1. Restart Cursor to load the new configuration


## Troubleshooting

### Symlinks Not Working

Verify symlinks are correctly created:

```bash
ls -la ~/.claude/agents/agents-environment-config
ls -la ~/.claude/skills/agents-environment-config
ls -la ~/.cursor/commands/agents-environment-config
ls -la ~/.cursor/rules/agents-environment-config
```

If you see broken symlinks, re-run the setup script:

```bash
cd agents-environment-config
./scripts/setup.sh
```

### Configuration Not Loading

1. **Verify file paths:** Check symlinks point to correct locations
2. **Check permissions:** Configuration files should be readable
3. **Restart application:** Most tools require restart to load new config
4. **Check logs:** Look for errors in application logs

### API Keys Not Working

1. Verify API keys are correctly entered (no extra spaces)
2. Check that environment variables are exported if using them
3. Ensure API keys haven't expired or been revoked
4. Verify the correct format for each service (some require "Bearer " prefix)

## Generated Agent Instruction Files

This repository includes automatically generated agent instruction files (`AGENTS.md`, `GEMINI.md`, `QWEN.md`, `CLAUDE.md`) that incorporate rules from `.cursor/rules/`. These files can be copied to your projects for consistent coding standards.

### Using Agent Files in Projects

1. **Copy the relevant file(s) to your project root:**
   ```bash
   cp AGENTS.md /path/to/your-project/
   cp CLAUDE.md /path/to/your-project/
   ```

2. **Create or update `AGENTINFO.md`** with your project-specific information

3. **Each agent will automatically discover and use the appropriate file:**
   - Codex looks for `AGENTS.md`
   - Gemini CLI looks for `GEMINI.md`
   - Qwen Code looks for `QWEN.md`
   - Claude Code looks for `CLAUDE.md`

### Regenerating Agent Files

When rules in `.cursor/rules/` are updated, regenerate the agent files:

```bash
python3 scripts/generate-agent-files.py
```

## Security Notes

- **Never commit `.env` file** - It contains sensitive API keys
- **Use placeholders in config files** - Replace with actual keys during setup
- **Review API key permissions** - Use least-privilege access
- **Rotate keys regularly** - Update keys periodically for security

## Contributing

When making changes:

1. Edit files directly in the repository
2. Test changes across all tools
3. Update documentation if needed
4. Commit with clear messages
5. Push to `bernierllc/agents-environment-config`

## License

MIT License

## Related Repositories

- [agency-agents](https://github.com/bernierllc/agency-agents) - The agent definitions repository
- [skills](https://github.com/bernierllc/skills) - The skills repository
