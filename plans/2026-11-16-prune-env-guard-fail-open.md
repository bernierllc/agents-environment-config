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

## Round 8 (independent Codex-high pass on `c5d4663`: six reproduced data-loss cases)

The six, each reproduced on `c5d4663`: (1) an allowlisted directory NAME (`dist/customer-database.sqlite`) authorises
deleting any ignored file under it; (2) `update-ref -d` deletes the BRANCH reflog and only the worktree HEAD reflog was
checked; (3) `MERGE_AUTOSTASH` of a clean in-progress `merge --autostash` goes with the admin dir; (4) `config.worktree`
(`extensions.worktreeConfig`) can hold the only copy of a credential; (5) a `.env.local` written between the scan and
`git worktree remove` is deleted; (6) a failed read-back of the scan list prints an error but the caller reads "nothing
found" and deletes (a failed safety read failed OPEN).

### Structural evaluation: quarantine instead of delete (decided BEFORE any round-8 code)

Every round since 5 found the next place the guard trusts something (a name, a list, a log, a window). Question: can
one change make a guard miss recoverable instead of fatal?

**Design.** `git worktree move <wt> $PROJECTS_ROOT/.prune-quarantine/<YYYY-MM-DD>/<repo>--<name>` (one same-volume
`rename`, atomic; git keeps the admin dir, so `HEAD`, its reflog, `config.worktree`, pseudorefs and the checked-out
branch ref with its own reflog all stay intact). Rescan the moved tree with the full guard; any hit moves it back.
Nothing is deleted. A later pass (the same scheduled run, entries whose date is older than `PRUNE_QUARANTINE_DAYS`,
default 7, minimum 1, anything else is an error) re-runs the full guard on the quarantined tree and only then
`git worktree remove`s it and deletes the branch by compare-and-delete. The directory sits outside every worktree glob
(`*` does not match a dot name). Restore is `git worktree move <qpath> <original>` and is printed in the log line.

**What it closes.** 1-6 all become recoverable for the hold: 1, 3, 4 (nothing is deleted by the guard's verdict; the
file, the autostash and `config.worktree` are all still there), 2 (the branch ref and its reflog are not touched until
purge, which re-checks the branch reflog), 5 (a rename is atomic; a writer that still holds the old path fails or lands
in the moved tree, and the purge rescan sees it), 6 (a failed read-back that still lets a tree through now costs a
move, not a deletion). It also shrinks the residual window of the rename-aside-then-delete variant: a process with its
cwd inside the tree (shell, editor, dev server) keeps writing into the renamed tree until the delete; with a hold of
days that process is seen by the purge rescan instead.

**What it does not close.** (a) Disk is not reclaimed for the hold, which is the tool's purpose: with `PRUNE_QUARANTINE_DAYS=7`
a merged worktree's `node_modules` stays 7 days longer (`PRUNE_QUARANTINE_DAYS=1` for a disk emergency). (b) It does
not replace the guard: the purge deletes, so a miss that nobody notices within the hold is lost then. Recoverable means
"noticed within N days", not "never lost". (c) The purge still has the `git worktree remove` status-then-delete gap
(measured 1.19 s at 100k files) against a writer with the quarantined directory open. (d) Branch deletion is deferred
to purge, so a merged branch name lingers for the hold.

**Cost.** One new orchestration step (move, rescan, move back) and one purge selection (path under the quarantine base,
date component older than the cutoff, still a registered worktree of a repo this run scans), about 70 lines, a date
cutoff that needs `date -v` (BSD) or `date -d` (GNU) and purges nothing when neither works. Purge acts only through
`git worktree remove`, which refuses an unregistered path, so a wrong path cannot delete anything git does not own.

**Decision: ADOPT.** The cost is delayed reclaim, which is a tunable; the benefit is that the next unknown guard hole
costs a move instead of the data. It is adopted together with the direct fixes (2-6 are fixed in the guard as well:
the quarantine is the second line, not the excuse for a weaker first one), and case 1 is closed by narrowing the rule,
not by the hold. Open for the operator: the purge runs in the same scheduled run (the existing scheduled job keeps working and
reclaims after the hold) rather than behind a second explicit `--purge` command, which would mean no disk is ever
reclaimed until someone schedules that second command. Flipping it is a five-line gate.

### Round 8 results

**Suites** (real git, stub `gh`, real script under `/bin/bash`): `tests/test_prune_env_guard.py` 334, `tests/test_prune_round8_cases.py`
74 (new), `tests/test_no_maintainer_specifics.py` 3: **411 passed**, none skipped.

**The six cases, old script (`c5d4663`) against new.** Each `test_case<N>_` test in `tests/test_prune_round8_cases.py` was
run against the `c5d4663` script (34 of the 37 `test_case*` tests fail there; the 3 that pass are the controls: a
worktree with nothing to protect still goes, a clean `COMMIT_EDITMSG`/`FETCH_HEAD` admin dir still goes, a shim that
never fires still goes) and against the new script (all pass).

| case | old script, `c5d4663` | new script |
|---|---|---|
| 1 `dist/customer-database.sqlite` (also build, coverage, .next, .turbo, out, `node_modules`) | `would`/`removed`: the directory name authorises the delete | `keep ... not proven regenerable`; a marker (`.package-lock.json`, `pyvenv.cfg`, `CACHEDIR.TAG`, a `.pyc` beside its `.py`) proves only its own tree |
| 2 commit only the BRANCH reflog (or `ORIG_HEAD`) names | `would`/`removed`; the commit is unreachable after `update-ref -d` | `keep: a reflog holds commits no ref reaches (reflogs, ORIG_HEAD or FETCH_HEAD)`; an unreadable branch log is a fault keep, exit 1 |
| 3 `MERGE_AUTOSTASH` (and any admin-dir file git does not create for a clean worktree) | `would`/`removed`: the stash goes with the admin dir | `keep: its git directory holds MERGE_AUTOSTASH ...` |
| 4 `config.worktree` | `would`/`removed`: the credential goes with the admin dir | `keep: its git directory holds config.worktree` |
| 5 `.env.local` written between the scan and the move/remove | deleted by `git worktree remove` | rename first (quarantine), rescan, hit moves it back (`moved back after the move`); the same at the purge (`moved back after the rescan`) |
| 6 scan list that cannot be read back (index, ignored, admin dir, nested repo, submodule directory) | `would`/`removed`: "nothing found" | `keep ... could not read back ...`, exit 1, "at least one check could not complete" |

