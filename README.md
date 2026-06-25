# `aec` — the package manager for AI-coding workspaces

> **One CLI, every agent.** Install rules, skills, and agents once. Set up new projects in seconds. Catch port collisions and test leaks before they bite. Cross-agent — Claude Code, Cursor, Codex, Gemini, Qwen.

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config
pip install -e .
aec install
```

> This is a **template repository**. Project-specific content goes in each project's `AGENTINFO.md` — not here.

## What you get

| | What it does |
|---|---|
| **Cross-agent rule sync** | Write rules once. AEC ships them to Claude (`CLAUDE.md`), Cursor (`.mdc` w/ frontmatter), Codex (`AGENTS.md`), Gemini, and Qwen — formatted correctly for each, parity-checked on commit. |
| **Catalog package manager** | `aec install / uninstall / list / search / outdated / upgrade` for skills, rules, and agents. Semver dependencies, dismissals, and an automatic prompt to promote per-repo installs to a single global one once you've used it in N repos. |
| **Project bootstrapper** | `aec setup` drops agent files, lint/typecheck hooks (TS, Rust, Python, Go, Ruby), git essentials (`.gitignore`, CI, dependabot, PR/issue templates, LICENSE, CODEOWNERS), `.aec.json`, and Raycast launchers. |
| **Multi-project ops** | A central port registry (no more `:3000` collisions), test framework detection, scheduled cross-project test runs (launchd, cron, Task Scheduler), profiling, leak detection, and opt-in parallel lanes. |
| **Discovery + governance** | `aec discover` finds the agent/skill/rule files you already had and brings them under management. Org admins can publish a single YAML of required, blocked, and pinned items. |

Cross-platform: macOS, Linux, Windows (NTFS junctions, no admin needed). All driven by one [`agents.json`](agents.json) source of truth.

## Quick start

> **New to Python/pip?** `pip` requires Python 3.10+. See the [official pip installation guide](https://pip.pypa.io/en/stable/installation/).

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config
pip install -e .

aec install              # full setup
aec install --dry-run    # preview first
```

After `aec install` you'll have:

- `~/.agent-tools/{rules,agents,skills,commands}/` — central tooling shared by every agent
- Agent-specific symlinks for Claude (`~/.claude/`) and Cursor (`~/.cursor/`)
- User preferences: projects directory, plans directory, port registry, test scheduler, report viewer

Then point `aec` at any project — new or existing:

```bash
aec setup my-new-project
aec setup /path/to/existing/project
aec setup --all                       # walk your projects directory
```

`aec setup` detects your stack, drops agent files, installs lint hooks, registers ports, finds existing skills/agents/rules, and offers to fill in missing git essentials.

## Supported agents

AEC handles the format differences between agents automatically. You write rules once; each agent gets them in the format it expects.

| Agent | Instruction file | Detection | Hooks | Description |
|-------|------------------|-----------|-------|-------------|
| Claude Code | `CLAUDE.md` | `claude` command or `~/.claude` | Yes | Anthropic's CLI coding agent |
| Cursor | `.cursor/rules/*.mdc` | `cursor` command or `/Applications/Cursor.app` | Yes | AI-first IDE with Cursor rules |
| Codex | `AGENTS.md` | `codex` command | No | OpenAI's coding agent |
| Gemini CLI | `GEMINI.md` | `gemini` command | Yes | Google's CLI coding agent |
| Qwen Code | `QWEN.md` | `qwen` command | No | Alibaba's coding agent |

All non-Cursor agents read `.agent-rules/*.md` (plain markdown). Cursor reads `.cursor/rules/*.mdc` (with YAML frontmatter). AEC keeps both in sync from a single source. See [Rules architecture](docs/users/rules-architecture.md).

Adding another agent is one JSON entry — see [Adding agent support](docs/contributors/adding-agent-support.md).

## Solo, team, or org

- **Solo.** Clone, `aec install`, done. Every project picks up a coherent set of rules, agents, skills, and MCP servers.
- **Team.** Share `.agent-rules/` and `.cursor/rules/` across machines. AEC's parity check catches drift between formats.
- **Org.** IT/admin teams publish an **org config** — a single YAML describing required, recommended, blocked, and pinned items, plus default preferences. Users enroll with `aec org enroll <path>`. AEC never hosts org configs; each org publishes their own. (Phase 1, behind `pip install aec[org-configs-preview]`.) See [Org configs for users](docs/users/org-configs.md) and [Authoring org configs](docs/orgs/authoring-org-configs.md).

## Command cheat sheet

