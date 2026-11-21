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
3. With valid `.aec/installed-hooks` state, `install_item_hooks` already calls `_remove_recorded_hooks` before
   merging, so a changed fingerprint is replaced, not appended. The duplicate therefore needs missing or stale
   state, and the gemini and cursor payloads carry neither the item key nor the source hook id (those exist only
   in the translated entries and the state file), so the merge cannot identify its own entries without state.
   Give each entry a durable on-disk identity: an AEC-owned marker in the entry (for example a stable
   `item:hook-id` key, if the agent's config schema tolerates the extra field; verify against each agent's
   documented schema before coding, otherwise encode it in a comment-free, schema-valid place such as the
   command's script name). Entries written before the marker existed are adopted explicitly: an entry whose
   command targets an AEC-installed script path is claimed and rewritten with the marker, and the install reports
   each adoption. Never claim a user-authored entry by guessing.

## Tests

- Run the installer from a linked worktree twice: `.gemini/settings.json` AND `.cursor/hooks.json` each hold
  exactly one entry per hook, the recorded state in `.aec/installed-hooks` is unchanged by the second run, and
  none of these files contains the worktree's absolute path. (`_merge_cursor_entries` and `_render_script_path`
  share the gemini cause, so cursor is covered by the same tests.)
- Install in the main checkout, then in a worktree, and compare: the rendered gemini and cursor entries are
  identical.
- Missing state: delete `.aec/installed-hooks`, install twice from a worktree: still one entry per hook in
  `.gemini/settings.json` and `.cursor/hooks.json`.
- Stale state (recorded fingerprint no longer matches the entry on disk): the next install replaces, not appends.
- Legacy entries without the marker (the shape already on disk today): adopted and reported once, then
  idempotent; a user-authored entry beside them is left untouched.
- Existing duplicate entries (already on disk) are collapsed on the next install.
- State refreshed without fingerprints: a downstream install whose recorded `content_fingerprint` (gemini
  `/hooks/BeforeTool/N`, claude `/hooks/PreToolUse/N`) was left unchanged while `item_version` and
  `hooks_file_hash` moved after a re-install from a linked worktree. Reproduce first by diffing the recorded
  fingerprint against `fingerprint_hook` of the on-disk entry; if they differ, the state writer is stale. Test: after
  any install or upgrade, every recorded `content_fingerprint` equals `fingerprint_hook` of the entry now on disk.

## Affected surfaces

`aec/lib/hooks/installer.py`, `aec/lib/hooks/state.py`, `aec/lib/scope.py`, `aec/lib/hooks/lifecycle.py`,
hook docs.