Case 6 is portable: the lists are made in a private directory through a template-based `mktemp` shim and deleted after the
named `git`/`find` call, so no macOS `lsof` and no platform `TMPDIR` rules are involved. Case 5 is a `git` shim that
writes the file just before the first `worktree move|remove`.

**What changed in the guard.** Regenerable is a marker rule, not a name rule (round 7's name allowlist is gone). The
admin-dir allowlist is `HEAD ORIG_HEAD FETCH_HEAD AUTO_MERGE COMMIT_EDITMSG commondir gitdir index logs/HEAD`; any other
non-directory file there keeps (this includes everything under `modules/`, so the submodule carve-out in the nested-repo
scan is removed). `reflog_orphans` also reads the branch reflog in the primary's git dir and keeps reftable repositories.
Every list read-back is checked (`exec 3<"$list" || return 2`), and every failed safety read is a fault keep: exit 1,
logged with context, never a delete. A real run quarantines, a later run past `PRUNE_QUARANTINE_DAYS` purges
(full guard, rename aside, rescan, `git worktree remove`, then compare-and-delete of the branch).

**Reversed tests (they pinned the old behaviour), with the reason.**

- Immediate-removal tests (`verdict(dry=False)` expected `removed` from the first run): a real run now quarantines; the
  fixture's `verdict()` follows it with the aged purge run, so they still assert the end state.
- Name-allowlist tests (`dist`, `build`, `.next`, `coverage`, ... removable by name): reversed to the marker rules; the
  name alone now keeps (case 1).
- The locked-worktree "refused removal" test: a locked worktree is now a policy keep at the move; new tests cover a
  refused move and a refused purge removal.
- The initialized-submodule `FAILED` tests: now a policy keep through `modules/` in the admin dir.
- The submodule-skip nested-repo tests: the carve-out is gone, the tree keeps.
- Reflog wording, and the `mktemp`/`rm`/`find` shim adaptations (a second `mktemp` is the scan list, not the script's own
  file).
- `_admin_dir` in the round-6 admin-dir tests uses `FETCH_HEAD` as the file git leaves behind.

**Over-keep costs (what the stricter rules hold back).** A worktree with an unmarked `dist/`, `build/`, `coverage/`,
`.next/` or `.turbo/` is kept whole until someone clears that directory: this is the price of case 1, and the open
decision below (strict, or a per-repo opt-in list). Any unknown ignored file keeps. Any extra admin-dir file keeps
(`MERGE_MSG`, bisect state, `modules/`, `config.worktree`). A merged worktree's disk stays for `PRUNE_QUARANTINE_DAYS`
(7 by default; 1 for a disk emergency) before it is reclaimed. A reftable repository keeps every worktree.

**Standing helper rule (traffic cop, 2026-11-18): the unattended purge deletes only through `git worktree remove` on a
registered path.** The script's only deleting commands are that call (on the `.purge` path git registered with its own
`worktree move`) and `rm -f` of its own temp files. `test_the_unattended_purge_deletes_only_through_git_worktree_remove_on_a_registered_path`
logs every `rm`/`rmdir`/`unlink`/`mv`/`find`/`git worktree` call of a quarantine plus purge and asserts it; a mutant adding
`rm -rf` after the remove is killed (118 mutants: 111 killed, 7 equivalent). Decisions (1) and (2) below: strict and
same-run purge stay as built, per the cop's recommendation.

**Decisions (Program Cop, 2026-11-19 01:29Z; binding for round 8).**

1. **Strict.** A `dist`, `build`, `.next`, `.turbo` or `coverage` directory with no marker keeps its worktree. There is no per-repo
   opt-in list: a list a PR can change is a trust input, so nothing vouches for a directory by name. Reclaiming build output
   is a separate piece of work and is not part of #165.
2. **Purge in the same scheduled run, after the hold.** `PRUNE_QUARANTINE_DAYS` defaults to 7 and must be a whole number of at
   least 1; anything else exits 1 before the script touches anything.

**Conditions.**

- **(a) The purge re-runs the FULL guard on every quarantined entry at purge time, and fails closed.** `purge_one` calls
  `keep_reason` on the held path, then again on the `.purge` path after the rename, and a fault at either keeps the tree
  (`test_the_purge_runs_the_full_guard_again_on_the_held_tree`, `test_a_dry_run_purge_runs_the_whole_guard_before_it_says_would_purge`,
  and the refused-rename and rescan-hit tests). The guard result from the quarantine run is never reused.
- **(b) The scheduled prune job stays disabled until the operator pulls this change; re-enabling it is the operator's.** Nothing in this
  branch loads, enables or edits a scheduled job, and no run of the script may start before the operator has this version.
- **(c) "Recoverable" means "noticed within N days", and the purge still deletes.** A quarantined worktree can be restored with
  `git worktree move` for `PRUNE_QUARANTINE_DAYS` days (7 by default). Nobody is told when something is quarantined, so a
  file nobody notices missing in that window is deleted by the purge, for good, once the guard passes. Quarantine narrows
  the window in which a wrong verdict costs data; it does not make a wrong verdict free.

## Coverage audit (b) of `c5d4663` (aec cop; folded into round 8, no extra round)

