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
3. **The scan only looked for `.env*`.** A review pass found that the same sweep also deleted other ignored data that
   exists only in the worktree: nested git repos with unpushed history (including ones under `node_modules`) and
   secret-named files that are not `.env*` (`.npmrc`, `*.pem`, `id_rsa`, and so on). Round 5 closes those two.

Four review rounds of "prove the data survives" (symlink target resolution, a cross-worktree protect list, an
`-ef` ancestor walk) each found new holes in the proof. The script cannot see every link on disk, so a proof of
safety cannot be complete. The fix therefore stops proving and refuses.

## Correct fix: the blunt rule

The guard is fail-closed: anything not positively proven safe keeps the worktree.

Keep a worktree if it holds ANY of:

- an untracked or ignored path with a `.env*` component, in any case (`.env`, `.ENV`, `.Env.local`, `conf/.eNv`,
  `.env.d/anything`; APFS is case-insensitive), including anything found inside an ignored nested repo (git lists
  one as a single `dir/` entry; the script runs `find -iname '.env*'` in it). This applies everywhere, including
  under `node_modules`;
- any `.env*` symlink, tracked or not, to any target. There is no target analysis;
- any tracked file flagged assume-unchanged or skip-worktree (`ls-files -v` tag `h`, `S` or `s`), because those
  flags make `git status` call a locally edited file clean;
- a file name containing a newline, which cannot be parsed safely;
- **(round 5)** an untracked or ignored **nested `.git`**, file or directory, anywhere below the worktree root other
  than the worktree's own. It is unpushed history the sweep cannot prove is on a remote. This applies everywhere,
  including under `node_modules`. Printed as `holds a nested git repo`;
