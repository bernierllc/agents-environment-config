# Skill Versioning & Copy-Based Installation

> Design spec for migrating AEC from symlink-based skill installation to copy-based
> installation with per-skill versioning, selective install, and update management.

## Problem

Claude Code cannot discover skills via symlinks ([anthropics/claude-code#14836](https://github.com/anthropics/claude-code/issues/14836)).
AEC currently creates a symlink chain:
- `~/.claude/skills/agents-environment-config` → `~/.agent-tools/skills/agents-environment-config` → `repo/.claude/skills/`

Skills behind this symlink are invisible to Claude Code's `/skills` listing and autocomplete.

## Core Principle

**AEC must never auto-install anything.** User optionality is a core principle. Every
install/update action must be opt-in. When new skills become available, notify the user
but never install automatically.

---

## Part 1: Skill Versioning Standard (claude-skills repo)

### SKILL.md Frontmatter

Every skill MUST include `version` and `author` fields in YAML frontmatter:

```yaml
---
name: my-skill
description: What it does and when to use it.
version: 1.0.0
author: Bernier LLC
---
```

**Version bump rules:**
- **PATCH** (0.0.x): Bug fixes, typo corrections, minor wording improvements
- **MINOR** (0.x.0): New capabilities, new reference files, expanded instructions
- **MAJOR** (x.0.0): Breaking changes — renamed skill, restructured workflow, removed
  features that users may depend on

**Skills without a version** are treated as `0.0.0` by AEC.

**Version must be bumped on every PR** that modifies a skill's SKILL.md or supporting
files (references/, scripts/, assets/).

### Nested Skills (document-skills)

The skills repo contains a `document-skills/` directory with grouped skills inside it
(docx, pdf, pptx, xlsx, etc.). These are handled as follows:

- **Discovery**: AEC reads `skills-manifest.json` which already flattens nested skills
  to top-level keys (e.g., `"docx"`, `"pdf"` — not `"document-skills/docx"`)
- **Source path mapping**: The manifest includes the relative path to the skill directory.
  For nested skills: `document-skills/docx/`. For top-level: `brand-guidelines/`
- **Copy destination**: Always flattened to `~/.claude/skills/<name>/`
  (e.g., `~/.claude/skills/docx/`, not `~/.claude/skills/document-skills/docx/`)
- **User-facing**: Users see `docx`, `pdf`, etc. as individual skills in `aec skills list`.
  The `document-skills/` grouping is an organizational detail of the source repo only.

### Skills Manifest

A `skills-manifest.json` at the repo root provides a machine-readable index:

```json
{
  "manifestVersion": 1,
  "generatedAt": "2026-03-30T12:00:00Z",
  "skills": {
    "skill-name": {
      "version": "1.0.0",
      "description": "...",
      "author": "Bernier LLC",
      "path": "skill-name"
    },
    "docx": {
      "version": "1.0.0",
      "description": "...",
      "author": "Anthropic",
      "path": "document-skills/docx"
    }
  }
}
```

The `path` field is the relative directory path from the skills repo root. Auto-generated
via `scripts/generate-manifest.py` and committed to the repo.

### Status

- [x] `version` and `author` fields added to all existing SKILL.md files
- [x] `skills-manifest.json` generated and committed
- [x] `agent_skills_spec.md` updated
- [x] `CONTRIBUTING.md` updated
- [ ] Add `path` field to manifest entries (update generate-manifest.py)
- [ ] Push missing Bernier LLC skills (commit, gdocs, ux-audit, verification-writer)
  to the claude-skills repo

---

## Part 2: Installed Skills Manifest (AEC)

AEC tracks installed skills in `AEC_HOME / "installed-skills.json"`
(`~/.agents-environment-config/installed-skills.json`):

```json
{
  "manifestVersion": 1,
  "installedAt": "2026-03-30T14:00:00Z",
  "updatedAt": "2026-03-30T14:00:00Z",
  "skills": {
    "commit": {
      "version": "1.0.0",
      "contentHash": "sha256:a1b2c3...",
      "installedAt": "2026-03-30T14:00:00Z",
      "source": "agents-environment-config"
    }
  }
}
```

Fields:
- `version`: The version from SKILL.md frontmatter at install time
- `contentHash`: SHA-256 hash of all non-hidden files in the skill directory, computed
  by sorting file paths, concatenating `path + content` for each, and hashing the result.
  Used for drift detection (see Part 6).
- `installedAt`: ISO-8601 timestamp of when this skill was installed/updated
- `source`: Provenance — currently always `agents-environment-config`

### Manifest Recovery

If `installed-skills.json` is missing or corrupt, AEC scans `~/.claude/skills/` for
directories, reads their SKILL.md frontmatter, and rebuilds the manifest. Skills without
a `version` field are recorded as `0.0.0`. The `contentHash` is computed from the
current directory state. This handles migration from the current state where skills like
`browser-verification`, `commit`, `gdocs`, `ux-audit`, `verification-writer` are already
real directories but untracked.

---

## Part 3: Symlink Cleanup

During `aec install` and `aec update`, before any skill copy operations:

1. **Remove only AEC-created symlinks** — specifically:
   - `~/.claude/skills/agents-environment-config` (→ `~/.agent-tools/skills/agents-environment-config`)
   - `~/.agent-tools/skills/agents-environment-config` (→ `repo/.claude/skills/`)
2. **Verify before removing** — check that the symlink target path contains
   `agent-tools` or `agents-environment-config` in its resolution chain. If a symlink
   at that name points somewhere else, leave it alone.
3. **No broad symlink scanning** — only these two known paths, nothing else.
4. **Never touch non-AEC content** — directories like `braingrid-cli`, `gdocs`, or any
   other skills the user has placed in `~/.claude/skills/` are never modified or removed
   by the cleanup step, regardless of whether they are symlinks or real directories.
5. **Log removals** — print: `Cleaned up legacy symlink: <path>`

---

## Part 4: `aec install` Skills Step

New interactive step in the install flow, inserted after submodule update and agent-tools
setup.

### Updated install flow

1. Initialize `~/.agents-environment-config/` *(existing)*
2. Update git submodules (agents, skills) *(existing)*
3. Generate `.agent-rules/` *(existing)*
4. Set up `~/.agent-tools/` structure *(existing, but skip skills symlink creation)*
5. **NEW: Clean up legacy AEC symlinks**
6. **NEW: Skills install/update step**
7. Detect installed agents *(existing)*
8. Prompt for settings *(existing)*
9. Repair hooks *(existing)*
10. Batch project setup *(existing)*

### First install (no manifest exists)

Present a numbered list of available skills:

```
Available skills:

  1. algorithmic-art (1.0.0) — Creating algorithmic art using p5.js...
  2. brand-guidelines (1.0.0) — Applies Anthropic's official brand colors...
  3. browser-verification (1.0.0) — Use when performing manual QA...
  ...
  18. template-skill (1.0.0) — Replace with description...

Install: [a]ll, [n]one, or enter numbers (e.g. 1,3,5-8):
```

**Note**: No external dependency for UI. Uses numbered list with `input()` and supports
ranges (e.g., `1,3,5-8`), `a`/`all`, or `n`/`none`. Follows the zero-extra-dependency
pattern of the existing codebase.

### Subsequent installs (manifest exists)

Only prompt if there are changes:

```
Skill updates available:
  browser-verification: 1.0.0 → 1.1.0
New skills available:
  my-new-skill (1.0.0) — Does something cool
Install updates and new skills? [a]ll, [s]elect, [S]kip:
```

If nothing has changed, skip silently.

### Dry-run behavior

In `--dry-run` mode, the skills step shows the numbered list and reports what would be
installed ("Would install 12 skills") but does not prompt or copy. Follows the existing
`_prompt_settings` dry-run pattern.

---

## Part 5: `aec skills` Subcommands

New command group registered in `cli.py`, following the Typer pattern used by `aec repo`,
`aec preferences`, etc. **Must be registered in both Typer and argparse fallback paths.**

### `aec skills list`

Unified view of all available and installed skills:

```
Skills (source: agents-environment-config)

  Name                    Installed    Available    Status
  ─────────────────────────────────────────────────────────
  algorithmic-art         1.0.0        1.0.0        up to date
  brand-guidelines        —            1.0.0        available
  browser-verification    1.0.0        1.1.0        update available
  commit                  1.2.0        1.2.0        up to date
  canvas-design           —            1.0.0        available
  ...

  Other skills (not managed by AEC):
    braingrid-cli
    my-custom-skill

  12 installed, 3 updates available, 5 not installed
```

Skills in `~/.claude/skills/` that are not in the AEC manifest are shown separately as
"Other skills (not managed by AEC)".

### `aec skills install <name> [name2 ...]`

- Copies skill from submodule source to `~/.claude/skills/<name>/`
- Updates installed-skills manifest
- Errors if skill name not found in source
- Supports `--yes`/`-y` flag to skip confirmation

### `aec skills uninstall <name> [name2 ...]`

- Confirmation prompt: `Remove browser-verification from ~/.claude/skills/? [y/N]`
- Removes `~/.claude/skills/<name>/` directory
- Removes entry from installed-skills manifest
- Supports `--yes`/`-y` flag to skip confirmation

### `aec skills update [name]`

- No argument: updates all installed skills that have newer versions available
- With name: updates just that skill
- Shows before/after: `browser-verification: 1.0.0 → 1.1.0`
- Prompts for confirmation before copying
- Supports `--yes`/`-y` flag to skip confirmation
- **Stale detection**: compares installed versions against the local submodule source
  manifest (no network call). If installed version matches source version for all skills,
  reports "All skills up to date." If the user suspects newer versions exist upstream,
  they should run `aec install` which updates the submodule first.

---

## Part 6: Copy Mechanics and Edge Cases

### Copy strategy

- Use `shutil.copytree(src, dst)` to copy skill directories
- Before copying an update, `shutil.rmtree` the existing directory then copy fresh
  (avoids orphaned files from deleted references)
- Skip hidden files (`.git`, `.DS_Store`) during copy via `ignore` parameter
- Ensure `~/.claude/skills/` directory exists before any copy operation
  (`CLAUDE_DIR / "skills"`, created with `ensure_directory()`)

### Version comparison

Use simple tuple comparison on split integers — no external dependency:
```python
def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))
```

This is sufficient since all skill versions follow strict `MAJOR.MINOR.PATCH` format.

### Content hashing

SHA-256 of all non-hidden files in the skill directory:
```python
def hash_skill_directory(path: Path) -> str:
    hasher = hashlib.sha256()
    for filepath in sorted(path.rglob("*")):
        if filepath.is_file() and not filepath.name.startswith("."):
            hasher.update(str(filepath.relative_to(path)).encode())
            hasher.update(filepath.read_bytes())
    return f"sha256:{hasher.hexdigest()}"
```

Computed at install time and stored in the manifest. Used for drift detection on update.

### Edge cases

1. **User-modified installed skill** — Detect drift by comparing current content hash
   against the `contentHash` recorded in the installed manifest. If they differ, warn:
   `browser-verification has local modifications. Overwrite? [y/N]`

2. **Skills not from AEC** — Skills in `~/.claude/skills/` not in our manifest are
   left completely alone. This explicitly includes `braingrid-cli` and any other
   user-created or third-party skills. Shown in `aec skills list` under "Other skills
   (not managed by AEC)".

3. **Manifest missing/corrupt** — Rebuild by scanning `~/.claude/skills/` and reading
   SKILL.md frontmatter. Handles migration from current untracked state.

4. **Submodule not updated** — `aec install` already updates submodules. `aec skills
   update` compares against local submodule source only (no network). If user wants
   latest, they run `aec install` first.

5. **`~/.claude/skills/` does not exist** — Create it with `ensure_directory()` before
   any copy operation.

---

## Part 7: `aec doctor` Updates

Add health checks:

- `installed-skills.json` exists and is valid JSON
- Each skill in the manifest has a matching directory in `~/.claude/skills/`
- No stale AEC symlinks remain at the two known paths
- Installed skill versions match what's recorded in the manifest (detect drift)

---

## Part 8: `agent_tools.setup()` Modifications

- **Stop creating** the `~/.claude/skills/agents-environment-config` symlink
- **Stop creating** the `~/.agent-tools/skills/agents-environment-config` symlink
- Keep `~/.agent-tools/skills/` directory itself (organizational parent)
- Keep rules, agents, and commands symlinks unchanged (not affected)

---

## Files Changed (AEC Repo)

| File | Change |
|------|--------|
| `aec/commands/skills.py` | **NEW** — `aec skills` command group (list, install, uninstall, update) |
| `aec/lib/skills_manifest.py` | **NEW** — read/write installed-skills.json, parse SKILL.md frontmatter, version comparison, content hashing |
| `aec/commands/install.py` | Add skills step to install flow, add symlink cleanup |
| `aec/commands/agent_tools.py` | Remove skills symlink creation from `setup()` |
| `aec/commands/doctor.py` | Add skills health checks |
| `aec/cli.py` | Register `aec skills` command group (both Typer and argparse fallback) |

## Files Changed (claude-skills Repo)

| File | Change |
|------|--------|
| All `SKILL.md` files | Added `version: 1.0.0` and `author` field — **DONE** |
| `skills-manifest.json` | Generated — **DONE** |
| `agent_skills_spec.md` | Documented `version` field — **DONE** |
| `CONTRIBUTING.md` | Added versioning guidance — **DONE** |
| `scripts/generate-manifest.py` | Add `path` field to manifest entries — **TODO** |
| Missing skills | Push commit, gdocs, ux-audit, verification-writer — **TODO** |