The aec cop mutated `c5d4663` (115 single-line mutants, one full suite each): 16 survived, 13 safety-weakening. Each
pattern is pinned below against the round-8 design; every new test fails on the `c5d4663` script or on the mutant
(old = `git show c5d4663:scripts/prune-merged-worktrees.sh`, run against the new tests). Tests are `test_audit<n>_*` in
`tests/test_prune_round8_cases.py`.

| # | audit item | test(s) | on `c5d4663` | mutant of the new script |
|---|---|---|---|---|
| 1 | listed path swapped file→dir, dir→file, dir→symlink (first, middle, last component) after git listed it | `test_audit1_*` (a stale-listing `git` shim over an already-swapped tree: the quarantine rescan would rescue a real swap, so the swap is simulated deterministically) | fail | `reg-no-dir-part`, `reg-dir-symlink`, and `! -L "$1/$acc"` with a trailing slash: killed |
| 2 | cached-prefix boundary (`dist/` vs `dist2/`) for venv, node_modules and CACHEDIR kinds | `test_audit2_*` | pass (the cached prefix keeps its slash there) | `regen_ok="${acc%/}"`: killed |
| 3 | secret names inside regenerable directories (3 kinds x 21 names) | `test_audit3_*` | pass | one mutant per alternative of every secret case arm: 19 of 19 killed |
| 4 | nested `.git` that is a symlink (to another repo's `.git`, or dangling) or a gitfile, inside a regenerable tree | `test_audit4_*` | fail | `-type d -iname .git`: killed |
| 5 | reflog check whose enclosing subshell is killed (137), for the HEAD log, ORIG_HEAD and the branch log, killing the ids subshell or the function's own | `test_audit5_*` (a `sort` shim kills the process) | fail | `-ge`, `-ne 2`, the ids status check dropped, and each of the three log sources dropped: killed |
| 6 | tracked gitlink whose name ends in whitespace (`sub\n`, `sub `, `sub<TAB>`) | `test_audit6_*` | pass | `read` without `IFS=`: killed |
| 7 | discovery: real `rev-parse --git-dir` / `worktree list --porcelain` prints a valid answer, then exits 137 | `test_audit7_*` | fail | each `|| { skip; note_fault; continue; }` dropped: killed |
| 8 | vacuous tests | see below | n/a | n/a |
| 9 | fsmonitor | `test_audit9_*` | fail on the call count only (`c5d4663` already used the flag on every call but has no rescan or purge scans); the flag itself is pinned by the mutants | `=true` and the flag dropped: killed |

**Item 8, vacuous tests fixed** (in `tests/test_prune_env_guard.py`): the two discovery-failure tests now also assert the
fault line, exit 1 and nothing held, and run a print-then-die git as well as a silent one; `test_clean_sweep_prints_no_skip_lines` and `test_scan_leaves_no_temp_file_behind`
now carry a real-removal control (the worktree line is `quarantined`; the scratch-dir test also runs the purge and sees
`removed`); the symlink-leaf and below-symlink allowlist tests now reach the symlink predicate (git never lists a path
through a link, so they use the stale listing, and the link points at a marked directory holding unique data, so only
the symlink test stops the marker from vouching); the blind-spot test now ends in `fx.keeps(KEEP_SUB)`, so it invokes
the script.

**Item 9, fsmonitor.** A native fsmonitor daemon cannot be made to miss an event on demand, so a stale-state test would
be non-deterministic. The substitute is deterministic: a logging `git` shim over a full quarantine-and-purge run asserts
that every `status`, `ls-files` and `diff` call carries `-c core.fsmonitor=false`. The hook-based staleness test from
round 8 still covers the hook form.

### The 13 P1 survivors: end state per item (Program Cop directive, 01:54Z)

Each ends in (a) a named test that fails against the audit's mutant, or (b) moot because round 8 removed the code path.
Mutants are the audit's, translated line-for-line to the new script (`/tmp/mutate_final.py`); each was run against the
named test(s) and failed. Re-grading closed none of them.

| # | audit mutant | state | test that fails against it, or the rule that removed the path |
|---|---|---|---|
| 1 | `regen-cache-boundary` (`"${regen_ok%/}"*`) | (a) | `test_audit2_a_proven_directory_does_not_vouch_for_a_sibling_that_shares_its_name_as_a_prefix` |
| 2 | `regen-no-directory` (no directory-part check) | (a) | `test_audit1_a_file_git_listed_that_is_now_a_directory_with_data_keeps[marked]` (and `[unmarked]`) |
| 3 | `regen-symlink` (no symlink check on a directory) | (a) | `test_audit1_a_directory_swapped_for_a_symlink_to_ignored_data_after_the_listing_keeps[dist]`, plus the two rewritten symlink-allowlist tests, each of which fails alone |
| 4 | `regen-real-directory` (`-d` half of the directory test) | (b) | the strict marker rule: an exemption needs a marker file *inside* the directory (`pyvenv.cfg`, `CACHEDIR.TAG` with its signature, `.package-lock.json`/`.yarn-integrity`/`.modules.yaml`/`.pnpm`), which a non-directory cannot hold. The `-d` test was removed from `regenerable()` in this round, so the mutant has no line to change |
| 5 | `reflog-exact-one` (`-ne 0` for the reflog verdict) | (a) | `test_audit5_a_reflog_check_killed_part_way_keeps_and_faults[head-ids]` |
| 6 | `read-ifs` (`read` without `IFS=`) | (a) | `test_audit6_a_tracked_gitlink_whose_name_ends_in_whitespace_is_not_trimmed[trailing-newline]` |
| 7 | `repo-revparse` (`continue` dropped) | (a) | `test_audit7_discovery_that_printed_valid_output_and_then_died_skips_the_repo[rev-parse]` and `test_failing_worktree_discovery_skips_the_repo_with_a_reason[prints-then-dies]` |
| 8 | `repo-list` (`continue` dropped) | (a) | `test_audit7_..._skips_the_repo[worktree-list]` and `test_failing_worktree_list_skips_the_repo_with_a_reason[prints-then-dies]` |
| 9 | `nested-git-symlink` | (a) | `test_audit4_a_nested_dot_git_that_is_not_a_directory_inside_a_regenerable_tree_keeps[symlink...]` |
| 10-13 | `regen-secret-exempt-*` (four secret-name arms exempted when inside a regenerable directory; the same observable behaviour as deleting an alternative from its arm) | (a) | `test_audit3_a_secret_named_file_inside_a_regenerable_directory_keeps[...]`: one mutant per alternative of every secret arm, 19 of 19 killed, covering all four |

**Weak tests now kill their mutant by themselves** (each run alone against the mutant; the empty script also fails all six):

| test | mutant it kills alone |
|---|---|
| `test_failing_worktree_discovery_skips_the_repo_with_a_reason[prints-then-dies]` | `rev-parse` skip without `continue`. The test used a git that prints nothing and fails, so the later `[ "$gd" = .git ] \|\| continue` supplied the keep; it now also runs a git that prints its valid answer and exits 137 |
| `test_failing_worktree_list_skips_the_repo_with_a_reason[prints-then-dies]` | `worktree list` skip without `continue`, same reason |
| `test_an_allowlisted_name_that_is_a_symlink_is_not_allowlisted` | symlink check on the directory removed (stale listing over a symlink to a marked directory holding unique data) |
| `test_an_allowlisted_directory_below_a_symlinked_one_is_not_allowlisted` | same mutant, symlink below the listed directory |
| `test_scan_leaves_no_temp_file_behind[dry\|real]` | `rm -f "$list"` dropped. It used `TMPDIR`, which BSD `mktemp` ignores without a template, so it watched nothing on macOS; a `mktemp` shim now sends every temp file to the scratch dir and the test asserts the shim was used |
| `test_clean_sweep_prints_no_skip_lines` | `[ -e "$gitdir" ] \|\| continue` dropped (the unmatched glob is then treated as a repo) |

**Item 9, fsmonitor: a test, no Tracker row.** `test_audit9_*` kills both the `=true` and the flag-dropped mutants.

**Surviving mutants after the final pass (all P3, none touches data safety).**

| mutant | why it survives |
|---|---|
| `regen-cache-remove` (the `regen_ok` lookup dropped) | the cache only skips re-running the same checks for a path under an already-proven directory; the verdict is identical, only slower |
| `gh-merged` (`\|\| true` on the merged-PR lookup) | `pr_heads` prints its reason and returns before it prints any `branch sha` line, so `merged` is empty either way and no candidate passes the non-empty-SHA guard; the mutant costs at most one extra open-PR request |
| `-prune` dropped from the nested-`.git` `find` | the nested `.git` entry itself is printed first and keeps the tree; descending only adds later hits for the same verdict |
| the `-d` half of the directory test | removed from the script (row 4), so there is nothing to mutate |

## Round 9 (independent Codex-high review of `5a8f894`: 2 P0 + 2 P1, all reproduced; no gate waived)

Five rounds of my own tests and 118 of my own mutants missed all four, because the tests encoded my model of the
guard. **How round 9 avoids that: the reviewer's own repros are permanent tests** (`tests/test_prune_round9_cases.py`,
`test_p0_*`, `test_p1_*`, copied from `/tmp/review-A-5a8f894-findings.md`), each ran against the pre-fix script first
(**20 failed, 4 passed**; the 4 are controls), and the P0-2 test injects the write in the real window with a `git` shim
that fires on the rename, not by simulating the outcome. A finding is closed only when its repro fails before and
passes after.

