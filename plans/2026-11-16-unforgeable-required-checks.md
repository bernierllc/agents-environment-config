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

- Fail closed: the named check exists `in_progress` before validation, a rejection completes it `failure`, and a
  failed check-run listing, a failed detector run or a missing guard script on the base each fail the check.
- `scripts/check-forged-gate-names.py` flags case 1: an Actions-job check run bearing a protected name whose
  workflow run is not the pinned trusted path + event.
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

Case 2. A check run published through the Checks API is indistinguishable from our own guard's publication:
same app, same name, no job URL. Reruns and `edited` events legitimately create several same-name check runs on
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

### Rollout order for a repo adopting the guard

`main-via-staging.yml` runs under `pull_request_target`: GitHub loads the workflow from the default branch (`main`
for a repo that promotes through `staging`), so it publishes nothing until it is on `main`; it also checks the
validator scripts out from the PR base (`main`). If the workflow reaches `main` before the scripts, the first
promotion after that publishes a failing `PRs into main must come from staging` ("guard script missing on
base"). Order the rollout so `main` has the scripts before any workflow that calls them runs:

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

Not a free pass: the plan has no sanctioned bootstrap that avoids a scan waiver, because the legacy job is still in
the head of the promotion that carries the canonical guard to `main`. Exactly one promotion is waived, and the
waiver is the owner's to grant (a directive or a cop never waives a gate); record the approval on that PR.

A same-path swap deadlocks: `pull_request` runs the head's `main-via-staging.yml` (the canonical file has no
`pull_request` trigger) and `pull_request_target` runs `main`'s (still the legacy file), so the swap promotion has no
publisher at all. So the canonical workflow arrives under a temporary second filename while the legacy file stays
in place:

1. `staging`: scripts, their tests and the canonical workflow at a temporary path (for example
   `.github/workflows/main-via-staging-canonical.yml`). The legacy workflow stays untouched.
2. Bootstrap promotion P1 to `main`. The legacy job still publishes the required context, so the merge-time scan
   exits 1 with only that job flagged. The merger waives it only after hand-verifying, and writing on the PR:
   head repo equals base repo, head ref is `staging`, every flagged run is the legacy workflow's job (path and event
   both match, none from another workflow), and the promotion adds no other workflow.
3. A normal PR into `staging` deletes the legacy workflow. Open no further promotion before it lands: with both
   publishers present, the canonical scan flags the legacy job and fails the context.
4. Promotion P2: its head has no legacy job, `main`'s canonical file publishes the context through the Checks API,
   and the scan exits 0. This is the first promotion that needs no waiver.
5. Move the canonical workflow to its standard path (`main-via-staging.yml`) in a `staging` PR and promote
   (P3). Flip the required check only after P2 or P3 shows a green guard run.

Status: derived from GitHub's event semantics, not yet run end to end. The first repo to adopt it records the
result here.

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
