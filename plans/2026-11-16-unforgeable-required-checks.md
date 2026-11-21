# Unforgeable required checks (SEC-MVS-01)

**Status:** interim detector shipped; the permanent fix needs a repo/org owner to choose A or B below.
**Priority:** assigned by the project's planning process.

## Root cause

A required status check is matched by NAME plus integration_id (15368 = GitHub Actions). Anything running as
the Actions app can publish that name on a commit:

1. an Actions **job** named like the check (a same-repo PR adds `jobs.x.name: <check>` with `run: true`);
2. a direct **Checks API** call from a PR workflow that has `checks: write` (`POST /check-runs`, no `details_url`).

`pull_request_target` loads our guard from the default branch, but it cannot stop another workflow from
publishing the same name. The name carries no provenance.

## What the interim covers (detection, fail closed)

**It detects Actions-job forgery only; a `checks: write` Checks-API POST is not detected; only A or B closes it.**

- Fail closed: the guard's job IS the named check, so it is `in_progress` from the moment the run starts and its
  exit code is the result. A rejection, a failed check-run listing, a failed detector run or a missing guard script
  on the base each fail the job, and so the check.
- `scripts/check-forged-gate-names.py` flags case 1: an Actions-job check run bearing a protected name whose
  workflow run is not the pinned trusted path + event (`.github/workflows/main-via-staging.yml` +
  `pull_request_target` for the guard name, `.github/workflows/review-gate.yml` + `pull_request_target` for
  `Review Gate`).
- Timing: the workflow checks once. A PR job that publishes its forged name after that check is not seen by it.
  Whoever merges must run the detector immediately before `gh pr merge`
  (`set -o pipefail; gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100&filter=all" --paginate | REPO=$REPO python3 scripts/check-forged-gate-names.py`,
  exit 0 required; `pipefail` is mandatory so a failed or truncated listing fails the command instead of reaching the
  detector as empty input), which is the point that cannot race.

## Scope of the interim (stated plainly)

- The detector runs from `main-via-staging.yml`, which triggers on PRs **into main only**. A same-repo PR into
  `staging` can still publish an Actions job named `Review Gate` and no detector sees it at PR time.
- PRs into `staging` are covered only by the merger's pre-`gh pr merge` detector step (the `set -o pipefail` command
  above, exit 0 required).
- The Checks-API residual below is unchanged.
- Proper coverage for PRs into any branch is S5.

## What it cannot cover (the residual risk)

Case 2. A check run published through the Checks API is indistinguishable from a legacy guard's publication
(guards before the job-as-check shape published that way): same app, same name, no job URL. Reruns and `edited` events legitimately create several same-name check runs on
one sha, so counting or id-matching would break legitimate promotions. No detection can close it. Only
provenance can: A or B.

## Correct fix (the repo/org owner picks one)

**A. Org ruleset "Require workflows to pass"** (rule type `workflows`). GitHub runs the named workflow file from a
trusted ref and a PR cannot substitute it. Availability depends on the GitHub plan (unverified for Team; a
repo-level create returned 422).
1. Give the CLI org-owner scope: `gh auth refresh -h github.com -s admin:org`.
2. Confirm the org plan offers the rule by creating the ruleset below with `enforcement: disabled`; a 422 on the
   `workflows` rule means it is not offered, so use B.
3. `gh api -X POST orgs/<org>/rulesets --input ruleset.json` with: `name`, `target: branch`,
   `enforcement: disabled`, `conditions.ref_name.include: ["refs/heads/main"]`,
   `conditions.repository_name.include: ["<repo>"]`, and one rule
   `{"type":"workflows","parameters":{"do_not_enforce_on_create":false,"workflows":[{"repository_id":<numeric id of the repo holding the workflow>,"path":".github/workflows/main-via-staging.yml","ref":"refs/heads/main"}]}}`.
4. Move to `evaluate`, read the result in org Settings > Rules > Insights, then `active`.
5. The required workflow must fail its own job on rejection (it is matched by workflow, not check name).
6. Drop the by-name required check once the required workflow is active.

**B. Own GitHub App as the only publisher.**
1. Create an org-owned App with only `Checks: Read and write` (add `Contents: Read and write` if it also pushes
   release commits); webhooks off; installable on this account only; install on the repos that carry the guard.
2. Store its App id (variable) and private key (secret) in an **Environment** restricted to
   the `main` and `staging` branches, never in repo secrets: a PR workflow runs on `refs/pull/N/merge`, which
   never matches that restriction.
3. Make the guard run in that environment, mint a token with `actions/create-github-app-token` (pinned version)
   and publish the named check with it.
