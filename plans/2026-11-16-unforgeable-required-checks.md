# Unforgeable required checks (SEC-MVS-01)

**Priority:** assigned by the PM task (Tracker row Owner `Needs-PM` until then; the row exists and is linked below).
**Status:** interim detector shipped (PR #151); permanent fix awaits the maintainer's choice of A or B.

## Root cause

A required status check is matched by NAME plus integration_id (15368 = GitHub Actions). Anything running as
the Actions app can publish that name on a commit:

1. an Actions **job** named like the check (a same-repo PR adds `jobs.x.name: <check>` with `run: true`);
2. a direct **Checks API** call from a PR workflow that has `checks: write` (`POST /check-runs`, no `details_url`).

`pull_request_target` loads our guard from the default branch, but it cannot stop another workflow from
publishing the same name. The name carries no provenance.

## What the interim PR covers (detection, fail closed)

- Fail closed: the named check exists `in_progress` before validation and a rejection completes it `failure`.
- `scripts/check-forged-gate-names.py` flags case 1 (an Actions-job check run bearing a protected name whose
  workflow run is not the pinned trusted path + event). A missing guard script on the base fails with a clear message.
- The cop merge step runs the detector before `gh pr merge` (ask handed to the claude-skills cop; owner `pr-merge-flow`).

## What it cannot cover (the residual risk)

Case 2. A check run published through the Checks API is indistinguishable from our own guard's publication:
same app, same name, no job URL. Reruns and `edited` events legitimately create several same-name check runs on
one sha, so counting or id-matching would break legitimate promotions. Codex review on PR #151 raised this as P1;
it is correct, and no detection can close it. Only provenance can: A or B below.

## Correct fix (maintainer picks one)

- **A. Org ruleset, "Require workflows to pass"** (rule `workflows`). GitHub runs the named workflow from a
  trusted ref; the PR cannot substitute it. The workflow must fail its own job on rejection. Plan availability on
  the Team plan is unverified (a repo-level create returned 422). Runbook: Notion "Runbook A".
- **B. Own GitHub App as the only publisher**, key in an Environment restricted to `staging`/`main`, required
  checks pinned to the App's integration_id so an Actions-published name never satisfies them. Also gives the
  version-bump push its credential. Runbook: Notion "Runbook B".

Run A first (its step 2 settles plan availability); B is the fallback.

## Affected surfaces

`main-via-staging.yml`, `review-gate.yml`, `check-main-source.sh`, `check-forged-gate-names.py`, every
downstream repo carrying the guard (hub, nevar-plan, nevar-content), the `main` rulesets requiring
`PRs into main must come from staging` and `Review Gate`.

## Steps

- S1. Maintainer chooses A or B and runs the runbook.
- S2. Switch the guard (A: required workflow; B: App token) and re-pin the required checks.
- S3. Probe PR: a branch that adds a same-name job AND a same-name Checks API call is blocked.
- S4. Retire the detector or keep it as defence in depth; update the runbooks.
