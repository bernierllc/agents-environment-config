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

One helper, `env_data_reason`, owns the decision. The rule: anything not positively proven safe keeps the tree.

- List with `git ls-files -z -o -i --exclude-standard` into a temp file (git quotes non-ASCII, backslash and
  newline names without `-z`, which hid them from the `.env` match), check its exit status, and read it with
  `read -r -d ''`. On failure keep the tree and say why. No `grep -q` at the end of a pipeline.
- A path is a candidate when any component starts with `.env`.
- A regular file is exempt only if byte-identical to a primary-checkout copy that is itself a regular,
  non-symlink file and not the same inode (unchanged otherwise, #141).
- A symlink is resolved with a pure Bash 3.2 resolver (`realpath` is absent and `readlink -f` unsupported on
  older macOS); failure, a loop, or a target that does not exist (dangling or unreadable) keeps the tree.
- A resolved target outside the worktree is exempt. Inside the worktree it is exempt only if it is a regular
  file that git tracks, with no index flag (`ls-files -v` tag `H`; assume-unchanged and skip-worktree hide local
  edits from `status` and `diff`) and no difference from the index. A directory, the worktree root, or an
  ignored or untracked file keeps the tree.
- Output wording for the data case is unchanged: `keep <path>  (<branch>: holds ignored .env files)`.

## Affected surfaces

- `scripts/prune-merged-worktrees.sh` (the guard only; no other lines changed).
- Callers: the scheduled prune (cron/launchd) and anyone running the script by hand.
- Tests: `tests/test_prune_env_guard.py` (real git repo, stub `gh`, real script; covers 1, 2 and 3000 unique
  files (the 3000 case overfills the pipe, so defect A fails deterministically on the old script), odd file
  names, byte-identical and symlinked primary copies, symlinks to files, directories, the root, unreadable and
  looping targets, index-flagged targets, a bare PATH without `realpath`/`readlink -f`, and an injected
  `git ls-files` failure).

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
