# `aec install skill` from a git worktree must not duplicate hooks

Status: planned. Scheduling pending (Tracker row, Owner `Needs-PM`).

## Problem

Running `aec install skill <name>` from a linked git worktree appends a second gemini `BeforeTool` hook to
`.gemini/settings.json`. The new entry carries the worktree's absolute path, and `.aec/installed-hooks/*`
is repointed at it. The change then travels in the PR and breaks the main checkout and every other clone.

## Root cause (confirm before coding)

`find_tracked_repo` treats a linked worktree as its own install target (`aec/lib/scope.py`, by design). The
hook installer renders gemini and cursor script paths as absolute paths (`_render_script_path`), and the hook
fingerprint includes the rendered command, so a worktree install produces a different fingerprint than the
main checkout's and `_merge_gemini_entries` appends instead of replacing.

## Correct fix

1. The selected worktree stays its own install target (the documented contract of `find_tracked_repo`): hook
   configuration and `.aec/installed-hooks` are written in that worktree and never redirected to another
   checkout. Redirecting would dirty a different tree, and the git common directory is not a reliable pointer to
   the main work tree for separate-git-dir layouts.
2. Render gemini and cursor script paths so they do not depend on the checkout location (the repo-relative or
   env-anchored form the claude and git renderers already use), so a worktree's files never carry its absolute
   path.
3. The merge identifies an entry by item and hook id, not by the rendered command, so a second install from any
   location replaces rather than appends.

## Tests

- Run the installer from a linked worktree twice: `.gemini/settings.json` AND `.cursor/hooks.json` each hold
  exactly one entry per hook, the recorded state in `.aec/installed-hooks` is unchanged by the second run, and
  none of these files contains the worktree's absolute path. (`_merge_cursor_entries` and `_render_script_path`
  share the gemini cause, so cursor is covered by the same tests.)
- Install in the main checkout, then in a worktree, and compare: the rendered gemini and cursor entries are
  identical.
- Existing duplicate entries (already on disk) are collapsed on the next install.

## Affected surfaces

`aec/lib/hooks/installer.py`, `aec/lib/hooks/state.py`, `aec/lib/scope.py`, `aec/lib/hooks/lifecycle.py`,
hook docs.
