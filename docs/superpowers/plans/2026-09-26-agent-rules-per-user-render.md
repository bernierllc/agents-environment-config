# Render agent rules per user, not into the tracked `.agent-rules/`

**Status:** Proposed (found closing out the 2026-09-24 install-fix session)
**Priority:** Tier 2 — placement confirmed by Matt (2026-09-27)

## Root cause

`.agent-rules/` is tracked in git **and** is every user's installed rule set:
`~/.agent-tools/rules/agents-environment-config` is a symlink to the repo's
`.agent-rules/` (`aec/commands/agent_tools.py`, repo symlinks). `aec install`
runs `rules.generate()` twice (`aec/commands/install.py` "Generating
.agent-rules/" and "Applying settings to rules..."), and `generate()` renders
the user's own settings into those tracked files via
`rules._apply_settings()` (`plans_dir`, `plans_completion`, `pr_open_mode`).

Consequences:

- Any user with a non-default setting (e.g. `plans_dir: .plans`) gets a dirty
  checkout after every install: dozens of modified `.agent-rules/*.md` files
  that must never be committed, and that block fast-forward pulls.
- Even with default settings, `generate()` writes a trailing newline the
  committed files lack, so the files churn anyway. `aec rules validate`
  compares with `.strip()`, so CI never notices the drift.
- The committed copy is whatever the last committer's settings produced, not
  a canonical default rendering.

Committing a fresh default render would not fix it: the next `aec install`
on a machine with custom settings rewrites the files again.

## Correct fix

Separate the two roles `.agent-rules/` plays today:

1. **Repo copy (tracked):** always rendered with *default* settings, byte-for-
   byte what `generate()` writes. `aec rules validate` compares exactly (no
   `.strip()`), so CI fails on drift. It remains the rules catalog
   (`get_source_dirs()["rules"]`).
2. **Installed copy (per user):** `~/.agent-tools/rules/agents-environment-config/`
   becomes a real directory, not a symlink. `aec install` / `aec update`
   render the rules into it *with the user's settings* (same
   `_strip_frontmatter` + `_apply_settings` pipeline, different target).
   `generate()` with user settings never writes into the repo again.

Migration: on the next `aec install`, replace an existing symlink at that path
(only if it points at this repo's `.agent-rules/`, per the ownership record
from the managed-symlink plan once that lands) with the rendered directory.

## Affected surfaces

- `aec/commands/rules.py` — `generate()` (target dir + settings on/off),
  `validate()` (exact comparison), `_apply_settings()` callers
- `aec/commands/install.py` — both `rules.generate()` calls; render the
  installed copy instead of the repo copy after settings prompts
- `aec/commands/agent_tools.py` — the Rules entry in the repo-symlinks list
  (and the Cursor rules link at `CURSOR_DIR / "rules" / "agents-environment-config"`)
- `aec/commands/doctor.py` — checks that expect the rules path to be a symlink
  (lines ~253, ~323) and the `.agent-rules/` parity check (~490)
- `aec update` / `aec upgrade` — re-render the installed copy when rules change
- `.agent-rules/` — one-time regeneration with defaults (fixes the newline
  drift) in the same PR as the exact-match validate
- Tests: installed copy honors `plans_dir`/`pr_open_mode`; repo copy is
  unchanged by an install with custom settings; validate fails on a
  one-byte difference; symlink → directory migration.

## Related

- `docs/superpowers/plans/2026-09-25-managed-symlink-ownership.md` — same
  links; land ownership-by-record first or together so the migration can tell
  AEC's rules link from a user's own.
