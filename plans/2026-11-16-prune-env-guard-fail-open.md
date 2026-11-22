# prune-merged-worktrees: the ignored-.env guard fails open

**Status:** fix shipped in the PR that adds this file.
**Priority:** P1, data loss (the script deletes worktrees; the data it fails to protect is unrecoverable).

## Root cause

`scripts/prune-merged-worktrees.sh` decides whether a merged, clean worktree holds ignored `.env*` data of its
own with one pipeline:

```
git ls-files -o -i --exclude-standard | grep -E '(^|/)\.env' | while read f; do ... echo "$f"; done | grep -q .
```

Two defects, both shipped since v2.48.7:

1. **Fail-open on the pipeline status.** With `set -o pipefail`, `grep -q .` exits on the first hit; the `while`
   loop takes SIGPIPE on its next `echo`, the pipeline returns non-zero, and the `if` reads "no unique .env".
   One unique ignored `.env` file keeps the worktree; 2, 3, 5 or 2000 mark it removable. Any failure of
   `git ls-files` also read as "nothing to keep".
2. **Symlink exemption without a target check.** Every `.env*` symlink was exempt. `.env -> only-copy`, where
   `only-copy` is ignored and exists only in the worktree, was deleted with the worktree.

## Correct fix

One helper, `env_data_reason`, owns the decision and fails closed:

- Capture `git ls-files` output first and check its exit status; on failure keep the tree and say why.
- Iterate the captured list with a here-string. No `grep -q` at the end of a pipeline.
- A `.env*` regular file is exempt only if byte-identical to the primary checkout's copy (unchanged, #141).
- A `.env*` symlink is exempt only if it is dangling, resolves outside the worktree, or resolves to a tracked
  file inside it. A symlink to an ignored or untracked file inside the worktree is unique data. A target that
  cannot be resolved keeps the tree.
- Output wording for the data case is unchanged: `keep <path>  (<branch>: holds ignored .env files)`.

## Affected surfaces

- `scripts/prune-merged-worktrees.sh` (the guard only; no other lines changed).
- Callers: the scheduled prune (cron/launchd) and anyone running the script by hand.
- Tests: `tests/test_prune_env_guard.py` (real git repo, stub `gh`, real script; covers 1, 2 and 50 unique files,
  byte-identical copy, symlinks in/out of the worktree and dangling, and an injected `git ls-files` failure).

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
