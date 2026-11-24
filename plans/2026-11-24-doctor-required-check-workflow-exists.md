# Review-gate doctor fails when a ruleset requires a check whose workflow is absent on the target branch

**Status:** planned. Scheduling pending.
**Priority:** medium. Cheap to build; it turns a silent merge deadlock into a named failure.

**Incumbent (checked 2026-11-24):**

- Seeding a new repo before its rulesets exist is already owned by an org's repo-create script (a platform-ops repo's
  `scripts/repo_create.py`, merged 2026-11-23). It writes the gate workflows to the integration branch, then applies rulesets, and
  stops at its step 4 when a workflow behind a required check is missing. The same ordering is written into the operator
  reference for that flow. So the **installer seed flag and the `main-via-staging.yml` / `notion-sync.yml` templates are dropped
  from this plan**: those two workflows are one org's conventions, not a generic `review-gate` product surface, and a second copy
  would drift from the reference repo the script copies byte-for-byte.
- `review-gate/scripts/doctor-review-gate.py` (claude-skills) has `remote_checks`, which lists rulesets and only *warns*; it has
  no check that a required check can report at all. That gap is what remains, and it is generic: it helps every repo that installs
  `review-gate`, including ones with no repo-create script.

## Problem

Rulesets applied before any workflow exists require checks that cannot report. `Review Gate` runs on `pull_request_target`, which
GitHub loads from the PR's **base** branch, so the workflow must already be merged on that branch before the first PR can pass.
The first PR and the first promotion into `main` then deadlock (seen on two new repos on 2026-11-23). The create-time script now
prevents the order mistake for repos it creates. Nothing detects the same state afterwards: a workflow renamed or deleted on the
base branch, a ruleset added by hand, a repo created some other way.

## Root cause

A required status check is a name in a ruleset; whether anything can produce that name is a separate fact nobody compares. A
check that fails loudly belongs next to the other ruleset checks in the doctor, which `review-gate-doctor.yml` already runs in CI.

## Correct fix (claude-skills PR, normal gates)

1. In `remote_checks`, for every **enforcing** ruleset that covers a branch (reuse `ruleset_is_enforcing` and
   `ruleset_covered_branches`), read its `required_status_checks` contexts.
2. Skip a context whose entry carries an `integration_id` other than GitHub Actions (15368): an installed app reports those, with
   no workflow in the repo. Contexts with no `integration_id` are treated as Actions checks.
3. For each remaining context and each covered branch, list `.github/workflows/` at that branch
   (`gh api repos/<repo>/contents/.github/workflows?ref=<branch>`) and look for a workflow whose job `name:` (or job id, or
   `<workflow name> / <job name>`) equals the context. **FAIL** (exit 1, naming the context, the branch and the fix: "merge
   the workflow to <branch> before requiring it") when none matches. **WARN** when a candidate name contains a `${{ }}` expression
   and cannot be resolved statically. A listing that cannot be read is a WARN, never an OK.
4. `install-workflow.py`'s closing hint orders the steps: commit the workflow to the base branch first, then require the check.
5. Contract test: a fixture ruleset requiring `Review Gate` with and without `review-gate.yml` on the branch (fail / pass), an
   Actions context with no workflow (fail), a non-Actions `integration_id` (skipped), a `${{ }}` job name (warn), an unreadable
   listing (warn).
6. Note in `review-gate/SKILL.md` under the doctor section; bump the skill version.

## Rollout

Author delegate opens the claude-skills PR into `main` with the `review:high` label (squash). aec picks up the new version through
the normal catalog sync; no fleet upgrade is requested, and no broad `aec upgrade` runs. Repos get the check when they next
re-vendor.

## Out of scope

Installer seed flag and workflow templates (dropped above). Applying or repairing rulesets (the org's repo-create script and its
operators own that). Branch protection rules that predate rulesets.