```bash
# Install / update
aec install                  # full setup
aec install <type> <name>    # one skill / rule / agent
aec update && aec upgrade    # fetch + apply upgrades
aec doctor                   # health check

# Projects
aec setup [path]             # track a project
aec setup --all              # track everything in your projects dir
aec list                     # show installed items
aec search <term>            # search catalog

# Ports
aec ports list | check | register | unregister | validate

# Tests
aec test run [-g]            # local / scheduled cross-project
aec test schedule            # set up automated daily runs
aec test report [-g]         # latest results

# Discovery
aec discover [-g]            # find existing items matching the catalog
```

Full reference: [CLI commands](docs/users/cli-reference.md).

## Plugins

AEC manages a fifth item type — **plugins** — alongside skills, rules, agents, and packages.

```bash
aec install plugin <name|url>   # install a plugin
aec uninstall plugin <name>     # remove a plugin
```

Plugins also appear in `aec list`, `aec info plugin <name>`, `aec search`, `aec outdated`, `aec export`, and `aec apply`.

### Install types

Each plugin declares its `install_type` in a `plugin.json` manifest:

- **`marketplace`** — Claude-only; AEC runs the marketplace install command after you confirm (or pass `--yes`).
- **`per-tool`** — per-agent install; if the plugin provides a `run` command, AEC runs it after confirmation; otherwise it prints `steps` as instructions only.
- **`external`** — AEC **never executes anything**; it prints the publisher's download URL and instructions verbatim.

### Never-auto-install guarantee

AEC never auto-installs any plugin. `marketplace` and `per-tool` commands only run after explicit user confirmation (or `--yes`). `external` plugins are always instructions-only — no execution, ever.

To downgrade every plugin to print-only (no execution even for `marketplace`/`per-tool`):

```bash
aec config set plugins.execution instructions-only   # print steps only, never run
aec config set plugins.execution default             # restore confirm-then-run
```

AEC installs a plugin only to the agents that both the plugin `supports` and are detected in your project.

Plugin publishers: ship a `plugin.json` loadout alongside your plugin. See [docs/loadout/](docs/loadout/) for the schema and examples.

## Documentation

**Using AEC**

- [CLI reference](docs/users/cli-reference.md)
- [Catalog: installing skills, rules, agents](docs/users/catalog.md)
- [Discovery](docs/users/discovery.md)
- [Lint hooks](docs/users/lint-hooks.md)
- [Port registry](docs/users/ports.md)
- [Test runner & scheduler](docs/users/test-runner.md)
- [Git essentials phase](docs/users/git-essentials.md)
- [`.aec.json` schema](docs/users/aec-json.md)
- [Preferences & local config](docs/users/preferences.md)
- [Org configs](docs/users/org-configs.md)
- [Raycast integration](docs/users/raycast.md)
- [Rules architecture](docs/users/rules-architecture.md)
- [Troubleshooting](docs/users/troubleshooting.md)

**Contributing**

- [Architecture](docs/contributors/architecture.md)
- [Generation pipeline](docs/contributors/generation-pipeline.md)
- [Testing](docs/contributors/testing.md)
- [Adding agent support](docs/contributors/adding-agent-support.md)
- [Adding hook language](docs/contributors/adding-hook-support.md)
- [Adding git provider](docs/contributors/adding-git-provider-support.md)
- [Adding test framework](docs/contributors/adding-test-framework-support.md)

## Repository layout

```
agents-environment-config/
├── aec/                  # Python CLI package
├── .agent-rules/         # Rules without Cursor frontmatter (generated)
├── .cursor/rules/        # Rules with frontmatter (source of truth)
├── .claude/{agents,skills}/   # Submodules: agency-agents, skills
├── agents.json           # Single source of truth for agent definitions
├── templates/            # Files copied into your projects (CLAUDE.md, etc.)
├── scripts/              # Setup, hooks, validators
├── raycast_scripts/      # Raycast launchers (parity-checked with scripts/)
└── docs/                 # User & contributor docs
```

## Trade-offs

| Benefit | Cost |
|---|---|
| Consistent rules across every agent | Maintain two file versions (`.mdc` + `.md`) |
| ~5% token savings per rule for non-Cursor agents | Pre-commit parity validation |
| User-extension points in `~/.agent-tools/` | A directory layout to learn |

## Related repos

- [agency-agents](https://github.com/bernierllc/agency-agents) — agent definitions
- [skills](https://github.com/bernierllc/skills) — skill definitions

## Security

- Never commit `.env` files. API keys go in `.env` (copy from `.env.template`).
- Review API key permissions — use least-privilege access.

## Hook key repair

Earlier versions of AEC wrote `.claude/settings.json` with camelCase hook keys (e.g., `postToolUse`) instead of the PascalCase keys Claude Code requires (`PostToolUse`). AEC automatically detects and fixes this in all tracked repos when you run `aec install`, `aec update && aec upgrade`, or `aec doctor`. No manual editing needed.
