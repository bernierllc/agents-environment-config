# Lint Hooks

AEC can automatically install lint/type-check hooks for your AI coding agents. These hooks run after every file edit, catching type errors and lint issues in real-time.

## Supported Agents

| Agent | Config File | Hook Trigger |
|-------|------------|-------------|
| Claude Code | `.claude/settings.json` | After Edit/Write |
| Gemini CLI | `.gemini/settings.json` | After write_file/replace |
| Cursor | `.cursor/hooks.json` | After file edit |

Codex and Qwen do not currently support hooks.

## Supported Languages

| Language | Detection | Command |
|----------|-----------|---------|
| TypeScript | `tsconfig.json` | `npx tsc --noEmit --pretty` |
| Rust | `Cargo.toml` | `cargo check` |
| Python | `pyproject.toml`, `setup.py`, `mypy.ini` | `mypy .` |
| Go | `go.mod` | `go vet ./...` |
| Ruby | `Gemfile` | `bundle exec rubocop` |

Multi-language projects are supported — all detected languages can be hooked simultaneously.

## How It Works

During `aec repo setup`, the CLI:

1. Detects which languages your project uses
2. Identifies which installed agents support hooks
3. Generates the correct hook config for each agent

## Hook Mode Preference

The first time you set up hooks, AEC asks how you want them handled:

- **Per-repo** (default): Prompts you each time during `aec repo setup`
- **Auto**: Always installs hooks for detected languages without asking
- **Never**: Skips hook setup entirely

Change your preference:

```bash
aec preferences reset hook_mode
```

This will re-prompt you on next `aec repo setup`.

## Existing Config Files

If an agent's config file already exists, you have three options:

1. **Skip**: Don't modify the existing file
2. **Merge**: Add hooks while keeping your existing settings
3. **Show**: Display the config snippet to add manually

## Manual Setup

If you prefer to configure hooks manually or need to customize them, here are the configs for each agent:

### Claude Code (`.claude/settings.json`)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "npx tsc --noEmit --pretty 2>&1 | head -20"
          }
        ]
      }
    ]
  }
}
```

### Gemini CLI (`.gemini/settings.json`)

```json
{
  "tools": { "enableHooks": true },
  "hooks": {
    "enabled": true,
    "AfterTool": [
      {
        "matcher": "write_file|replace",
        "hooks": [
          {
            "type": "command",
            "command": "npx tsc --noEmit --pretty 2>&1 | head -20",
            "name": "lint-0"
          }
        ]
      }
    ]
  }
}
```

### Cursor (`.cursor/hooks.json`)

```json
{
  "version": 1,
  "hooks": {
    "afterFileEdit": [
      {
        "command": "npx tsc --noEmit --pretty 2>&1 | head -20"
      }
    ]
  }
}
```
