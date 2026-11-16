# prune-merged-worktrees: the ignored-.env guard fails open

**Status:** fix shipped in the PR that adds this file.
**Priority:** P1, data loss (the script deletes worktrees; the data it fails to protect is unrecoverable).

The hole is **pre-existing in the shipped `staging` and `main` script** (since v2.48.7). This PR closes it; it does
not introduce it.

## Root cause

`scripts/prune-merged-worktrees.sh` decided whether a merged, clean worktree holds ignored `.env*` data of its own
with one pipeline:

```
git ls-files -o -i --exclude-standard | grep -E '(^|/)\.env' | while read f; do ... echo "$f"; done | grep -q .
```

1. **Fail-open on the pipeline status.** With `set -o pipefail`, `grep -q .` exits on the first hit; the `while`
   loop takes SIGPIPE on its next `echo`, the pipeline returns non-zero, and the `if` reads "no unique .env".
   One unique ignored `.env` file keeps the worktree; 2, 3, 5 or 2000 mark it removable. Any failure of
   `git ls-files` also read as "nothing to keep".
2. **Symlink exemption without a target check.** Every `.env*` symlink was exempt. `.env -> only-copy`, where
   `only-copy` is ignored and exists only in the worktree, was deleted with the worktree.

Four review rounds of "prove the data survives" (symlink target resolution, a cross-worktree protect list, an
`-ef` ancestor walk) each found new holes in the proof. The script cannot see every link on disk, so a proof of
safety cannot be complete. The fix therefore stops proving and refuses.

## Correct fix: the blunt rule

Keep a worktree if it holds ANY of:

- an untracked or ignored path with a `.env*` component, in any case (`.env`, `.ENV`, `.Env.local`, `conf/.eNv`,
  `.env.d/anything`; APFS is case-insensitive), including anything found inside an ignored nested repo (git lists
  one as a single `dir/` entry; the script runs `find -iname '.env*'` in it);
- any `.env*` symlink, tracked or not, to any target. There is no target analysis;
- any tracked file flagged assume-unchanged or skip-worktree (`ls-files -v` tag `h`, `S` or `s`), because those
  flags make `git status` call a locally edited file clean;
- a file name containing a newline, which cannot be parsed safely.

The only exemption (#141 is preserved): a **regular, non-symlink** file whose bytes are identical (`cmp -s`) to the
same relative path in the primary checkout, where that copy is itself a regular, non-symlink file and no parent
directory on its path is a symlink.

Everything the script cannot establish keeps the worktree and prints why: `git status`, `git ls-files`, `find`
or `mktemp` failing or being killed (any scan exit status other than "may go" is a keep, `scan failed, exit N`), a
warning from git about an unreadable directory (git exits 0 for that), a failed `git rev-parse` or
`git worktree list` for a repo (the repo is skipped with a printed reason), a failed `gh pr list` (the repo is
skipped with a printed reason). Statuses are captured explicitly; no `| grep -q` or `| head` sits behind a keep
decision.

Ordering: `du` runs first, then the scan, then `git worktree remove` immediately. `git status --porcelain -uall`
overrides `status.showUntrackedFiles=no`. The single scan sits right before the removal, so a file created while
`du` ran is seen.

The result replaces the 213-line two-pass design with one scan function. Deleted: pass 1, pass 2, the sweep
inventory, the protect list, `survives_removal`, the path resolver.

Output wording for the data case is unchanged: `keep <path>  (<branch>: holds ignored .env files)`.

### What reclaim is lost

A merged worktree is no longer pruned automatically when it holds any `.env*` file that is not byte-identical to a
regular primary copy, any `.env*` symlink, or any flagged index entry, or when any part of it cannot be scanned.
Those worktrees stay until a person removes them. That is deliberate: disk reclaim is worth less than one lost
secret.

## Residual limits (documented, not solved)

1. **A link held elsewhere.** An `.env*` symlink held in the primary checkout, in another repo, or in a kept
   worktree, that points through a non-`.env*` target into a worktree this sweep removes, is not seen: the script
   cannot enumerate every link on disk. Example: the primary's `.env -> ../wt/only-copy` loses `only-copy` when
   `wt` is removed. Reproducers t4 9R, t5 17d and t6 from the data-loss hunt (not in the test suite: nothing the
   script can see distinguishes them).
2. **No lock window.** Nothing locks the worktree between the final scan and `git worktree remove`. A `.env*`
   file created in that instant is lost. The window is one `git` invocation; the scan sits immediately before it.
   A quarantine-rename was considered and rejected as more machinery than the window warrants.
3. **Submodules.** The scan does not look inside initialized submodules. `git worktree remove` refuses a worktree
   with one, which is all that protects an ignored `.env` in a submodule (pinned by a test that expects `FAILED`).
4. **Temp-list read-back.** A failure to read the temp list after it was written successfully is not handled
   separately; it cannot happen short of the file being deleted under the script.

## Affected surfaces

- `scripts/prune-merged-worktrees.sh`: the guard and the discovery loop's failure reporting. Nothing else changed.
- Callers: the scheduled prune (cron/launchd) and anyone running the script by hand. It now prints `keep` where
  it used to print `would`/`removed` for the cases above.
- Tests: `tests/test_prune_env_guard.py` (real git repo, stub `gh`, real script under `/bin/bash`), one test per
  refusal branch plus controls that prove a worktree with nothing to protect is really removed (a real run, and a
  `.worktrees/<topic>` layout inside the primary checkout). A mutation check flipping each keep to a remove in a
  scratch copy was run: every mutant fails a test.

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