- **(round 5)** an untracked or ignored **secret-named file**, matched case-insensitively: `*.env`, `.dev.vars*`,
  `.npmrc`, `.netrc`, `.pypirc`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`. Printed as
  `holds secret-named files`.

The only exemptions:

1. (#141 is preserved) a **regular, non-symlink** file with a `.env*` component whose bytes are identical (`cmp -s`)
   to the same relative path in the primary checkout, where that copy is itself a regular, non-symlink file and no
   parent directory on its path is a symlink.
2. **(round 5)** The secret NAME rule (the list above) is not applied to a path with a `node_modules`, `.venv`,
   `venv` or `site-packages` component. Dependency trees and virtualenvs ship `*.pem`, `*.key` and `id_rsa`-named
   test fixtures by the hundred, and keeping every worktree that ran `npm install` would defeat the script. The
   exemption covers the NAME rule only: the `.env*` rule and the nested-`.git` rule still apply there. The
   component test is exact and case-sensitive (`my_node_modules`, `node_modules.bak`, `Node_Modules`, `venv2`,
   `site-packages-old` are not exempt), so a doubtful path is scanned, not skipped.

Primary comparison: the discovery loop skips the primary checkout with `[ "$path" -ef "$repo" ]` (same inode), not a
text compare, because `git worktree list` prints real paths while the `$ROOT/*/.git` glob walks through a symlinked
`$PROJECTS_ROOT`. Under text compare the primary would be treated as a removable worktree.

Everything the script cannot establish keeps the worktree and prints why: `git status`, `git ls-files`, `find`
or `mktemp` failing or being killed (any scan exit status other than "may go" is a keep, `scan failed, exit N`), a
warning from git about an unreadable directory (git exits 0 for that), the nested-`.git` `find` failing or warning,
a failed `git rev-parse` or `git worktree list` for a repo (the repo is skipped with a printed reason), a failed
`gh pr list` (the repo is skipped with a printed reason). Statuses are captured explicitly; no `| grep -q` or
`| head` sits behind a keep decision.

How the nested-`.git` scan works: `git ls-files -z -o` collapses a **valid** nested repo to one `dir/` entry but
skips a **broken** one silently (an empty `.git` directory, a dangling gitfile), so its files look like plain files.
A separate `find <worktree> -name .git -prune -print0` therefore lists every `.git` name. A tracked submodule's own
`.git` (index mode `160000`) is excluded and left to `git worktree remove`, which refuses a worktree with an
initialized submodule (`FAILED`), as before.

Ordering: `du` runs first, then the scan, then `git worktree remove` immediately. `git status --porcelain -uall`
overrides `status.showUntrackedFiles=no`.

The result replaces the 213-line two-pass design with one scan function. Deleted: pass 1, pass 2, the sweep
inventory, the protect list, `survives_removal`, the path resolver.

Output wording for the data case is unchanged: `keep <path>  (<branch>: holds ignored .env files)`. The round-5 keeps
use the same shape: `keep <path>  (<branch>: holds a nested git repo)` and
`keep <path>  (<branch>: holds secret-named files)`.

### What reclaim is lost

A merged worktree is no longer pruned automatically when it holds any `.env*` file that is not byte-identical to a
regular primary copy, any `.env*` symlink, any flagged index entry, any nested `.git` (**blunt, with a real cost**:
a worktree that ran `npm install` of a package that vendors a git checkout, or that holds any cloned dependency, is
kept), any secret-named file outside a package tree, or when any part of it cannot be scanned. Those worktrees stay
until a person removes them. That is deliberate: disk reclaim is worth less than one lost secret or one lost commit.

## Residual limits (documented, not solved)

1. **A link held elsewhere.** An `.env*` symlink held in the primary checkout, in another repo, or in a kept
   worktree, that points through a non-`.env*` target into a worktree this sweep removes, is not seen: the script
   cannot enumerate every link on disk. Example: the primary's `.env -> ../wt/only-copy` loses `only-copy` when
   `wt` is removed. Reproducers t4 9R, t5 17d and t6 from the data-loss hunt (not in the test suite: nothing the
   script can see distinguishes them).
2. **No lock window.** Nothing locks the worktree between the final scan and the removal, and the removal is not one
   git invocation: `git worktree remove` makes its own `git status` pass before it deletes. Measured with 100k ignored
   files, the gap between the script's scan finishing and the deletion starting is **1.19 s**. A `.env*` file (or
   other protected data) created inside that window is lost. A quarantine-rename was considered and rejected as more
   machinery than the window warrants. An earlier revision of this file and of a script comment said the window was
   "one `git` invocation"; that was wrong.
3. **Submodules.** The scan does not look inside initialized submodules. `git worktree remove` refuses a worktree
   with one, which is all that protects an ignored `.env` in a submodule (pinned by a test that expects `FAILED`).
4. **Other ignored data without a secret name.** Ignored `.otto/` run-state and sqlite files under ignored caches,
   and any other ignored file whose name is not on the secret list, are still lost with the worktree. Follow-up item
   PRUNE-NONENV-NAMES; not fixed here.
5. **Temp-list read-back.** A failure to read the temp list after it was written successfully is not handled
   separately; it cannot happen short of the file being deleted under the script.

## Affected surfaces

- `scripts/prune-merged-worktrees.sh`: the guard and the discovery loop's failure reporting. Nothing else changed.
- Callers: the scheduled prune (cron/launchd) and anyone running the script by hand. It now prints `keep` where
  it used to print `would`/`removed` for the cases above.
- Tests: `tests/test_prune_env_guard.py` (real git repo, stub `gh`, real script under `/bin/bash`). A test, or a parametrized set, per
  refusal branch (the mutation check below names the 8 statements no test can tell from their removal), including each round-5 branch (nested `.git` under `node_modules`, in a path with spaces, empty
  `.git` directory, dangling gitfile, nested linked worktree, `find` failing three ways; each of the 11 secret
  name patterns in mixed case), and one control per exemption (package trees removed, lookalike directory names
  not exempt, `.env` still kept under `node_modules`, a symlinked `$PROJECTS_ROOT` still skips the primary). Controls
  prove a worktree with nothing to protect is really removed (a real run, and a `.worktrees/<topic>` layout inside
  the primary checkout).

## Mutation check

Method: single-edit mutants of the script applied to a scratch copy, the test file pointed at the copy, `pytest -x`
per mutant; a failing run is KILLED. Two harnesses, both kept out of the repo.

**Pass (b), on the round-4 head `c9d5fa47` (the pre-round-5 script):** 124 entries, one of which (m98) is a no-op
control that must survive, so 123 real mutants: **114 killed, 9 survived**. The recorded run files show 114 killed
and 10 survivors of 124; two figures quoted elsewhere for this pass (93 killed, and 115 killed with 33 added tests)
could not be reproduced from those files and are not repeated here. The 9 survivors, with why:

| id | mutation | why it survives |
|---|---|---|
| m29 | first index read drops `IFS=` | a record starts with its tag character, never whitespace: equivalent |
| m46 | dir `find` drops `2>&1` | `find` exits non-zero for every error it reports, so the `rc` check still keeps: equivalent |
| m47 | dir arm `*/)` widened to `*)` | on `c9d5fa47` the extra `find` calls print nothing: equivalent (round 5 added arms below it, so this mutation is now killed) |
| m58 | `rev-parse HEAD` keeps stderr | stderr is not in the `$(...)` comparison: equivalent |
| m63 | `status` stderr not merged | failure is caught by the exit code; a warning is not dirt: equivalent |
| m66 | `|| continue` after merged `pr_heads` dropped | empty `merged` means no branch has a sha, so nothing is removed: equivalent in effect |
| m83 | `pipefail` dropped | no pipeline decides a keep any more: equivalent for keeps |
| m94 | `du` stderr left on | display only: equivalent |
| m102 | `du` path unquoted | **real, cosmetic gap**: a path with spaces prints `0M` instead of the size. No data effect; not pinned by a test |

**Round-5 head (new branches only):** 50 mutants of the new code (primary `-ef`; the nested-`.git` scan and its
submodule exclusion; each of the 11 secret name patterns removed and made case-sensitive; the three keep returns; the
package-tree exemption removed, loosened to substring, case-folded, reordered, widened). First run: 47 killed, 3
survived. Two survivors were real test gaps and got a test each: a submodule-exclusion match loosened to a substring
(a nested repo at `su` hid behind the submodule `sub`), and the exemption also skipping the `.env*` scan of a nested
repo under `node_modules` (the tree was still kept, but for the wrong reason). After those tests: **49 killed, 1
survives**: dropping `-prune` from the nested-`.git` `find`. It is equivalent for the verdict (a `.git` directory holds
no entry named `.git`, so the walk finds nothing extra); `-prune` only stops `find` walking the object store of each
nested repo. Full suite on this head: 190 passed, no skips.

**Round-5 head `aab6599`, the full pass-(b) list re-run against the whole script** (190 tests; five patches, m30, m31,
m123, m69 and m133, re-targeted because round 5 changed their text: a second `ls-files` check line and the `-ef`
primary skip; all 124 patches apply exactly once). 124 entries, m98 the no-op control: **123 real mutants, 115 killed,
8 survived**, and the control survived as it must. Against `c9d5fa47` the differences are m47 and m102, both now
killed (round 5 added arms and a test for the reported size of a path with a space), and one new survivor, m52.
None of the 8 survivors changes whether a tree is kept or removed:

| id | why it survives |
|---|---|
| m29, m46, m58, m63, m66, m83, m94 | as in the table above: equivalent or display only |
| m52 | the dir-arm `find` failure message loses its `return 0`; control falls to the next line, where `find`'s merged stderr is non-empty (m46 shows the same), and the nested-`.git` `find` that runs after it fails the same way and keeps the tree. Only the printed reason differs: equivalent for the verdict |

The 8 are the only statements a test cannot tell from their removal. Everything else in the script that decides a
keep or a removal is pinned by at least one test that fails when it is changed.

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