4. Pin the required checks to the App's integration_id in the ruleset
   (`required_status_checks: [{"context": "<name>", "integration_id": <app id>}]`), so a check published by Actions
   never satisfies them.

Prefer A first when the plan offers it (smaller moving parts); B is the fallback.

## Affected surfaces

`main-via-staging.yml`, `review-gate.yml`, `check-main-source.sh`, `check-forged-gate-names.py`, every
downstream repo that copies the guard, and every ruleset requiring the guard check or `Review Gate`.

### The guard job is the required check

The guard workflow publishes no hand-made Checks-API run. Its job is named exactly
`PRs into main must come from staging` and its exit code is the result, the same shape as `review-gate.yml`, whose
`Review Gate` job already satisfies this repo's ruleset as a required check. A `pull_request_target` job's check run
lands on `pull_request.head.sha` in that run's own check suite, the suite the required-status rule reads; a Checks-API
POST lands in the head's oldest suite instead. The workflow has no `concurrency:` group: a cancelled newest run would
leave the required check cancelled or absent until re-run.

Default-branch rule (GitHub change effective 2025-12-08, verified against GitHub's docs): `pull_request_target`
takes the workflow file and the checkout commit from the repository default branch, whatever the PR base. So:

- **staging-default repo**: the canonical guard on `staging` governs PRs into `main` as soon as it merges there.
  No transitional trigger is needed.
- **main-default repo**: unchanged. The guard counts only once it is on `main`, so it lands on `main` first.

The guard's own `checkout` still selects `pull_request.base.sha`, so the scripts come from `main`.

### Workflow shapes: old, transitional, canonical

- **OLD**: `on: pull_request`, job id `source-branch` named for the check. The workflow file comes from the PR head,
  so any PR can rewrite it. The detector flags it (pinned path, wrong event).
- **CANONICAL**: `on: pull_request_target` (branches `[main]`), job named for the check, no `concurrency:`. This
  repo's `.github/workflows/main-via-staging.yml`.
- **TRANSITIONAL**: CANONICAL plus a 3-line block, only for a main-default repo whose guard has not reached `main`
  yet and whose `main` ruleset already requires the context:

  ```yaml
    pull_request:
      types: [opened, edited, synchronize, reopened]
      branches: [main]
  ```

  On the promotion that carries it to `main`, `main`'s old file has no `pull_request_target` trigger, so the
  `pull_request` run of the head's file is the only publisher. That run's own scan flags itself (pinned path, event
  `pull_request`), so the check is red on that one promotion and needs an owner waiver (below).

  Probe evidence (PR #176, a throwaway PR closed after the run, 2026-11-20): the transitional shape with its
  `pull_request` branch filter pointed at a throwaway base. In run 44877949889 (event `pull_request`) `github.sha`
  was the merge commit `96316cf`, and the scan for `pull_request.head.sha` `738fdb8` listed the job's own check run
  (`PRs into main must come from staging`, in progress, job 136766720792). A `pull_request` job's check run is
  listed under the PR head sha, not the merge commit, so the scan sees it; the detector flagged it as forged and the
  job exited 1. The waiver step cannot be bypassed by the scan missing its own job. The next
  `staging` PR deletes the 3 lines; from then on `main`'s file runs under `pull_request_target`, its job is the
  pinned pair, and promotions pass with no waiver. a staging-default repo needs no transitional shape.

### Rollout order for a repo adopting the guard

`main-via-staging.yml` runs under `pull_request_target`: GitHub loads the workflow from the repository's DEFAULT
branch, and the workflow's own checkout then takes the validator scripts from the PR base (`main`). Which branch is
the default decides the order, so check it first (`gh api repos/<repo> --jq .default_branch`):

- **default=main**: the workflow publishes nothing until it is on `main`. If it reaches `main` before the scripts,
  the first promotion after that publishes a failing `PRs into main must come from staging` ("guard script missing
  on base"). Follow the order below.
- **default=staging**: the workflow is live on every main-targeted PR the moment it merges to `staging`, while
  `main` may still lack the scripts. Follow "Rollout order when the default branch is staging" further down.

Which case a repo is in depends on three facts, all read-only to check: the default branch, the workflow type on
`main` and `staging`, and whether the `main` ruleset already requires the guard context
(`gh api repos/<repo>/rules/branches/main`). The waiver follows the legacy publisher plus the required context, not
the default branch alone:

| Default branch | `main-via-staging.yml` | `main` ruleset requires the context | Waiver needed |
|---|---|---|---|
| main | not yet on `main` | no | none: follow the default=main order below |
| main | legacy on `main` | yes | two, see "Bootstrap for a repo whose main ruleset already requires the context" |
| staging | legacy (`pull_request`) | yes | one, on the scripts promotion |
| staging | legacy (`pull_request`) | no | none: follow "Waiver-free variant when `main` does not require the context" (delete the legacy file first), not the waiver order |
| staging | canonical (`pull_request_target`), `main` already has the scripts | either | none |
| staging | canonical (`pull_request_target`), `main` lacks the scripts | no | none: the guard check is red ("guard script missing on base") on the scripts promotion but is not required; note it on the PR |
| staging | canonical (`pull_request_target`), `main` lacks the scripts | yes | one, of the guard check itself: it cannot pass until the scripts are on `main`, see "Canonical workflow already on staging, scripts missing on main" |

Which downstream repo falls in which row is tracked outside this product repo.

The default=main order, for a repo whose `main` has the scripts last:

0. Look at what `main` requires (`gh api repos/<repo>/rules/branches/main`, the `required_status_checks`
   contexts) and at who publishes it today. A hand-rolled `main-via-staging.yml` whose **job** is named
   `PRs into main must come from staging` publishes that name as an Actions job, so the forged-gate scan flags it.
   - `main` does **not** require that context: delete the legacy workflow on `staging` first, re-run the scan,
     then continue with step 1.
   - `main` **already requires** it and the legacy job is its only publisher: do **not** delete it first and do
     **not** drop the context from the ruleset. Deleting the publisher leaves no promotion able to satisfy the
     required context, because the canonical workflow counts only once it is on `main`. Follow "Bootstrap for a
     repo whose main ruleset already requires the context" below instead of steps 1 to 4.
1. Scripts (`check-main-source.sh`, `check-forged-gate-names.py`) and their tests land on `staging`.
2. A `staging` to `main` promotion carries the scripts to `main`.
3. Only then the workflow (and its test) lands on `staging`.
4. Promote again.
5. Flip the required check to the guard name only after its first green run.

### Bootstrap for a repo whose main ruleset already requires the context

Not a free pass. This bootstrap needs two owner waivers, on two different promotions, and each one is the owner's to
grant (a directive or a cop never waives a gate); record each approval on its PR:

- **Waiver 1, the scripts promotion (step 1):** its head still carries the legacy `pull_request` job, so the
  merge-time scan flags that job. The owner waives the scan result on that PR.
- **Waiver 2, promotion P1 (step 3):** the TRANSITIONAL job's own scan flags itself, so the required check is red.
  The owner waives the guard check on that PR.

A main-default repo whose `main` already carries the canonical workflow is not in this section. It
does not inherently need a waiver for the first replacement promotion: `main`'s file runs under
`pull_request_target`, and GitHub evaluates a `pull_request_target` job's check for rulesets
(<https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks#checks-from-some-workflow-jobs-are-not-evaluated>).

An earlier version of this section put the canonical workflow at a temporary second path while the legacy file
stayed. That no longer works: the guard's job is now the required check, and a job from the temporary path is not
the pinned (`.github/workflows/main-via-staging.yml`, `pull_request_target`) pair, so its own scan flags it on every
promotion until the file moves. Use the TRANSITIONAL shape in place instead:

1. `staging`: scripts and their tests land first (default=main order steps 1 and 2 carry them to `main`), with the
   legacy workflow untouched. Waiver 1: the merge-time scan flags the legacy job on this scripts promotion; the
   owner waives it with the waiver text below, recorded on that PR.
2. `staging`: one PR replaces the legacy `main-via-staging.yml` with the TRANSITIONAL shape at the same path.
3. Promotion P1 to `main`. Only the head's `pull_request` run publishes the context, and its scan flags its own
   job, so the check is red. Waiver 2: the owner waives it, after hand-verifying and writing on the PR: head repo equals
   base repo, head ref is `staging`, every flagged run is this workflow's own job (path matches, event
   `pull_request`), and the promotion adds no other workflow.
4. A normal PR into `staging` deletes the 3-line `pull_request:` block. Open no further promotion before it lands.
5. Promotion P2: `main`'s file runs under `pull_request_target`, its job is the pinned pair, the scan exits 0 and
   the check is green. This is the first promotion that needs no waiver.

Status: derived from GitHub's event semantics, not yet run end to end. The first repo to adopt it records the
result here.

### Rollout order when the default branch is staging

The waiver rule is about the legacy workflow, not the default branch. Whenever `staging` still carries a legacy
`pull_request` `main-via-staging.yml` and `main` requires its context, every main-targeted PR head carries the legacy
job, the detector exits 1 on it, and the scripts promotion needs exactly one owner waiver. Repos already on the
canonical workflow need no scan waiver, provided `main` already has the guard scripts; if it lacks them and requires
the context, the guard check itself needs one waiver (see "Canonical workflow already on staging, scripts missing on
main").

No order avoids that waiver:

- Delete the legacy file in the scripts PR: `main` has no publisher, the required context never appears, and the
  promotion is blocked.
- Scripts, legacy deletion and the canonical workflow in one `staging` PR: `staging` is the default branch, so the
  canonical workflow runs on main-targeted PRs at once and checks out `main`, which still lacks the scripts. It
  publishes "guard script missing on base" and the legacy job is gone, so nothing can pass. Never combine them.

The order:

1. `staging`: scripts and their tests, no canonical workflow, legacy untouched.
2. Scripts promotion, with one owner waiver (text below).
3. ONE `staging` PR that deletes the legacy file and adds the canonical workflow and its test. `main` already has the
   scripts, so the canonical run at once is correct.
4. Promote again. The head has no legacy job and `main` has the scripts, so the detector exits 0: no waiver.
5. Flip the required check to the guard name only after a green canonical run.

A repo that already runs the canonical workflow starts at the promotion step and needs no scan waiver, but only when
`main` already has the scripts; otherwise see "Canonical workflow already on staging, scripts missing on main".

#### Canonical workflow already on staging, scripts missing on main

This is the combined-rollout failure above reached by another route: with `staging` as the default branch the
canonical workflow runs on every main-targeted PR, checks out `main`, and fails on the missing scripts. Fourth
fact to read before choosing a row: whether `main` has `scripts/check-main-source.sh` and
`scripts/check-forged-gate-names.py` (`gh api "repos/<repo>/contents/scripts?ref=main" --jq '.[].name'`).
No order fixes it, because the scripts can only reach `main` through a promotion the guard then judges:

- `main` does not require the guard context: the scripts promotion carries a red, non-required guard check. Merge it
  with that stated on the PR; the next promotion is green.
- `main` requires it: the owner waives the guard check once, on the scripts promotion only, with the same
  record-on-the-PR rule as the scan waiver (a directive or a cop never waives). The next promotion must pass with no
  waiver. Do not delete the canonical workflow to dodge it: with the publisher gone the required context never
  appears and the promotion is blocked anyway.

#### Waiver-free variant when `main` does not require the context

The detector flags the legacy job whether or not its context is required, so the waiver order above is only for a
repo whose `main` requires the context. When `main` does **not** require it, nothing needs the legacy publisher, so
remove it before any promotion carries it:

1. `staging`: delete the legacy `main-via-staging.yml` alone (no scripts, no canonical workflow yet; with no
   workflow there is nothing to publish and nothing required to be missing).
2. `staging`: scripts and their tests.
3. Scripts promotion. The head has no legacy job, so the detector exits 0: no waiver.
4. ONE `staging` PR that adds the canonical workflow and its test (`main` has the scripts, so its first run is
   correct).
5. Promote again, then flip the required check to the guard name after a green canonical run.

Steps 1 and 2 may be one PR; the canonical workflow must never share a PR with the scripts, for the reason above.

The waiver is the owner's to grant; a directive or a cop never waives a gate. The merger re-runs the detector after
the comment is posted and merges only when the flagged set is exactly the one legacy run. Waiver text (fill in the
placeholders):

> Owner waiver, one time, this PR only. I waive the main-via-staging forged-gate scan result for `<repo>` `#<pr>`
> at head `<40-hex sha>`. The only flagged run is Actions run `<run id>` (job `<job id>`), the repo's own legacy
> `.github/workflows/main-via-staging.yml` on event `pull_request`. Verified: head repo equals base repo, head ref
> is `staging`, no other flagged run, the promotion adds no other workflow. The next promotion must pass the scan
> with no waiver. - `<owner>`, `<date>`

The flagged legacy job is the repo's own publisher, not an attacker's: its run path is the pinned path and only the
event differs (`pull_request` against the trusted `pull_request_target`). The detector cannot tell the two apart by
name, so the answer is an owner waiver, never a looser detector.

First run (a staging-default repo on the legacy workflow): its scripts promotion merged with no scan run (the PR
body said no scanner runs against that head) and no waiver recorded, so it did not show the one-PR order works: the
detector exits 1 on that head after the fact. The owner ratifies it with the text above, recorded on that PR. Its
swap then followed this order, and the next promotion head passes the scan with exit 0.

Two gotchas seen on the first end-to-end rollout (confirmed on a downstream repo's first green main-targeted run,
check published by app 15368):

- A PR into `main` needs the `review:high` label before `Review Gate` goes green; add it when opening a promotion.
- A head can carry two `Review Gate` runs (the workflow job and a Checks-API run). Rerun the failed one, not only
  the latest; a green latest run does not clear a failed earlier one.

### Drift check (installer and doctor)

Downstream repos copy the guard byte-identically (`scripts/check-vendored-drift.py` `COPY_SET`: the workflow, both
scripts and the detector's test). A Dependabot bump or a hand edit silently forks the copy. The doctor (and any
fleet hub) must flag a repo whose copy differs from the canonical blob, by running
`python3 scripts/check-vendored-drift.py --canonical-repo <owner>/agents-environment-config --ref <released tag>`
(exit 1 names each drifted file; exit 2 fails closed). The one re-sync command, run from the repo root:

```bash
for f in .github/workflows/main-via-staging.yml scripts/check-main-source.sh scripts/check-forged-gate-names.py tests/test_check_forged_gate_names.py; do gh api "repos/<owner>/agents-environment-config/contents/$f?ref=<released tag>" -H "Accept: application/vnd.github.raw" > "$f"; done
```

The doctor wiring is not built yet (plan only); the script itself ships.

### Vendoring source is a released tag, never a branch

Incident: a hub copied its canonical `main-via-staging.yml` from aec `main` (blob `0aea5d69`, `actions/checkout@v4`)
while aec `staging` already had blob `827ffda7` (`@v7`), so every repo that took the hub's copy was downgraded.
A branch is a moving target and `main` lags `staging`.

- The vendoring source for the guard workflow and scripts is a released aec tag (or the installer's output for that
  tag), never a branch.
- The fleet/hub drift check (`scripts/check-vendored-drift.py` and the doctor) compares a repo's copy against the TAGGED blob: pass `--ref <released tag>`. The script's `--ref main` default stays only for backward compatibility
  of existing callers; the doctor must always pass a tag.
- The installer prints the tag it vendored from, so a repo's copy names its source.

Status: plan only. The tag-based doctor check and the installer's tag line are not built.

Input contract of the detector: it fails closed (exit 2) on empty, malformed or check-run-less input, because a head
always has check runs by merge time; an empty set is not "no forgery". Callers should still use `set -o pipefail`.

## Steps

- S1. Owner chooses A or B and runs it.
- S2. Switch the guard (A: required workflow; B: App token) and re-pin the required checks.
- S3. Probe PR: a branch that adds a same-name job AND a same-name Checks API call is blocked.
- S4. Retire the detector or keep it as defence in depth.
- S5. `review-gate.yml` (owned by the claude-skills repo, a separate PR after its in-flight 1.4.0 change lands)
  invokes `scripts/check-forged-gate-names.py` for PRs into every protected branch, so `Review Gate` forgery is
  detected at PR time on `staging` as well, not only by the merge-time step.
- S6. WITHDRAWN (2026-11-16): the `Review Gate` trusted pair in `scripts/check-forged-gate-names.py`
  (`.github/workflows/review-gate.yml`, `pull_request_target`) stays as it is. S6 assumed a stacked PR could make that
  pair vouch for something it did not judge, by either of two routes, and probes disproved both:
  1. The job's result attaches to another PR's head. It does not: a stacked child's `Review Gate` job and its check
     run attach to the child's OWN head sha (probe PRs #158 and #159, closed).
  2. The workflow file comes from the PR's base branch, which for a stacked PR is a contributor-controlled branch.
     It does not: `pull_request_target` runs the file from the repository's default branch, as GitHub documents ("runs
     in the context of the default branch of the base repository"). Probe PR #160 (closed): the outer base branch
     carried a modified `review-gate.yml` with an extra job, and the stacked child's run executed the default branch's
     copy without it.
  So (path, event) does identify a trusted file, and the pair cannot be supplied by a PR head. Designs that were built
  and rejected on the way, so nobody rebuilds them: own-run exclusion, head-sha binding, GitHub's `protected` branch
  flag as a trust test, and a `TRUSTED_BASE_BRANCHES` base-branch allowlist (each guarded a threat route 1 or 2 above
  shows does not exist, and the allowlist added encoding and default-branch edge cases to every caller). The
  claude-skills wrapper keeps its own `{"Review Gate": set()}` scoping, and from claude-skills 3.2.0 the workflow job
  is named `review-gate-runner`, so that scoping flags only a legacy `Review Gate` Actions job on a repo whose main
  still carries the old workflow. Re-vendoring this script into claude-skills therefore needs no S6 change. The
  remaining forgery gap is the one A or B closes: a Checks-API POST under a protected name.
