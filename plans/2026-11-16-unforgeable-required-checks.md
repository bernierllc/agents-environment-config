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
  (`gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100&filter=all" --paginate | REPO=$REPO python3 scripts/check-forged-gate-names.py`,
  exit 0 required), which is the point that cannot race.

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
downstream repo that copies the guard, and every ruleset requiring the guard check or `Review Gate`. Scripts land
on the default branch before the workflow that calls them.

## Steps

- S1. Owner chooses A or B and runs it.
- S2. Switch the guard (A: required workflow; B: App token) and re-pin the required checks.
- S3. Probe PR: a branch that adds a same-name job AND a same-name Checks API call is blocked.
- S4. Retire the detector or keep it as defence in depth.
