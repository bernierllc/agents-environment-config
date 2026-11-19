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
2. **(round 5; REMOVED in round 7, see below: secret names now keep the tree under package trees too)** The secret NAME rule (the list above) is not applied to a path with a `node_modules`, `.venv`,
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

## Round 6 (two P1s, five P2s)

Every fix is in the script, each has a test that fails on `3d0d7d78` and passes now.

- **P1-1, `git worktree prune` deleted.** The script ran it unconditionally after every repo, so `DRY_RUN=1` still
  mutated, and it deleted the admin dir of any worktree whose directory is missing. A moved folder or an unmounted
  volume looks the same as a deleted one, and a detached worktree's commit then dangles. `worktree remove` cleans up
  its own admin dir; git's gc prunes stale entries after `gc.worktreePruneExpire` (3 months). The stale-entry test is
  renamed `test_stale_worktree_entry_is_left_for_gits_own_gc` and asserts the entry stays.
- **P1-2, uninitialized submodule data.** `git status`, `ls-files -o` and `worktree remove` cannot see files under a
  gitlink (index mode `160000`) directory that has no `.git`, so a file there is lost silently. KEEP when such a
  directory is non-empty. An initialized submodule (has `.git`) stays protected by git's own refusal. A deleted
  gitlink directory is dirty, which `status` already keeps. A `find` failure there keeps (`could not scan the
  submodule directory`). A newline in a gitlink path keeps, because the path list is newline-joined.
  "Initialized" means `$dir/.git` EXISTS (`-e`, which follows links). The first cut exempted a `.git` that was a
  symlink (`-L`), found by a mutation survivor: a dangling `.git` symlink makes `git status` clean (rc 0) and
  `git worktree remove` succeed, so the files beside it were lost. Now a dangling link counts as uninitialized and
  keeps. A `.git` symlink to a real non-repo directory makes `status` fail (128) and `remove` refuse, so it stays
  with git's own refusal (control test).
- **P2-a, nested repo spelling.** `-iname .git` (`.Git`, `.GIT`), plus a bare layout: a directory `objects` beside a
  file `HEAD` and a directory `refs`, with the same (no) exemptions as the `.git` rule. Blunt: it also fires on a
  tracked folder with that layout.
- **P2-b, per-worktree refs.** KEEP when `for-each-ref refs/worktree refs/bisect refs/rewritten` is non-empty.
  `refs/rewritten` goes beyond the review's list because it is per-worktree too.
- **P2-c, stale fsmonitor.** Every git call on a worktree runs through `wgit`, which passes `-c core.fsmonitor=false`.
  A stale hook (`printf 'tok\0'` after one priming `status`) hid tracked edits. `core.untrackedCache` was tried and
  not added: git checks directory mtime, ctime, inode and size, and no way to make it hide a file was found.
- **P2-d, DRY_RUN fails closed.** Live only when unset or exactly `0`; `1`, `true`, `yes`, empty all print only.
  Header comment updated.
- **P2-e, newline in a worktree path.** `worktree list --porcelain` prints such a path verbatim over two lines. A
  line that is not a known key (`worktree`, `HEAD`, `branch`, `detached`, `bare`, `locked`, `prunable`, blank) makes
  the script keep every worktree of that repo and say why. An `awk` failure keeps too.

Tests: 53 new or changed. Against the old script `3d0d7d78` 39 fail and 14 pass (the 14 are controls: removal still
happens, an initialized submodule still fails as before, a `.git` symlink to a real directory is left to git, a
primary marked bare is accepted). All 53 pass now. Full suite (`test_prune_env_guard.py` 242 tests plus
`test_no_maintainer_specifics.py`): 245 passed, no skips. The old-script run of the final test file: 39 failed, 203
passed.

## Round 7 (option B: keep unless proven regenerable)

Why: review pass (a) reproduced a P1. Ignored files whose names are not on the secret list (`x.p8`, `up.jks`,
`prod.keystore`, `prod.tfvars`, `app.env.local`, `.git-credentials`, `credentials.json`) were deleted from a clean
merged worktree. No name list is complete, so the rule is inverted.

**The rule.** Keep the worktree if it holds ANY ignored or untracked path, unless every such path sits under a
directory from a short allowlist of regenerable output, matched by WHOLE path components, case-sensitively:
`node_modules`, `.venv`, `venv`, `site-packages`, `__pycache__`, `dist`, `build`, `.next`, `.turbo`, `coverage`,
`.pytest_cache`, `.mypy_cache`, `.ruff_cache`. Not on the list on purpose: `.cache` and anything else that can hold
user data. An allowlisted name that is a symlink (or sits below one), any other spelling (`Node_Modules`, `DIST`),
and a lookalike (`my_node_modules`, `venv2`, `distribution`) is NOT allowlisted. Printed as
`holds ignored files that are not known regenerable output (<path>)`.

