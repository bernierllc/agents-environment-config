# Trusted replay for merge-with-main promote slices (main-via-staging guard)

> Status: R1 (step 3 provenance, rejection-only) and R2 (trusted replay, `scripts/replay-promote-slice.py`,
> rejection-only) implemented; every merge-with-main slice still fails closed. R3 (hosted evidence) not started.
> Owner of the follow-up: aec (the canonical `main-via-staging.yml` and `scripts/check-main-source.sh`).

## Problem

A downstream repo (a staging-default repo that cuts `promote/*` slices) lands a mid guard for `promote/<YYYY-MM-DD>-<n>` heads. The guard
(`main-via-staging.yml`, `pull_request_target`, a privileged job) cannot run the PR head's code, so
for a promote slice it runs an inline, metadata-only GitHub compare check. It enforces: same-repo
head, a `promote/<date>-<n>` ref, a head SHA on staging's first-parent history, and fail closed on a
truncated compare, an API error, an empty `HEAD_REPO` or a head that merges a staging cut with main.

That last rule is the gap. A slice head that merges main into its staging cut (a merge-with-main
slice) fails closed. Today's escape hatches are both manual: back-merge main into staging with a
merge commit and cut a plain slice, or use a `hotfix/*` branch.

## Correct fix: a trusted replay

The guard runs the BASE ref's script and generator over fetched head objects. It never runs the
head's generator.

Incumbent: a downstream `scripts/check-main-source.sh` already replays with `git merge-tree` and regenerates
manifests. What is missing is trusted execution of that replay, so this plan extends the existing guard and keeps
the detector, Review Gate and merge-time checks. It does not add a parallel mechanism.

1. The trusted-base checkout (already in the guard) supplies the script and the generator from the
   PR base. In `pull_request_target` that checkout is the base ref, which is main in a staging-default repo (see
   Bootstrap).
2. The job fetches the head's git objects only, by the event's immutable head SHA (`github.event.pull_request.head.sha`),
   never by ref name, so a moved head ref cannot change what is evaluated. No checkout of head files into the working
   tree, no execution of anything the head carries.
3. **Provenance first (retained from the downstream validator, not replaced by tree equality).** Tree equality alone
   does not authorize ancestry: a same-repo author could merge a legitimate staging cut with an unrelated commit and
   replay it faithfully. Before the replay the script requires: exactly two parents; the first parent on staging's
   first-parent history; the second parent EQUAL to the event's `base.sha` (the main tip being evaluated), not merely
   an ancestor of main; and no appended commits beyond the merge. A slice built against an older main is stale and
   fails closed: it is rebuilt, never re-evaluated into a pass. Octopus merges, extra parents and non-first-parent
   staging cuts fail closed. Same-repo ownership never authorizes replay inputs. (Departure, stated: the downstream
   validator accepts any main ancestor; this guard is stricter on purpose, because the replay must describe the
   merge that will actually land.)
4. The base script replays the slice from those authorized parents under the trusted generator contract below and
   compares the result to the head's tree by object id.
5. A merge-with-main slice passes only when provenance holds and the replayed result equals the head's tree. Any
   difference, a missing object, a truncated fetch or an API error fails closed.

### Replay tuple and freshness

A pass is valid only for this tuple: head SHA, staging snapshot SHA, main/base SHA (`base.sha`), and the trusted tool
version (the guard's released tag). Two separate jobs, each owned once:

- **The guard owns "the replay describes the merge that lands against this base"**: the second parent must equal
  `base.sha` (Correct fix, step 3). Re-running the same event cannot select a newer main (the event's `base.sha` is
  immutable), so freshness is never obtained by re-evaluation. A stale slice is rebuilt on the new main, which pushes
  a new head and fires a new event with the new `base.sha`. Rebuild means re-cutting the slice from its ORIGINAL
  staging cut with the new main as second parent. The generic `pr-merge-flow` advice for a BEHIND PR (`gh pr
  update-branch`) does not apply to a slice: it would merge main into the existing slice, giving parents
  `(old-slice, new-main)`, whose first parent fails the staging-first-parent rule. The slice exception is stated
  in the downstream handoff and as a docs-only note in `pr-merge-flow` (no hook change) when this plan ships.
- **The server owns "the base did not move between evaluation and merge"**: the repo ruleset for main requires
  branches to be up to date before merging (the strict required-status-checks policy). GitHub rejects the merge
  atomically when main has moved past the head's main parent, so there is no check-then-merge race for `pr-merge-flow`
  or the traffic cop to close, and neither changes. `--match-head-commit` still protects the head.

Rollout dependencies: the strict policy on main is an infra change, so it goes through the platform-ops issue queue and
is verified live (a slice whose main parent is stale cannot merge); it is checked against the CI-cost note on
serialising flags before it is enabled. Two slices validated at M0 then behave correctly in either merge order: the
second is blocked as out of date after the first merges, rebuilt on M1 and re-evaluated.

### Trusted generator contract

- **Trusted code** is the base checkout's replay script and the downstream's own generator, whose runtime and entry
  point the downstream declares in base-controlled config (the canonical guard does not own a repo-specific
  generator). Today's downstream generator is a Node script (`scripts/verification-playwright/bootstrap-manifest.mjs`
  and its imports `sync-tests.js` and `lib/manifest.js`), so the whole base-side directory is the trusted dependency
  closure, run as `node <entry>` and never `python3 -I`. Isolation: `contents: read` token, no network, no
  `npm install` of head or base dependencies, and no `node_modules` on the path, so imports resolve only to Node
  builtins and the base tree. A generator whose imports need installed packages is out of scope here and needs its
  own generator-migration plan before it can be replayed. Python helpers, where present, run with `python3 -I`.
