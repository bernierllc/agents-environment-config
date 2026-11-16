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

1. Decide the single owner of "which checkout holds installed hook state": the main checkout (the git common
   directory's work tree). Hook wiring and `.aec/installed-hooks` resolve to it, whichever worktree the command
   runs from; the worktree keeps its own skill files only when they are untracked there.
2. Alternatively (or additionally) render gemini/cursor paths so they do not depend on the checkout location.
   Choose one in review; both must satisfy the idempotence test below.
3. The merge identifies an entry by item and hook id, not by the rendered command, so a second install from any
   location replaces rather than appends.

## Tests

- Run the installer from a linked worktree twice: `.gemini/settings.json` holds exactly one entry per hook,
  and neither file contains the worktree's absolute path.
- Install from the main checkout, then from a worktree: still one entry; state unchanged.
- Existing duplicate entries (already on disk) are collapsed on the next install.

## Affected surfaces

`aec/lib/hooks/installer.py`, `aec/lib/hooks/state.py`, `aec/lib/scope.py`, `aec/lib/hooks/lifecycle.py`,
hook docs.