- **Secret names apply everywhere**, including under the allowlisted directories (the round-5 package-tree exemption
  is gone). The glob list grew: `.git-credentials`, `credentials`, `credentials.*`, `*.p8`, `*.jks`, `*.keystore`,
  `*.tfvars`, `*.tfstate`, plus the old `.dev.vars*`, `.npmrc`, `.netrc`, `.pypirc`, `id_*`, `*.env`, `*.env.*`,
  `*.pem`, `*.key`, `*.p12`, `*.pfx`.
- Unchanged: the `.env*` rule and its single exemption (a regular file byte-identical to the primary's copy), the
  nested-repo and bare-layout keeps, uninitialized gitlinks, per-worktree refs, the dangling `.git` symlink, no
  `git worktree prune`, `wgit` (`core.fsmonitor=false`), `DRY_RUN` live only when unset or `0`, a newline in a path
  skips the repo.
- **Cost, stated:** a worktree is kept when it holds any untracked scratch file outside those directories, and a
  package tree that ships a `.pem` or `.key` fixture now keeps its worktree (round 5 exempted those). The allowlist
  trusts directory NAMES: user data placed inside `node_modules/...` or `dist/...` is treated as regenerable, as
  `git clean -X` would treat it.

**Also in round 7.**

- **P2, branch `-D` race.** The branch is deleted with `git update-ref -d refs/heads/<branch> <verified sha>`. If the
  branch moved after the scan, git refuses, the branch is kept and the script prints
  `kept    branch <b> of <repo>  (not deleted: it is now <sha>, not the checked <sha>)`. `update-ref -d` leaves the
  `branch.<name>.*` config section behind, so it is removed with `git config --remove-section`; the one exit 128
  "no such section" (a branch without upstream) is silent, any other failure prints a `note` line.
- **P3, reflog.** `git worktree remove` takes the worktree's private HEAD reflog with it. Exact test
  (`reflog_orphans`): read `$(git rev-parse --absolute-git-dir)/logs/HEAD`, take fields 1 and 2 of every line, `sort -u`,
  keep only objects that exist as commits (`cat-file --batch-check='%(objecttype) %(objectname)'`), then
  `git rev-list --stdin --max-count=1 --not --all`. Any output means KEEP (`HEAD reflog holds commits no ref reaches`).
  A missing `logs/HEAD` has nothing to lose. Any git failure, or a kill, keeps (`exit 137` is tested). **Over-keep
  cost:** a rebased, amended or force-pushed worktree has its old tip in the reflog and is kept, though the work may
  be on the remote under a new sha. A commit reachable from any branch, tag or remote ref is not an orphan.
- **P3, bare repo with a symlinked `objects`.** The nested-repo `find` matched `-type d -iname objects`; it now matches
  `\( -type d -o -type l \)`, so a `git clone --shared` style store is kept.

**Tests re-placed or reversed, and why.** The round-5/6 tests encoded the old contract. 27 tests failed on the first
run of the new script and none was edited to fit the code; each was judged on its own: tests that isolate ONE keep
rule (nested repo, `.env`, bare layout, per-worktree refs, ...) put their files under `dist/` so the new
"not proven regenerable" rule cannot be the one that fires; the package-tree secret-name exemption tests and the old
"unlisted names are removed" test were reversed to assert KEEP. The header test is unchanged (the header was
shortened to fit its 10-line window).

New tests: the allowlist (every component, symlink, symlinked parent, case, lookalikes, one unproven file among
regenerable ones), secret names under `dist/`, the reflog (orphan after reset, amend, tag, other branch, absent
object, no reflog, three git failures, kill 137, unreadable log), the compare-and-delete branch (moved branch, failed
`update-ref`, config section removed, none present, failed cleanup), the symlinked `objects`, a tracked `.env`
symlink to an ignored file, a unique file under an uninitialized submodule, and a scan file that becomes unwritable
midway.

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
   (Round 6: files under an UNinitialized gitlink directory are now kept.)
4. ~~**Other ignored data without a secret name.**~~ CLOSED in round 7: the guard keeps unless every ignored or untracked
   path is proven regenerable (allowlist below). PRUNE-NONENV-NAMES is no longer needed.
5. **Temp-list read-back.** A failure to read the temp list after it was written successfully is not handled
   separately; it cannot happen short of the file being deleted under the script.
6. ~~**P1-3, ignored data and secret names: awaiting Matt's decision.**~~ DECIDED and implemented in round 7 (option B).
7. **A forged worktree-list record.** A worktree path that contains a complete fake record (a blank line followed by
   valid keys) passes the round-6 line check. Telling it apart needs `git worktree list -z` (git 2.36+).
8. **Bare-layout breadth.** The bare-repo rule fires on any `objects/` directory beside a `HEAD` file and a `refs/`
   directory, tracked or not. Fail-closed by design.

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

**Round-6 head, the whole script** (242 prune tests; harness `/tmp/mut6.py`, the 124 earlier patches re-targeted where
round 6 changed their text, plus mutants for every new branch: `wgit`, the gitlink loop, the bare-layout `find` and
`case` arm, the per-worktree `for-each-ref`, the `awk` porcelain check, `DRY_RUN`, the removed `worktree prune`). 196
entries, m98 the no-op control: **195 real mutants, 175 killed, 20 survived**, and the control survived as it must.
Three survivors of the first run exposed gaps and got work: the case-folded `objects` spelling and the `bare` porcelain
line each got a test, and one (the `-L` exemption) was a **real data-loss hole**, the dangling `.git` symlink under a
gitlink directory, fixed in the script (P1-2 above) with two tests. All three are killed now. The 20 survivors; none
changes whether a tree is kept or removed:

| id | why it survives |
|---|---|
| m29, m46, m58, m63, m66, m83, m94 | as in the tables above: equivalent or display only |
| m52 | as above: only the printed reason differs |
| n03, n04, n06 | `ls-files -s`, `ls-files -o` and `for-each-ref` bypass `wgit`: `core.fsmonitor` only changes the index-versus-worktree comparison (`status`), and a stale hook was measured not to hide anything from these three. `status` bypassing `wgit` (n05) is killed. `wgit` stays on all of them for uniformity |
| n10 | gitlink loop loses its empty-line guard: an empty `rel` is the worktree root, whose `.git` exists, so the next line already skips it |
| n11 | gitlink `-d` check dropped: a deleted gitlink directory is dirty (`status` keeps), and a gitlink that is a file lists nothing |
| n15 | gitlink `find` loses `-maxdepth 1`: only the first entry decides "non-empty", deeper entries add nothing |
| n16 | gitlink `find -print0` becomes `-print`: the result is tested with `[ -s file ]`, never parsed |
| n20 | gitlink `find` failure loses its `return 0`: the nested-repo `find` that runs later walks the same unreadable directory and fails the same way, so the tree is still kept (only the printed reason differs) |
| n38 | nested-repo `find` loses `-mindepth 1`: matches only a worktree whose own directory is named `.git` (or `objects` with a bare layout). A false KEEP, fail-closed, contrived |
| n39 | `-prune` dropped: as the round-5 survivor above, a `.git` directory holds no entry named `.git` |
| n49 | per-worktree `for-each-ref` stderr not merged: a failure is caught by the exit code, a warning is not a ref |
| n66 | `awk` prints every unrecognised line instead of the first: `bad` is non-empty in both cases |

**Round-7 head, whole script** (harness kept outside the repo; 130 entries, `noop` the control). First run: 117
killed, 13 survived (the control plus 12 real). Five survivors were real test gaps and got tests (`.cache` and other
cache-style directories are not allowlisted; plain `credentials` and `*.tfstate` under `dist/`; a reflog orphan named
only in the old or only in the new field of a line). Re-run of those five: all killed. **Final: 129 real mutants, 122
killed, 7 survived; the control survived as it must.** The 7, none changes whether a tree is kept or removed:

| id | why it survives |
|---|---|
| regen-no-dir-part | `[ "$rest" != "$2" ] \|\| return 1` removed: a path with no directory part is a root-level file, and a file is never `-d`, so the loop returns 1 anyway: equivalent |
| regen-needs-no-dir | the `-d` test dropped: every ancestor of a path git lists exists as a directory: equivalent |
| regen-symlink-allowed | the `! -L` test dropped: `ls-files -o` never lists below a symlink (it lists the link as one entry with no directory part), so the check is unreachable defence in depth. The symlink tests pass because the link entry itself is not allowlisted |
| sub-e-to-L | the "initialized submodule" test `-e .git` becomes `-f .git`: differs only for an old-style submodule whose `.git` is a directory, which then keeps (over-keeps) instead of failing in `git worktree remove`. Both keep the data |
| reflog-rc-loose | `reflog_orphans` returns only 0 or 1, so `-ne 0` and `-eq 1` agree: equivalent |
| reflog-empty-ids-keeps | `rev-list --stdin --not --all` on empty input prints nothing and exits 0, so the early `return 1` is redundant: equivalent |
| moved-msg-dropped | the mutant turned out to be a no-op (`else :; echo`): a second control, not a real mutant |

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