| finding | what was wrong | how it is closed |
|---|---|---|
| P0-1 a marker authorised everything beneath it | `.package-lock.json` / `pyvenv.cfg` / `CACHEDIR.TAG` made every ignored file under that directory "regenerable", so `node_modules/customers.sqlite` went | A marker says which TOOL owns the directory; each file under it must be proven by that tool's own records. **venv:** a scaffold regex (`pyvenv.cfg`, `.gitignore`, `CACHEDIR.TAG`, `lib64`, `bin/*`, anchored) plus the files each `*/site-packages/*.dist-info/RECORD` lists (a path that climbs out of the worktree, or an absolute one, proves nothing; an unreadable RECORD keeps and faults). **npm:** the package directories `.package-lock.json` lists, plus `.package-lock.json` and `.bin/*` (marker only counts for a directory named `node_modules`). **cache:** the standard `CACHEDIR.TAG` signature line proves the directory, spec-based. **yarn / pnpm trees keep** (`.yarn-integrity`, `.modules.yaml`, `.pnpm` list no package files). A `__pycache__` `.pyc` is proven if its `.py` is beside it or is itself a claim. Secret-name arms still run first. Anything unproven blocks and is named in the keep line. The old blanket-rule test is replaced (said so in the commit message) and every other test that put arbitrary files under a marker was reviewed |
| P0-2 write between the final rescan and `git worktree remove` | A rename cannot stop a process that already holds the directory | **Structural choice, and it is not a full close.** After the rescan the purge runs `holder_scan` (`lsof -n -P -w -F pc +D <realpath>`): any process with a cwd or open file inside refuses the delete. `lsof` missing, failing, or printing to stderr is a fault keep, never "no holder". Residuals: a process owned by another user that `lsof` cannot see; the gap between `lsof` returning and `git worktree remove` starting; platforms whose `lsof` hides processes. **So deletion ships OFF by default**: the scheduled run quarantines and rescans, and only deletes when `PRUNE_ALLOW_DELETE` is exactly `1` (unset, `0`, `true`, empty: all keep, `unattended deletion is off`). Product consequence for the operator: with the scheduled job as is, disk is NOT reclaimed until the variable is set |
| P1-3 `FETCH_HEAD` treated as disposable | After `git fetch <url> <ref>` the fetched commits are reachable only from `FETCH_HEAD` | `reflog_orphans` now feeds the `FETCH_HEAD` object ids through the same `rev-list --not --all` check as the reflogs and `ORIG_HEAD`; a dangling `FETCH_HEAD` symlink or an unreadable file is a fault keep |
| P1-4 clean per the stat cache, dirty in content | `git status` trusts size+mtime, so a same-size edit with the mtime restored reads clean | `status --porcelain -uall` runs against a throwaway index built from `HEAD` (`GIT_INDEX_FILE=$list.idx git read-tree HEAD`), so every file is compared by content; a failing `read-tree` is a fault keep; the throwaway index is removed with the other temp files |

