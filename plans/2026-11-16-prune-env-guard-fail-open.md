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
- A path is a candidate when ANY component of it starts with `.env`, in any case (`.ENV`, `.Env.local`; APFS is
  case-insensitive). This name test runs first on every listed path. A collapsed `dir/` entry (git lists an
  ignored nested repo or worktree as one entry and never enumerates its files) whose own path carries the name
  keeps the tree; any other `dir/` entry keeps it when `find -iname '.env*'` finds anything inside (or fails).
- Paths keep their bytes: `$(...)` strips trailing newlines (a link to `config` + newline read as a link to the
  tracked `config`), so the resolver returns its result in a global, reads `pwd -P` and `readlink -n` with a
  sentinel character, and a resolved path that contains a newline is "not proven": keep.
- Data is shared across worktrees and repos, so the sweep has two passes. Pass 1 walks every repo under
  `$PROJECTS_ROOT` and records every linked worktree of each (`git worktree list --porcelain`, the primary
  checkout excluded, a registered worktree whose directory is gone skipped). It then finds the `.env*` symlinks in
  each of those worktrees (candidates or not, merged or not), resolves them, and records every worktree a link
  in a *different* worktree points into: the protect list. Pass 2 is the per-worktree decision below, and it keeps
  a worktree on the protect list (`holds data an .env symlink in another worktree points at`). Keeping the
  holder of the link therefore never lets the sweep remove the worktree that holds the data, in either direction.
  Pass 1 failing to read anything (listing worktrees, scanning one for symlinks), or either list file being
  missing, keeps every worktree with the reason printed (an empty protect list is the normal case).
- "Outside this worktree" and "a copy exists" are proven by the data surviving the whole sweep, by one helper,
  `survives_removal <physical path> <repo>`. It walks the resolved path's ancestors and compares each with `-ef`
  (filesystem identity, never path text, so case aliases, firmlinks and symlinked ancestors are caught). Inside
  any linked worktree of any repo pass 1 found (the primary checkout of a repo included, nested or not): not
  proven. Under `$PROJECTS_ROOT` but outside this repo's primary checkout: not proven. Otherwise proven, e.g. a
  shared env file outside every worktree.
- A regular file is exempt only if byte-identical to a primary-checkout copy that is itself a regular,
  non-symlink file, whose resolved physical path (parents included) is not the same inode and survives the sweep
  (unchanged otherwise, #141).
- A symlink is resolved with a pure Bash 3.2 resolver (`realpath` is absent and `readlink -f` unsupported on
  older macOS); failure, a loop, or a target that does not exist (dangling or unreadable) keeps the tree.
- A resolved target is exempt if it survives the sweep. Inside the worktree it is exempt only if it is a regular
  file that git tracks, with no index flag (`ls-files -v` tag `H`; assume-unchanged and skip-worktree hide local
  edits from `status` and `diff`) and no difference from the index. A directory, the worktree root, a target
  in another worktree, or an ignored or untracked file keeps the tree.
- Output wording for the data case is unchanged: `keep <path>  (<branch>: holds ignored .env files)`.

## Affected surfaces

- `scripts/prune-merged-worktrees.sh` (the guard only; no other lines changed).
- Callers: the scheduled prune (cron/launchd) and anyone running the script by hand.
- Tests: `tests/test_prune_env_guard.py` (real git repo, stub `gh`, real script; covers 1, 2 and 3000 unique
  files (the 3000 case overfills the pipe, so defect A fails deterministically on the old script), odd file
  names, byte-identical and symlinked primary copies, symlinks to files, directories, the root, unreadable and
  looping targets, index-flagged targets, a bare PATH without `realpath`/`readlink -f`, an injected
  `git ls-files` failure, case and firmlink aliases of the worktree, targets in another removable worktree
  (also registered through a symlinked path), another repo under the projects root, primary copies reached
  through parent symlinks, `.env` names in other cases, ignored nested repos, an `.env*`-named parent of a nested
  repo, a link target ending in a newline, protection both ways between two worktrees (also when the link's holder
  is never removed), a worktree of another repo nested in the primary checkout, an unscannable worktree and a
  stale worktree directory; plus the cases that must stay
  exempt: a target in an unrelated directory outside the projects root or in the primary checkout).

## Known limit

Pass 1 only sees `.env*` symlinks held in linked worktrees of repos the sweep walks. A link held in a primary
checkout, or in a worktree of a repo outside `$PROJECTS_ROOT`, that points into a worktree the sweep removes is not
seen. Pass 1 also lists symlinks with `find`, so it walks ignored trees such as `node_modules` in every worktree:
slower than before, still one pass. Deferred.

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
