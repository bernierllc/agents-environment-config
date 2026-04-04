# Brew-Aligned CLI Redesign

> Design spec for restructuring the AEC CLI to follow Homebrew's command model with
> local/global scope support for skills, rules, and agents.

## Problem

The current AEC CLI organizes commands under nested subgroups (`aec repo update`,
`aec skills install`, `aec rules generate`). This creates several issues:

1. **No single `aec update`** — users expect a top-level update command (like `brew update`)
   but must know to run `aec repo update` and `aec skills update` separately.
2. **Skill updates don't happen** — `aec repo update` doesn't trigger `aec skills update`,
   so installed skills go stale silently (the v2.0.0 verification skills bug).
3. **No scope model** — users may want different skills/rules in different repos, but the
   CLI only manages global installs.
4. **Unfamiliar command structure** — developers know `brew install`, `npm install`, `pip install`.
   Nobody knows `aec skills install`.

## Core Principles

1. **AEC must never auto-install or auto-upgrade anything.** User optionality is a core
   principle. Every install and upgrade action must be opt-in. `update` (fetching latest
   sources) is not an install/upgrade action — it only refreshes what's available.
2. **Explicit scope.** Default is local (current repo). `-g` for global. Error if not in a
   tracked repo without `-g`.
3. **Fetch and apply are separate.** `update` fetches what's new. `upgrade` applies changes.
4. **Flat commands.** No nested subgroups for the core lifecycle. `aec install`, not
   `aec skills install`.
5. **Read commands are permissive, write commands are strict.** Read-only commands (`list`,
   `search`, `outdated`) show all applicable scopes without requiring `-g`. Write commands
   (`install`, `uninstall`) require explicit scope resolution — error if ambiguous.
6. **`update` is scope-exempt.** Fetching sources is a single git operation on the AEC repo.
   There is no "local fetch" vs "global fetch" — there's one source of truth. What varies
   by scope is what gets *reported* as outdated, not what gets fetched.

---

## Command Surface

### Core Lifecycle

| Command | Description |
|---|---|
| `aec update` | Pull latest AEC repo + submodules. Report what's outdated. |
| `aec upgrade` | Apply available upgrades to installed items. |
| `aec install <type> <name>` | Install a skill, rule, or agent. |
| `aec uninstall <type> <name>` | Remove a skill, rule, or agent. |
| `aec list` | Show installed items. |
| `aec search <term>` | Search available skills, rules, and agents. |
| `aec outdated` | Show what has upgrades available. |
| `aec info <type> <name>` | Show detailed metadata for a specific item. |

### Project Management

| Command | Description |
|---|---|
| `aec setup` | Full first-time bootstrap, or `aec setup <path>` to track a repo. |
| `aec setup --all` | Track all repos in configured projects directory. |
| `aec untrack <path>` | Stop tracking a repo. Removes AEC config from it. |
| `aec prune` | Remove stale tracking entries (repos no longer on disk). |
| `aec discover` | Discover repos from Raycast scripts (`--dry-run`, `--auto`). |

### Generation & Validation

| Command | Description |
|---|---|
| `aec generate rules` | Generate `.agent-rules/` in a tracked repo. |
| `aec generate files` | Generate agent instruction files from templates. |
| `aec validate` | Validate rule parity across agents. |

### System

| Command | Description |
|---|---|
| `aec doctor` | Health check for installation. |
| `aec config` | Manage preferences (replaces `aec preferences`). |
| `aec version` | Show version. |

---

## Scope Model

AEC manages three types of installable items across two scopes:

### Installable Types

| Type | Global location | Local location |
|---|---|---|
| `skill` | `~/.claude/skills/<name>/` | `.claude/skills/<name>/` |
| `rule` | `~/.agent-tools/rules/<project>/<path>` | `.agent-rules/<path>` |
| `agent` | `~/.claude/agents/<name>.md` | `.claude/agents/<name>.md` |

### Scope Behavior

**`install` / `uninstall` (write commands):**
- Default scope is **local** (current tracked repo).
- Use `-g` for global scope.
- If not in a tracked repo and no `-g` flag: **error**.
  > "Not in a tracked repo. Use `-g` for global install, or `cd` into a project first."

**`update` (scope-exempt):**
- Always pulls latest AEC repo + submodules. This is a single git operation — there is
  no local vs global fetch. The AEC repo is the one source of truth for available versions.
- After fetching, reports what's outdated per scope:
  - Always reports global scope.
  - If in a tracked repo, also reports local scope.
  - Mentions other tracked repos may have updates.

**`upgrade` (write command, special scope rules):**
- Always upgrades global scope.
- If in a tracked repo, also upgrades local scope.
- Offers to scan and upgrade other tracked repos:
  ```
  3 other tracked repos have upgrades available:
    ~/projects/api-server       2 skills outdated
    ~/projects/dashboard        1 rule outdated
    ~/projects/mobile-app       1 skill outdated

  Upgrade them too? [y/N/list]
  ```

