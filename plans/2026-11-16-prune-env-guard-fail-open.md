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
- A path is a candidate when any component starts with `.env`, in any case (`.ENV`, `.Env.local`; APFS is
  case-insensitive).
- "Outside this worktree" and "a copy exists" are proven by the data surviving the whole sweep, by one helper,
  `survives_removal <physical path>`. It walks the resolved path's ancestors and compares each with `-ef`
  (filesystem identity, never path text, so case aliases, firmlinks and symlinked ancestors are caught) against
  every linked worktree of the repo (`git worktree list --porcelain`, primary excluded, the candidate always
  included). Inside any of them: not proven. Under `$PROJECTS_ROOT` but outside the repo's primary checkout:
  not proven (the sweep may remove other repos' worktrees). Otherwise proven.
- A regular file is exempt only if byte-identical to a primary-checkout copy that is itself a regular,
  non-symlink file, whose resolved physical path (parents included) is not the same inode and survives the sweep
  (unchanged otherwise, #141).
- A symlink is resolved with a pure Bash 3.2 resolver (`realpath` is absent and `readlink -f` unsupported on
  older macOS); failure, a loop, or a target that does not exist (dangling or unreadable) keeps the tree.
- A resolved target is exempt if it survives the sweep. Inside the worktree it is exempt only if it is a regular
  file that git tracks, with no index flag (`ls-files -v` tag `H`; assume-unchanged and skip-worktree hide local
  edits from `status` and `diff`) and no difference from the index. A directory, the worktree root, a target
  in another worktree, or an ignored or untracked file keeps the tree.
- git lists an ignored nested repo or worktree as one `dir/` entry and never enumerates its files; the tree is
  kept if `find -iname '.env*'` finds anything in it (or fails to read it).
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
  through parent symlinks, `.env` names in other cases, and ignored nested repos; plus the cases that must stay
  exempt: a target in an unrelated directory outside the projects root or in the primary checkout).

## Known limit

A target inside a linked worktree of a different repo that lives outside `$PROJECTS_ROOT` is treated as safe
(the rule above covers this repo's worktrees and everything under the projects root). Closing it would need
`git rev-parse --git-dir` vs `--git-common-dir` on the target's directory. Reachable when that repo sits under
the projects root (so it is swept) with its worktrees elsewhere; deferred.

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