**Decisions worth a second look.** The cache marker is spec-based (trusts the signature line). npm proof is
package-granular, not file-granular (a stray file inside a listed package directory is not seen). yarn and pnpm trees
keep, which over-keeps. A venv with pip installed keeps because `pip/_vendor/certifi/cacert.pem` matches the `*.pem`
secret arm (pre-existing, fail-closed). One redundant guard is kept on purpose (the flag arm). One dead check in
`proof_venv` (a RECORD path outside the worktree compared against the root) was removed: claims only ever lie under the
root, and the mutant that removed it was equivalent.

**Round 9 results.** Suite: **547 tests** (`test_prune_env_guard.py`, `test_prune_round8_cases.py`,
`test_prune_round9_cases.py`, `test_no_maintainer_specifics.py`), final run: 547 passed, none skipped. Mutation, harness
outside the repo, one edit per mutant, `-x`: **37 mutants over the new code (marker proofs, holder scan and the
deletion gate, `FETCH_HEAD`, the throwaway index), 37 killed.** The first run had 13 survivors: 12 were real test gaps
(top-level-only scaffold names, a `lsof` stand-in that never exercised `command -v`, the absolute RECORD path, the
symlinked marker, an unreadable RECORD, a failing `read-tree`) and got tests; one was an equivalent dead check, deleted
from the script together with its mutant. The round-8 audit mutants (38) re-run on the new script: **32 killed, 6 not**:
four (`reg-dir-symlink`, `reg-dir-half-d`, `reg-cache-no-slash`, `reg-cache-drop`) target code round 9 removed
(`BAD-PATTERN`, nothing to mutate), `reg-no-dir-part` is now equivalent for the verdict (a swapped-in directory is kept by
the per-file proof anyway), and `nested-git-no-prune` stays equivalent as in rounds 5-8.

**Who turns deletion on.** Enabling unattended deletion (setting `PRUNE_ALLOW_DELETE` to exactly `1` on a real machine) and re-enabling the scheduled job are the operator's decision, never an agent's or a CI job's.

### Round 9 addendum 1 (independent Review B, Sonnet high, on `5a8f894`)

Review B reproduced both Review A defects without seeing it. Its **P2-1** is the marker-authorises-everything-beneath
problem (ignore `node_modules/`, add `node_modules/.package-lock.json`, put `node_modules/pkg/my.sqlite` and
`node_modules/notes.txt` under it: both were quarantined and later purged) and its **P2-2** is the post-rescan writer race
(a `git` wrapper writes `.env.late` into the `.purge` tree just before `git worktree remove`). Review B graded them P2;
that grade is not ours to change and Review A's P0 grade stands. Both repros are permanent tests
(`test_p2_1_an_npm_marker_that_lists_no_package_authorizes_nothing_beneath_it`, `test_p2_2_*`) and are closed by the P0-1 and P0-2 fixes above, unchanged. P2-2 stays
the documented residual: the default test (deletion off) passes, and the same race with `PRUNE_ALLOW_DELETE=1` is pinned
as a **strict xfail**, so closing the gap later fails the suite until the xfail is removed.