**`list` / `outdated` / `search` / `info` (read commands):**
- Always include global scope.
- If in a tracked repo, also include local scope.
- Output clearly separates global vs local sections.
- `list` and `outdated` support `--all` to scan all tracked repos.

---

## Command Details

### `aec update`

Fetches the latest available versions without changing any installed items.

**Implementation:**
1. `git pull` the AEC repo (fast-forward only).
2. `git submodule update --init --recursive`.
3. Compare installed manifest(s) against source.
4. Print summary.

**Output example:**
```
$ aec update
Pulling latest... done.

Global:
  2 skills have updates (verification-writer 1.0→2.0, browser-verification 1.0→2.0)

Local (~/projects/my-app):
  1 skill has updates (verification-writer 1.0→2.0)

3 other tracked repos may have updates. Run `aec outdated --all` to check.

Run `aec upgrade` to apply.
```

**Not in a tracked repo:**
```
$ aec update
Pulling latest... done.

Global:
  2 skills have updates (verification-writer 1.0→2.0, browser-verification 1.0→2.0)

Run `aec upgrade` to apply.
```

### `aec upgrade`

Applies available upgrades to installed items.

**Flags:**
- `--yes` / `-y`: Skip confirmation prompts.
- `--dry-run`: Show what would change without applying.

**Implementation:**
1. Check if sources are stale (last `aec update` > 24h ago). If so, warn:
   > "Sources are 3 days old. Run `aec update` first? [Y/n]"
   Do not auto-fetch. Wait for user response.
2. For each scope (global, local, other repos):
   - Compare installed versions against available versions.
   - Detect local modifications via content hash (SHA-256 of sorted non-hidden files).
   - If modified: prompt "X has local modifications. Overwrite? [y/N]"
   - Copy new version, update manifest.
3. Offer to upgrade other tracked repos.

**Output example:**
```
$ aec upgrade
Upgrading global scope...
  ✓ skill verification-writer  1.0.0 → 2.0.0
  ✓ skill browser-verification 1.0.0 → 2.0.0

Upgrading ~/projects/my-app (current repo)...
  ✓ skill verification-writer  1.0.0 → 2.0.0

3 other tracked repos have upgrades available:
  ~/projects/api-server       2 skills outdated
  ~/projects/dashboard        1 rule outdated
  ~/projects/mobile-app       1 skill outdated

Upgrade them too? [y/N/list]
```

### `aec install <type> <name>`

Install a skill, rule, or agent.

**Positional arguments:**
- `type`: one of `skill`, `rule`, `agent`
- `name`: the item name (e.g., `verification-writer`, `typescript/typing-standards`)

**Flags:**
- `-g`: Install to global scope.
- `--yes` / `-y`: Skip confirmation.

**Implementation:**
1. Resolve scope (local or global).
2. Verify item exists in available sources.
3. Copy to target location.
4. Record in installed manifest (global or local).

**Output example:**
```
$ aec install skill verification-writer
Installing verification-writer v2.0.0 to ~/projects/my-app/.claude/skills/...
  ✓ Installed verification-writer v2.0.0

$ aec install -g skill verification-writer
Installing verification-writer v2.0.0 to ~/.claude/skills/...
  ✓ Installed verification-writer v2.0.0
```

### `aec uninstall <type> <name>`

Remove a skill, rule, or agent from the current scope.

**Positional arguments:**
- `type`: one of `skill`, `rule`, `agent`
- `name`: the item name

**Flags:**
- `-g`: Uninstall from global scope.
- `--yes` / `-y`: Skip confirmation.

**Implementation:**
1. Resolve scope.
2. Confirm with user (show what will be removed).
3. Remove files from target location.
4. Remove from installed manifest.

Note: To stop tracking a repo, use `aec untrack <path>` — not `aec uninstall`.
The `uninstall` command is exclusively for the three installable types (skill, rule, agent).

### `aec info <type> <name>`

Show detailed metadata for a specific installed item.

**Output example:**
```
$ aec info skill verification-writer
verification-writer v2.0.0
  Author:      Bernier LLC
  Description: Generate QA verification checklists
  Installed:   global (2026-04-04), local ~/projects/my-app (2026-04-04)
  Modified:    no (hash matches source)
  Files:       SKILL.md, references/ (3 files), scripts/ (1 file)
```

### `aec list`

Show installed items across applicable scopes.