- **Inert data** is the fetched head objects: read as git objects, never imported, never executed, symlinks not followed.
- The replay is deterministic: manifest initialization is defined (start from the base-side manifest), output paths are
  fixed, and `updated_at` (and any timestamp) is normalized the way the downstream replay already normalizes it
  (`check-main-source.sh` normalizes timestamps before comparing). A generator failure fails closed.

### Bootstrap for a staging-default downstream repo

The guard workflow merged into staging activates immediately, but `pull_request_target` checks out the base ref,
which is main. Main may not yet carry the replay script, the generator or their dependencies, so the slice meant to
deliver them cannot use them. Re-vendoring the tag is therefore not activation. The supported route is two steps:
(1) a scripts-first promotion lands the script, generator and dependencies on downstream main with the guard
workflow unchanged; (2) only then is the guard workflow change activated. Each step carries its own live evidence:
a staging-default first-promotion run and a main-default activation run. aec is main-default, so an aec promotion
cannot prove the staging-default bootstrap and does not count as that evidence.

## Rejected: consuming the `Promote slice` check result

Do not make the guard pass because a `Promote slice` check run succeeded. `promote-slice.yml` is an
unprivileged `pull_request` workflow that runs from the PR head, so the head controls its
definition. A forged same-name check run (or a head that edits the workflow) would pass the guard.
The guard must derive its verdict from code and data the base controls. `promote-slice.yml` stays
read-only and gates nothing.

## Surfaces to change (grep every one before coding)

- aec `.github/workflows/main-via-staging.yml` (canonical blob at tag v2.53.1 is `00c2a594`).
- aec `scripts/check-main-source.sh` and its tests.
- The forged-check detector pins in `scripts/check-forged-gate-names.py` (the guard name and the
  `Promote slice` name must stay distinct; no new job may take a protected name).
- Any downstream repo's slice-aware mid guard, its `promote-slice.yml` and the tests that pin them.
- The main ruleset's strict up-to-date policy (infra, via the platform-ops issue queue). `pr-merge-flow` and its merge
  hook are deliberately NOT changed: the server enforces base movement at merge time.
- Every repo carrying the mid guard or the canonical guard re-vendors after this lands.
- **Drift mechanisms (existing owners, extend, do not duplicate).**
  [2026-11-16-upgrade-detects-vendored-skills](2026-11-16-upgrade-detects-vendored-skills.md) owns guard drift
  detection and [2026-11-21-stale-skills-fail-loudly](2026-11-21-stale-skills-fail-loudly.md) owns its automatic
  execution and released-source checks. `scripts/check-vendored-drift.py` `COPY_SET` lists only four files
  (`main-via-staging.yml`, `check-main-source.sh`, `check-forged-gate-names.py`, its test). Every new replay helper,
  generator and test this plan adds goes into `COPY_SET`, so a downstream with no drift on the old four files cannot
  keep an obsolete replay dependency. Rollout owner: aec, in the same release that ships the replay.

## Acceptance

- A merge-with-main promote slice whose replayed tree equals the head passes the guard.
- A tampered slice, a fork head, a deleted fork, a truncated fetch and an API error each fail closed
  (one test per case, a real git graph, stubbed `gh` only at the network boundary).
- Provenance, real-graph tests: an unrelated second parent, a first parent that is not on staging's first-parent
  history, an octopus merge, an appended commit and a head ref moved after the event each fail closed.