| finding | what was wrong | how it is closed |
|---|---|---|
| P2-3 a worktree outside `$PROJECTS_ROOT` was quarantined | the discovery loop trusted any path `git worktree list` printed | `RROOT` is the root's real path (`pwd -P`); `under_root` accepts a path only when its real path is strictly below it (`"$RROOT"/?*`, so `/projects2` is not `/projects`). The discovery loop refuses and reports (`keep ... outside <root>`, a policy keep, exit 0). Tests: `../` and sibling-prefix forms, a worktree directory that is a symlink out, a root given as a symlink or with `..`. The quarantine base and the run's directory are checked the same way before anything is moved, and the base is checked **before** the run directory is created, so a `.prune-quarantine` symlink out of the root makes no directory out there (`FAILED`, fault, exit 1) |
| P3-1 the hold was calendar-day granular | `PRUNE_QUARANTINE_DAYS=1` purged an entry quarantined at 23:59 about a minute later | the quarantine directory is a UTC instant, `YYYY-MM-DDTHHMMSSZ`, and the cutoff is the same format for now minus DAYS; they are compared as fixed-width strings, so DAYS is a true minimum and "noticed within N days" is accurate. Test: an entry made 23h59m ago stays and one made 24h01m ago goes with DAYS=1. **Replaced tests:** every existing test that built or read a `YYYY-MM-DD` directory now uses the stamp. **No legacy support:** a date-only directory is kept and faults with a rename hint (`not a UTC timestamp`); nothing in the field can hold one, since deletion has never run unattended |
| P3-2 `delete_branch` could delete `staging` | a linked worktree on `staging` at a merged promotion head was removed and its branch deleted | `long_lived` (`main`, `master`, `staging`, `develop`, every remote's HEAD branch) is checked first in `delete_branch`: the branch is kept (`kept    branch ... long-lived`), the worktree removal still follows the guard. A `for-each-ref` that fails keeps the branch. Tests per name plus a remote HEAD branch (`trunk`) and the failing-`for-each-ref` shim |
| P3-3 `gh pr list --limit 1000` truncated silently | a repo with 1000 open PRs could hide the PR that reuses a branch name | `PR_LIMIT=1000`; an open list whose count reaches it is unverifiable: the repo is skipped with exit 1. The merged list is exempt: a full page only hides candidates, and a worktree absent from it is kept anyway. Tests: exactly the limit (skip), one below (trusted), merged at the limit (not a skip) |

**Addendum results.** Suite: **569 prune tests** (the four prune/maintainer test files, all passing; the full `tests/` run also passed except two timing-sensitive signal tests in `test_cleanup_hung_processes_script.py` that pass alone and are unrelated). Mutation: **18 mutants over the new code
(limit check, `-le`, applying it to the merged list; the long-lived guard, `staging`, the remote HEAD list, an unreadable
list; date granularity, local time, a non-stamp accepted, an unnoted cutoff fault; a text-prefix root, an always-true
root check, logical (non-`pwd -P`) paths for the path and for the root, the discovery check, the quarantine-base check,
the stamp-directory check), 18 killed; the 37 round-9 mutants re-run on this script: 55 of 55 killed.** The first run had two survivors, both real test gaps: an unreadable remote-HEAD
list (the guard fell open) and a stamp-directory symlink; both got tests and are killed.

### Round 9 addendum 2 (Program Cop mutation audit on `5a8f894`: 276 mutants, 52 survived, tests only)

No script change. The audit's 43 gap tests (`tests/test_prune_mutation_gaps.py`, now 45 with two of ours) kill 41 of the 52
survivors; the other 11 are equivalent or P3. They pass on the `502c06e` script (run in a temp copy with the date-only
directory name) and on round 9.

- **Systemic gap closed.** `Fixture.run` asserted exit 1 only when the fault line was printed, so a dropped `note_fault`
  (exit 0, no fault line) passed. `run(..., expect_fault=True)` now asserts exit 1 and the fault line together, `False`
  asserts exit 0 and no fault line; `purge_run` and `_purged` pass it through. Every fault-pinning gap test uses it. The
  older fault tests already asserted `last_rc == 1` themselves and are unchanged.
- **Drop-every-`note_fault` audit (ours).** One mutant per call site (25): two survived and got tests, so all 25 are killed.
  `mkdir -p "$dir"` failing (the stamp directory cannot be made) and a held tree whose move-back fails (a holder is a policy
  keep, so only the failed move can raise the fault; the first version used a failing lsof, which raised it at an earlier
  line and left the mutant alive).
- **Adapted, not copied** (intent kept, premise updated to round 9): `test_unproven_file_after_a_marked_directory_still_keeps`
  (`_marked` is a cache marker, the one kind that proves a whole directory, so only the prefix test can keep `zz/`);
  `test_glob_characters_in_the_cached_prefix_are_literal` (a venv marker proves only recorded files, so a mis-matched
  `ab/data.db` kept the tree either way and the mutant lived; a cache marker makes the literal match the only thing that
  keeps it); `test_a_file_written_just_before_the_remove_is_not_deleted` (the P0-2 window: pins git's refusal of a
  non-ignored late file; an ignored late file is the strict xfail in `test_p2_2_*`). `test_purge_guard_failure_keeps_and_faults`
  also moved from the `2000-01-01` directory to the stamp.
- **Kept as the audit wrote them:** the ORIG_HEAD removal in the no-reflogs test, the private-directory `mktemp` shim, the
  `' M injected'` policy keep with a failing move-back.
- **Results.** Prune tests: **610 passed, 1 xfailed** (full `tests/`: 4062 passed, the two signal tests in
  `test_cleanup_hung_processes_script.py` fail under load and pass alone, 22/22). Mutants: the 55 round-9 and addendum-1
  mutants plus two for the adapted tests, **57 of 57 killed** on the combined suite, plus the 25 `note_fault` mutants,
  25 of 25 killed.

## Round 10 (two independent reviews of `ef1e812`: 1 P0, 3 P1, four P2s; every one reproduced, no gate waived)

Inputs: a Codex-high review (1 P0, 2 P1) and a Sonnet review (the fourth P1 and the P2s). Each item below has a
failing-first test in `tests/test_prune_round10_cases.py` that fails on `ef1e812` and passes on the fix. Round 10, so
the direction is to delete less and prove more: where a proof cannot be made file by file, the reclaim is dropped.

### P0: a marker proved a tool, never a file

`ef1e812` let an installation record authorize deletion of everything it named, or (npm) everything beneath a named
package directory. A record identifies where a file was installed, not what is in it now.

- **(a) venv, fixed per file.** `VENV_VERIFIER` (`python3 -I`, one run over every `site-packages/*.dist-info/RECORD`)
  prints a file only when it is a regular file, not a symlink (`O_NOFOLLOW`), whose **sha256 and size both equal** the
  RECORD entry. A missing or non-sha256 hash, a missing size, a mismatch, an unreadable file, or a path leaving the
  worktree proves nothing and the file keeps the tree. The RECORD itself has no hash by design (pip) and is printed as
  read. A `.pyc` is proven only when its `.py` source is itself a claim. The venv scaffold files (`pyvenv.cfg`,
  `bin/activate*`, `bin/python*`, `lib64`, `.gitignore`, `CACHEDIR.TAG`) stay allowlisted by name: venv creation writes
  them and nothing hashes them. The reviewer's repro B (a real, non-matching hash) is the test; it uses real hashes, not
  the empty ones the round-9 control used.
- **(b) npm, reclaim removed.** `node_modules/.package-lock.json` lists packages, not files: no per-file hash exists, so
  nothing under a package directory is provably an installed file (reproduced: `node_modules/pkg/customers.sqlite`).
  Decision: an npm tree is kept. **The npm reclaim is now a no-op; a worktree with a `node_modules` tree is quarantined
  never, until a tool that records file hashes exists to prove it.** This costs the disk reclaim the script used to get
  from `node_modules`; that reclaim was the unsound part, and deleting less is the trade the brief names.
- **(c) CACHEDIR.TAG, same decision.** The tag says "a tool calls this a cache" and nothing about any file in it
  (reproduced: a dataset in a directory somebody tagged). Per marker the rule is: **keep unless there is file-level
  proof.** `.pytest_cache`, `.mypy_cache` and `target` trees are therefore kept too. Only the venv marker has file-level
  proof, so only it remains.
- Everything unproven fails closed. `PRUNE_ALLOW_DELETE` is untouched: default off, exactly `1` enables.
- Dependency: the venv proof needs `python3`. If it cannot run, or a RECORD cannot be read, the result is a fault keep
  (exit 1, "could not read the venv RECORD files"), never a pass.

### P1: staged-only work behind a clean fresh index

The throwaway index built from HEAD (round 9) correctly ignores stat caches but replaces the real index, so staged
content with the working copy restored to HEAD's read as clean (`MM` in real git). `keep_reason_scan` now also runs
`git diff-index --cached --quiet HEAD` against the real index (exit 1 keeps: "the index holds staged changes"; any
other failure is a fault keep). It reads no file, so no stat cache is trusted. It runs in the pre-move and post-move
guards, which both go through `keep_reason`.

### P1: the first move ran no holder check

`quarantine_one` now runs `holder_scan` before it creates the quarantine directory or moves anything. A holder keeps
the tree in place ("nothing was moved"); a failed or missing `lsof` is a fault keep. **Honest residual race:** a process
that starts, or chdirs into the tree, after this scan and before the rename is not seen, and the post-move rescan only
sees one that has already written. The rename is atomic and reversible (the tree is moved back on any later hit), so
the worst case is a live process finding its cwd renamed to a path in the quarantine, not data lost.

### P1: `delete_branch` could unborn another worktree

`checked_out_at` (a `git worktree list --porcelain -z` read) now gates `delete_branch`: a branch some other worktree has
checked out is kept and reported; a list failure keeps the branch and records a fault. The sha compare-and-swap
(`update-ref -d <ref> <sha>`) stays. Residual race: a checkout made between the list and the `update-ref` is not
closed, `update-ref` has no check to lean on.

### P2s

- **`-z` worktree parsing.** The main loop and `checked_out_at` read `git worktree list --porcelain -z` with NUL-delimited
  reads into arrays, so a newline in a path can never forge a `branch` field and a TAB path is a worktree like any other
  (it produces a keep or quarantine line, it does not vanish). This replaces the round-6 line heuristic and closes
  residual limits 7 and 11 below.
- **Quarantine collision test.** The same-name-same-day collision test is deterministic: it freezes the stamp it
  collides with instead of racing the clock.
- **Relative `PROJECTS_ROOT`.** Refused once at startup with one message ("PROJECTS_ROOT must be an absolute path");
  it changed meaning with the working directory.
- **Nested-repo scan order.** The whole-worktree scan for nested `.git` entries and bare layouts now runs before the
  ignored-file loop, so a nested repo reports as a nested repo (not as an `.env` or an unproven file). The `dir/` case
  inside the loop is kept as a fail-closed branch; it is unreachable in practice because the scan above keeps first.

### Kept as a residual (not fixed)

`long_lived` reads `refs/remotes/*/HEAD` to learn each remote's default branch; a clone with that ref missing is not
protected by it. The branch is still protected by name (`main`, `master`, `staging`, ...) and by `delete_branch`'s
other checks. Left as a one-line residual: fixing it means a network call or a heuristic, neither of which the guard
should make.

### Round 10 results

- `tests/test_prune_round10_cases.py`: 33 tests; against `ef1e812` 28 fail and 5 pass. The 5 are the two positive
  controls (a fully matching RECORD still goes; a branch with no other checkout still goes), the stamp test (its fix is
  in the test), and the two neighbouring-venv tests added after the mutation run (they guard mutants, not a review finding).
- Round-8 and round-9 tests that treated npm or `CACHEDIR.TAG` trees as removable were flipped to expect a keep, or
  moved to a venv whose RECORD proves the file; none was weakened to pass.
- Mutation run on the Round 10 script: 23 new mutants over the per-file proof, the index check, the first-move holder
  scan, the checkout refusal, `-z` parsing, the absolute-root check and the scan order, plus every still-applicable
  mutant from earlier rounds: 81 patterns, 12 no longer apply (the code they mutated is gone), **67 of 69 killed**.
  The two survivors: `r10-unreachable-dir-entry` (the unreachable fail-closed branch above: equivalent by design) and
  `p01-dir-symlink-below-marker` (a symlinked directory below a marker is also not followed by `find`, so no RECORD is
  ever found through it: the symlink test is a second line of defence, not the only one). Two earlier survivors were
  killed by the neighbouring-venv tests.

## Residual limits (documented, not solved)

1. **A link held elsewhere.** An `.env*` symlink held in the primary checkout, in another repo, or in a kept
   worktree, that points through a non-`.env*` target into a worktree this sweep removes, is not seen: the script
   cannot enumerate every link on disk. Example: the primary's `.env -> ../wt/only-copy` loses `only-copy` when
   `wt` is removed. Reproducers t4 9R, t5 17d and t6 from the data-loss hunt (not in the test suite: nothing the
   script can see distinguishes them).
2. ~~**No lock window.**~~ SUPERSEDED in round 8: the tree is renamed (`git worktree move`, one atomic rename) and
   rescanned before anything is deleted; a hit moves it back. What is left is the purge's own `git worktree remove`
   status-then-delete gap against a process whose cwd is inside the quarantined directory (see the round-8 quarantine
   evaluation, "What it does not close" (c)). The original description follows. Nothing locks the worktree between the final scan and the removal, and the removal is not one
   git invocation: `git worktree remove` makes its own `git status` pass before it deletes. Measured with 100k ignored
   files, the gap between the script's scan finishing and the deletion starting is **1.19 s**. A `.env*` file (or
   other protected data) created inside that window is lost. A quarantine-rename was considered and rejected as more
   machinery than the window warrants. An earlier revision of this file and of a script comment said the window was
   "one `git` invocation"; that was wrong.