**Output example (in a tracked repo):**
```
$ aec list
Global:
  skill  verification-writer     v2.0.0
  skill  browser-verification    v2.0.0
  skill  commit                  v1.0.0
  rule   typescript/typing-std   v1.2.0

Local (~/projects/my-app):
  skill  verification-writer     v2.0.0
  agent  code-reviewer           v1.0.0

Tracked repos: 4
```

**Flags:**
- `--type skill|rule|agent`: Filter by type.
- `--scope global|local`: Filter by scope.
- `--all`: Include all tracked repos (not just current).

### `aec search <term>`

Search available items. Shows items regardless of install status, but marks installed
items so the user knows what they already have.

**Output example:**
```
$ aec search verification
skill  verification-writer     v2.0.0  Generate QA verification checklists     [global, local]
skill  browser-verification    v2.0.0  Browser-based QA verification runner    [global]
```

Items with no bracket annotation are not installed anywhere. `[global]` means installed
globally, `[local]` means installed in the current repo, `[global, local]` means both.

**Flags:**
- `--type skill|rule|agent`: Filter by type.

### `aec outdated`

Show items with available upgrades across all scopes and tracked repos.

**Output example:**
```
$ aec outdated
Global:
  skill  verification-writer     1.0.0 → 2.0.0
  skill  browser-verification    1.0.0 → 2.0.0

Local (~/projects/my-app):
  skill  verification-writer     1.0.0 → 2.0.0

~/projects/api-server:
  skill  commit                  1.0.0 → 1.1.0
  rule   testing/standards       1.0.0 → 1.1.0

~/projects/dashboard:
  (up to date)
```

**Flags:**
- `--type skill|rule|agent`: Filter by type.
- `--all`: Scan all tracked repos (default: global + current repo only).

### `aec untrack <path>`

Stop tracking a repo. Removes AEC configuration from it.

**Implementation:**
1. Confirm with user (show what will be removed from the repo).
2. Optionally remove local installs (skills, rules, agents) from the repo.
3. Remove repo from tracking registry.
4. Remove repo entries from installed manifest.

**Output example:**
```
$ aec untrack ~/projects/my-app
This will stop tracking ~/projects/my-app and remove:
  - .claude/skills/verification-writer/
  - .claude/agents/code-reviewer.md
  - .agent-rules/ (generated rules)

Remove AEC config from this repo? [y/N]
```

### `aec setup`

First-time bootstrap or repo tracking.

**Modes:**
- `aec setup` (no args, not yet installed): Full first-time AEC installation (creates
  `~/.agent-tools/`, global manifests, etc.).
- `aec setup` (no args, already installed, in an untracked repo): Offers to track the
  current repo.
- `aec setup` (no args, already installed, not in a repo): Reports current installation
  status.
- `aec setup <path>`: Track a specific repo. Creates local AEC structure in that repo.
- `aec setup --all`: Track all repos in configured projects directory.
- `aec setup --skip-raycast`: Skip Raycast integration during setup.

**Absorbs:** current `aec install`, `aec repo setup`, `aec repo setup-all`,
`aec agent-tools setup`, `aec agent-tools migrate`.

### `aec config`

Manage user preferences. Replaces `aec preferences`.

**Subcommands:**
- `aec config list`: Show all preferences and their values.
- `aec config set <key> <value>`: Set a preference.
- `aec config reset <key>`: Reset a preference to default.

### `aec generate`

Generate agent configuration files.

**Subcommands:**
- `aec generate rules`: Generate `.agent-rules/` directory.
- `aec generate files`: Generate agent instruction files from templates.

**Relationship with `aec install rule`:** `aec generate rules` produces the *full* set of
rules for a repo from templates. `aec install rule <name>` installs a *single* rule into
a repo's `.agent-rules/` or the global rules directory. Installing a single rule does not
conflict with generation — installed rules are tracked in the manifest and `generate` will
not overwrite them. If a generated rule and an installed rule have the same path, the
installed version takes precedence and `generate` will skip it with a note.

### `aec validate`

Validate rule parity across agent platforms (Claude, Cursor, Gemini, etc.).

### `aec prune`

Remove stale repo tracking entries where the repo directory no longer exists on disk.
Unlike `aec untrack`, this does not modify repo contents — it only cleans the registry.

**Flags:**
- `--yes` / `-y`: Skip confirmation.
- `--dry-run`: Show what would be pruned.

### `aec discover`

Discover repos from Raycast scripts. Unchanged from current implementation.

**Flags:**
- `--dry-run`: Show what would be added without adding it.
- `--auto`: Add missing paths without prompting.

---

## Content Hashing

All three installable types (skills, rules, agents) use SHA-256 content hashing for
drift detection. The algorithm:

1. Collect all non-hidden files in the item's directory (or the single file for agents/rules).
2. Sort by relative path.
3. For each file, hash the relative path bytes followed by the file content bytes.
4. Produce `sha256:<hex digest>`.