- Freshness, real-graph tests: a slice whose second parent is an older main ancestor fails (never passes on
  re-evaluation); two concurrently validated slices merged in either order (the second is blocked as out of date, then
  rebuilt and passes); a rerun of the same event keeps the same `base.sha`. Live: the main ruleset rejects the merge of
  a slice whose main parent is stale.
- Generator behavior tests: two runs give an identical tree, a changed generator version changes the tuple, a malicious
  sibling import or symlink in the head objects is never loaded, and a generator failure fails closed.
- Drift tests: a missing or stale replay dependency blocks evaluation, and re-vendoring the complete released copy set
  restores it. Detector rc 0 and byte-identical vendoring alone do not prove replay behavior; they are necessary only.
- Bootstrap evidence: a staging-default first promotion and a main-default activation, each run live and recorded
  separately.
- A forged `Promote slice` check run changes nothing (test). The detector's direct Checks-API forgery limitation and
  late-publication race stay as documented; the replay preserves the merge-time detection requirement and does not
  claim to close them.
- Compare pagination beyond 124 commits and the live truncation path are exercised on a throwaway PR
  (the downstream repo's throwaway-PR checklist) before any promotion relies on the guard.
- The detector (`check-forged-gate-names.py`) returns rc 0 on the head.

### R2 acceptance: hardening carried from the R1 review (round 4)

R2 also closes the P2 items raised on R1's last review round, each with a real-graph test in
`tests/test_check_slice_provenance.py`:

- (a) Env-injected git config (`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` pairs) is removed before the
  first git call, `git init` included, so it cannot redirect the fetch.
- (b) Every inherited `GIT_*` variable except the `GIT_REMOTE` input is unset (`GIT_EXEC_PATH`, `GIT_SSH_COMMAND`,
  `GIT_PROXY_COMMAND`, `GIT_ASKPASS`, `GIT_TEMPLATE_DIR`, ...). HTTP proxy and TLS variables stay: they are the
  runner's environment, which the `pull_request_target` job controls, never the PR head.
- (c) A private repo's fetch authenticates with `SLICE_FETCH_TOKEN`, sent as an `http.extraHeader` through env config
  (never argv), only to an `https` remote, and never printed.
- (d) A fresh adversarial review of the replay and the activation diff stays an activation gate for R3: R2 passing its
  review does not stand in for it.
- (e) R3 proves the fetch cost on a large slice and that the workflow passes the event's immutable SHAs
  (`github.event.pull_request.head.sha` / `base.sha`) and `SLICE_REPLAY_TOOL_VERSION`; R2 only consumes them.

R2 decisions, stated: the generator config lives in BASE_SHA's tree at `.github/slice-replay.json`
(`{"generator": {"entry": ..., "outputs": [...]}}`); with none, the replay is git's plain merge. A conflict outside the
declared outputs fails closed; a conflicted output starts from BASE_SHA's copy, a clean one from git's merge, and the
generator rewrites both. The tool version in the tuple is the release tag plus a digest of the replay and provenance
scripts. Network isolation of the generator is not OS-enforced in R2: it runs with no token, no proxy variables and
no installed packages, but Node can still open a socket; R3 decides whether the hosted job adds a network sandbox.

## Consequence for a downstream repo that re-vendors the guard without `promote/*`

A downstream repo that replaces its local guard variant with the canonical guard drops `promote/*` support, because
the canonical guard has none until this plan lands. State the consequence rather than leave it to inference:

- Any release route that depends on merge-with-main slice promotions is **blocked** until this plan ships in a
  tagged canonical release and the downstream repo re-vendors that tag. No slice promotion may be called ready, and
  no waiver stands in for the replay.
- Until then, a promotion that needs a merge-with-main slice has no supported path. The only paths are a
  squash-clean promotion through the canonical guard, or waiting for this plan.
- Whoever hands such a release route to the downstream repo's merge owner repeats this in the handoff, and the
  downstream repo's own divergence plan links back here. The supported behavior is deferred, never silently deleted.
- Unblock criteria: this plan's acceptance list is met (including the separate bootstrap evidence), the canonical guard
  ships it in a tagged release, the scripts-first promotion has reached downstream main, and the downstream repo
  re-vendors that tag.

## Open questions

- Fetch cost for large slices: fetch the compare range only, or the whole head?
- Does the replay live in the canonical guard (aec) with downstream repos adopting it, or stay a
  downstream script until a second repo needs it? Recommendation: canonical, because every
  staging-default repo with slices needs the same rule.