3. ~~**Submodules.**~~ CHANGED in round 8: the nested-repo scan no longer carves out submodule directories, and the
   admin-dir scan keeps any non-directory file it does not recognise, including everything under `modules/`. A worktree
   with an initialized submodule is therefore a policy keep, not a `FAILED` from `git worktree remove`. (Tests that
   expected `FAILED` for that case were reversed; see the round-8 results.) Round 6: files under an UNinitialized
   gitlink directory are kept.
4. ~~**Other ignored data without a secret name.**~~ CLOSED in round 7: the guard keeps unless every ignored or untracked
   path is proven regenerable (allowlist below). PRUNE-NONENV-NAMES is no longer needed.
5. ~~**Temp-list read-back.**~~ CLOSED in round 8 (case 6): every list is opened with `exec 3<"$list" || return 2`, so
   a failed read-back is a fault keep (exit 1, logged), never "nothing found". Pinned by shim fault injection for the
   four lists (index, ignored, nested, admin), without `lsof`.
6. ~~**P1-3, ignored data and secret names: awaiting the operator's decision.**~~ DECIDED and implemented in round 7 (option B).
7. ~~**A forged worktree-list record.**~~ CLOSED in round 10 (`git worktree list --porcelain -z`). Original: **A forged worktree-list record.** A worktree path that contains a complete fake record (a blank line followed by
   valid keys) passes the round-6 line check. Telling it apart needs `git worktree list -z` (git 2.36+).