This hash is recorded in the manifest at install time. Before upgrading, the current hash
is compared against the recorded hash. If they differ, the user has made local modifications
and is prompted before overwriting.

---

## Manifest Changes

### Global Manifest

Location: `~/.agents-environment-config/installed-manifest.json`

Repo keys use **absolute paths** to avoid tilde-expansion ambiguity across tools and contexts.

```json
{
  "manifestVersion": 2,
  "updatedAt": "2026-04-04T00:00:00Z",
  "lastUpdateCheck": "2026-04-04T00:00:00Z",
  "global": {
    "skills": {
      "verification-writer": {
        "version": "2.0.0",
        "contentHash": "sha256:abc123...",
        "installedAt": "2026-04-04T00:00:00Z"
      }
    },
    "rules": {},
    "agents": {}
  },
  "repos": {
    "/Users/matt/projects/my-app": {
      "skills": {
        "verification-writer": {
          "version": "2.0.0",
          "contentHash": "sha256:abc123...",
          "installedAt": "2026-04-04T00:00:00Z"
        }
      },
      "rules": {},
      "agents": {}
    }
  }
}
```

The manifest tracks both global and per-repo installs in one file. This lets `aec outdated`
and `aec upgrade` scan everything without visiting each repo on disk.

The `lastUpdateCheck` field records when `aec update` was last run, enabling the stale
source warning in `aec upgrade`.

### Migration from v1 Manifest

The current `installed-skills.json` (manifestVersion 1) will be migrated:
1. On first run of new CLI, detect v1 manifest.
2. Move all entries into `global.skills`.
3. Scan tracked repos for locally installed skills.
4. Write v2 manifest.
5. Remove old `installed-skills.json`.

---

## Breaking Changes

| Old Command | New Command | Migration |
|---|---|---|
| `aec install` (full setup) | `aec setup` | Alias with deprecation warning for 1 major version |
| `aec repo setup <path>` | `aec setup <path>` | Direct replacement |
| `aec repo setup-all` | `aec setup --all` | Direct replacement |
| `aec repo list` | `aec list` (repos shown in output) | Absorbed |
| `aec repo prune` | `aec prune` | Direct replacement |
| `aec repo update` | `aec update` + `aec upgrade` | Split into fetch vs apply |
| `aec skills list` | `aec list` / `aec search` | Absorbed |
| `aec skills install <name>` | `aec install skill <name>` | Reordered args |
| `aec skills uninstall <name>` | `aec uninstall skill <name>` | Reordered args |
| `aec skills update` | `aec upgrade` | Renamed |
| `aec rules generate` | `aec generate rules` | Reordered |
| `aec rules validate` | `aec validate` | Promoted to top-level |
| `aec files generate` | `aec generate files` | Reordered |
| `aec agent-tools setup` | `aec setup` | Absorbed |
| `aec agent-tools migrate` | `aec setup` (auto-detects) | Absorbed |
| `aec agent-tools rollback` | removed (no longer needed) | Drop |
| `aec preferences list/set/reset` | `aec config list/set/reset` | Renamed |
| `aec discover` | `aec discover` | Unchanged |

### Deprecation Strategy

For one major version after this change:
1. Old commands still work but print a deprecation warning with the new command.
2. Help text shows new commands only.
3. Next major version removes old commands entirely.

---

## Scope Detection

### How AEC Determines Scope

1. **Local scope**: Walk up from `cwd` looking for `.claude/` or `.agent-rules/` directory
   that is in a tracked repo (listed in `~/.agents-environment-config/repos.json`).
2. **Global scope**: Always available. Uses `~/.claude/`, `~/.agent-tools/`.
3. **Not in a repo**: If no tracked repo found in parent directories and no `-g` flag,
   write commands (`install`, `uninstall`) error out. Read commands (`list`, `search`,
   `outdated`, `info`) show global scope only.

### Tracked Repo Registry

Existing `~/.agents-environment-config/repos.json` continues to serve as the registry
of tracked repos. `aec setup <path>` adds to it, `aec prune` cleans it,
`aec untrack <path>` removes from it.

---

## Prior Art

This design builds on the skill versioning spec from 2026-03-30. The versioning standard
(semver in SKILL.md frontmatter), content hashing, and drift detection from that spec
remain unchanged. What changes is the command surface and scope model that wraps them.
The content hashing approach is extended from skills-only to all three installable types.

---

## Out of Scope

- **Network-based updates**: AEC sources remain local (git submodules). No registry server.
- **Dependency resolution**: Skills/rules/agents are independent. No dependency graph.
- **Lockfiles**: The manifest serves as the install record. No separate lockfile.
- **Rollback**: If an upgrade breaks something, user re-installs the old version manually
  or reverts the AEC repo. Could be a future enhancement.
