# prune-merged-worktrees: harden the ignored-.env guard (follow-up to #165)

**Status:** planned. #165 landed with the three findings below waived by the maintainer in its review, and deferred here.
**Priority:** P1, data loss. The script deletes worktrees; the data the guard misses is unrecoverable.

## Root cause

`env_data_reason` in `scripts/prune-merged-worktrees.sh` (added by the fail-open fix, see
`2026-11-16-prune-env-guard-fail-open.md`) decides "does this worktree hold ignored `.env*` data of its own" from
three inputs that are each trusted more than they should be: git's own listing of ignored files, git's index flags,
and the platform's path resolver. Three cases still read an unverifiable state as "nothing to keep".

## Deferred findings (each needs a failing-first test)

1. **P1, assume-unchanged / skip-worktree.** A symlink target inside the worktree counts as "tracked" when
   `git ls-files --error-unmatch` finds it, but a file marked `assume-unchanged` or `skip-worktree` is tracked
   with local content git does not compare, so `git status` stays clean and the content is lost.
   Fix: read `git ls-files -v` for the target and keep the tree when the flag is not plain `H`
   (or compare the target's bytes with the index blob).
2. **P1, C-quoted names.** `git ls-files` prints names with non-ASCII bytes or newlines quoted and escaped, so the
   `*/.env*` match and the `$path/$f` lookups see a different name than the file on disk.
   Fix: `git ls-files -z -o -i --exclude-standard` and a NUL-delimited read loop (Bash 3.2: `read -r -d ''`).
3. **P2, readlink / realpath portability.** Stock macOS has neither `readlink -f` nor always `realpath`; both fail
   and the guard keeps the tree with the same message, so every symlinked `.env` is reported as data.
   Fix: a small Bash 3.2 resolver (`cd -P` on the directory part plus a bounded `readlink` loop), or report
   once that resolution is unavailable instead of repeating "holds ignored .env files".

## Fixed in #165 itself (found by the final review, both P2, each with a test)

- A symlink target with glob characters (`only-copy[1]`) was matched as a pathspec against a tracked
  `only-copy1`. Fix: `git --literal-pathspecs`.
- A symlink to a directory counted as tracked when any file under it was tracked. Fix: only a regular file
  target (`[ -f ]`) can be exempt.

## Surfaces

- `scripts/prune-merged-worktrees.sh` (the guard only).
- `tests/test_prune_env_guard.py` (one new test per deferred finding; real git repo, stub `gh`, real script under
  `/bin/bash` 3.2).
- `CLAUDE.md` / `AGENTINFO.md` Scripts entry if the reported wording changes.

## Done when

Each of the three cases has a test that fails on the current script and passes on the fix, and the three review
threads from #165 are closed with `fixed in <sha>` replies.
