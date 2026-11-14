# Rules architecture

The core problem: Cursor needs YAML frontmatter in its rule files, but every other agent treats that frontmatter as noise. AEC maintains both formats from a single source.

## Two rule formats

| Directory | Format | Used by |
|-----------|--------|---------|
| `.cursor/rules/*.mdc` | Cursor format (WITH YAML frontmatter) | Cursor IDE |
| `.agent-rules/*.md` | Standard markdown (NO frontmatter) | Claude, Codex, Gemini, Qwen |

## Why two formats?

- **Cursor** requires YAML frontmatter (`description`, `globs`, `alwaysApply`, `tags`) for rule discovery
- **Other agents** don't understand Cursor frontmatter and waste tokens parsing it
- `.agent-rules/` saves ~5% tokens per rule and avoids polluting non-Cursor agents

## Keeping rules in sync

A pre-commit hook validates parity between `.cursor/rules/` and `.agent-rules/`:

```bash
# Generate .agent-rules/ from .cursor/rules/ (strips frontmatter)
aec generate rules

# Regenerate the agent instruction files (from templates/)
aec generate files

# Validate parity (also runs in pre-commit hook)
aec validate
```

After regenerating, commit the changes:

```bash
git add .agent-rules/ templates/
git commit -m "chore: regenerate agent rules and files"
```

## Updating submodules

Submodules track the latest commits on their default branches (same as `aec update` and the post-merge hook):

```bash
git submodule update --init --recursive --remote
```

## File purposes

| File | Purpose | Edit in project? |
|------|---------|------------------|
| `AGENTS.md` | Project-specific info plus rule references, read by every agent | **YES** — fill this in |
| `CLAUDE.md`, `GEMINI.md`, `QWEN.md` | `@AGENTS.md` import, plus agent-specific notes | Only for agent-specific notes |
| `.cursor/rules/*.mdc` | Development standards (Cursor) | No — shared across projects |
| `.agent-rules/*.md` | Development standards (other agents) | No — generated from `.cursor/rules/` |

Projects set up before AEC moved to `AGENTS.md` use the older layout: `AGENTINFO.md` holds the project info and `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and `QWEN.md` point to it. AEC keeps that layout until you run `aec migrate agents-md`, which `aec rollback` can undo. Claude Code reads `AGENTS.md` through the `@AGENTS.md` import ([docs](https://code.claude.com/docs/en/memory#agents-md)).