8. **Bare-layout breadth.** The bare-repo rule fires on any `objects/` directory beside a `HEAD` file and a `refs/`
   directory, tracked or not. Fail-closed by design.
9. **Lossy `.gitattributes` clean filter** (Review B, no repro of harm). A clean filter that rewrites content can make
   `git status` read a modified file as clean; the content check compares what the filter produces.
10. **Numeric-looking branch names in awk** (Review B, no repro of harm). Branch names are compared in awk and a name
    such as `1e3` could be compared as a number rather than a string; no failing input found.
11. ~~**Newline in a path forging a branch line**~~ CLOSED in round 10 (same fix as item 7). Original: **Newline in a path forging a branch line** (Review B, no repro of harm). A worktree path containing a newline can
    print a line that looks like a `branch` record; the same cause as item 7, fixed by `git worktree list -z`.
12. **`baseRefName` ignored** (Review B, no repro of harm). A PR merged into a branch other than the default still
    counts as merged; the script checks the head commit, not where it landed.

## Affected surfaces

- `scripts/prune-merged-worktrees.sh`: the guard and the discovery loop's failure reporting. Nothing else changed.
- Callers: the scheduled prune (cron or another scheduler) and anyone running the script by hand. It now prints `keep` where
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

**Round-8 head, whole script** (harness kept outside the repo, same method; both new-file tests and the old suite run per
mutant). 117 mutants over the new rules (marker rule, admin-dir allowlist, the three reflog sources, read-back checks,
quarantine and purge, the cutoff). First run: 91 killed, 26 survived. Nineteen survivors were real test gaps and got tests
(`test_prune_round8_cases.py`, "Mutation-run survivors"): the CACHEDIR signature as a prefix, the `node_modules`-only
marker, a symlinked `.pnpm`, `.pyo` and other extensions, a `.pyc` outside `__pycache__`, a dangling `.py` symlink, the
submodule-directory read-back, `logs/*` beyond `logs/HEAD`, a leftover `AUTO_MERGE`, `ORIG_HEAD` and each column of a
reflog line as the only source, a reftable repository, a failed move back, a dangling symlink at the quarantine name,
the full guard on a dry-run purge, a refused rename-aside, and an uncomputable cutoff. Re-run of those 19: all killed.
**Final: 117 mutants, 112 killed, 5 survived** (`reg-no-dir-part` and `reg-dir-symlink` were survivors here and are now killed by the coverage-audit (b) tests below). The 5, none changes whether a tree is kept or removed:

| id | why it survives |
|---|---|
| rl-max-count | `--max-count=1` dropped from `rev-list`: only the volume of the output changes, the `-z` test is the same |
| rl-ids-empty | the early `return 1` on an empty id list dropped: `rev-list --stdin --not --all` with no positive revisions prints nothing: equivalent |
| q-mkdir-fault | a failed `mkdir -p` of the quarantine date directory no longer prints/faults itself: the next `move_wt` into that directory fails with `FAILED` and `note_fault` anyway, same verdict and exit status |
| p-cutoff-empty | an empty cutoff no longer keeps: the empty cutoff only exists when the startup computation already printed its note and called `note_fault`, and `[[ "$d" > "" ]]` is true for any date, so the entry is kept either way |
| p-aside-always | the `.purge` suffix is added even when the entry already ends in `.purge`: it is renamed to `.purge.purge`, rescanned and removed; same outcome |

**Round-9 head:** 37 mutants over the per-file marker proofs, the holder scan, the deletion gate, `FETCH_HEAD` and the
throwaway index, all killed (see Round 9 results above for the first-run survivors and what they became).

## Out of scope

Widening the script's disk reclaim is a separate change owned elsewhere; this fix touches only the guard.
