# Review-gate doctor fails when a ruleset requires a check that no workflow can publish

**Status:** planned. Scheduling pending.
**Priority:** medium. Cheap to build; it turns a silent merge deadlock into a named failure.

**Incumbent (checked 2026-11-24):**

- Seeding a new repo before its rulesets exist is already owned by an org's repo-create script (a platform-ops repo's
  `scripts/repo_create.py`, merged 2026-11-23). It writes the gate workflows to the integration branch, then applies rulesets, and
  stops at its step 4 when a workflow behind a required check is missing. The same ordering is written into the operator
  reference for that flow. So the **installer seed flag and the `main-via-staging.yml` / `notion-sync.yml` templates are dropped
  from this plan**: those two workflows are one org's conventions, not a generic `review-gate` product surface, and a second copy
  would drift from the reference repo the script copies byte-for-byte.
- `review-gate/scripts/doctor-review-gate.py` (claude-skills) has `remote_checks`, which lists rulesets and only *warns*, and
  returns nothing, so `main()` cannot turn a remote finding into an exit code. It has no check that a required check can report
  at all. That gap is what remains.

## Problem

Rulesets applied before any workflow exists require checks that cannot report. `Review Gate` runs on `pull_request_target`; the
shipped `review-gate.yml` records (in its header, with a live run as evidence) that GitHub takes that workflow file from the
repository **default branch**, whatever the PR base, so the workflow must already be merged there before any PR can pass. A new
repo whose default branch has no gate then deadlocks the first PR and the first promotion for every ordinary (non-bypass) merge
(seen on two new repos on 2026-11-23). The create-time script now prevents the order mistake for repos it creates. Nothing detects
the same state afterwards: a workflow renamed or deleted, a ruleset added by hand, a repo created some other way. An active ruleset
may list bypass actors; the check still runs on it, because a bypass list does not make the required check satisfiable.

## Root cause

A required status check is a name in a ruleset; whether anything can produce that name is a separate fact nobody compares. A
check that fails loudly belongs next to the other ruleset checks in the doctor.

## Where it can run

`review-gate-doctor.yml` (the optional CI job) states it has no token that can read rulesets, so its ruleset checks are warnings
there. This check therefore runs where `gh` can read rulesets and repository contents (an operator's shell, or a post-create step
in an org's repo-create flow); in the CI job it stays a warning that says why it was skipped. Opting the CI job into a token is a
separate decision for the repo owner. Minimum permissions: ruleset reads need Metadata read, workflow reads need Contents read.

## Correct fix (claude-skills PR, normal gates)

1. `remote_checks` returns a result and `main()` exits 1 on a confirmed remote failure (it returns nothing today).
2. For every **enforcing** ruleset (paginate the listing), read its `required_status_checks`. Scope is the doctor's own
   `MERGE_BRANCHES` (`main`, `staging`) via `ruleset_covered_branches`; other branches are out of scope and the output says so.
3. Classify each context by `integration_id`. Another id (not 15368): an installed app reports it, so skip. **15368 (GitHub
   Actions) is the only case that can FAIL.** No `integration_id` is "any source" (an external CI or a commit-status publisher can
   satisfy it) and is never assumed to be Actions: OK when a workflow job matches, otherwise a WARN naming the context and saying
   to pin 15368 or confirm the producer.
4. Fetch the workflow files once per ref and cache them (list `.github/workflows/` at the ref, then read each file). Refs to read:
   the **default branch** (source of a `pull_request_target` workflow) and each covered branch. A listing is complete only below
   the Contents API cap of 1,000 entries; at the cap, or after a partial fetch failure or rate limit, the result is a WARN.
5. Derive the contexts each workflow can publish with GitHub's own formats: an ordinary job publishes its `name:`, or its job id
   when it has no `name:` (an explicit name **replaces** the id, so a stale required `build` fails when the job is now named
   `Tests`); a job that calls a reusable workflow publishes `<calling job name> / <called job name>`. A `<workflow name> / <job
   name>` form is not derived: a workflow `CI` with job `build` publishes `build`. A name that cannot be resolved statically
   (a `${{ }}` expression, a matrix job, a reusable workflow whose file cannot be read) is a **WARN**, never a pass.
6. A producer must be able to run on a pull request. A workflow whose only triggers are `workflow_dispatch` or `schedule` cannot
   report on a PR: that does not count as a producer (FAIL for a pinned Actions context). Branch or path filters that may exclude
   the protected branch, and a merge queue without a `merge_group` trigger, are WARN: not decidable statically.
7. A `pull_request_target` producer counts only when found on the **default branch**; one found only on a covered branch is a WARN
   that says it will not load until it is merged to the default branch. Other producers count on the covered branch.
8. **FAIL** (exit 1, naming the context, the ref and the fix: "merge the workflow to <branch> before requiring it") when a pinned
   Actions context has no producer. An absent `.github/workflows/` directory is that case when the ref is readable and the
   listing returns 404; the helper keeps the HTTP status so it can tell absence from a missing ref, denied access (WARN) or a
   transient failure (WARN). Do not read a 404 as absence before the repository and ref are known to be readable.
9. `install-workflow.py`'s closing hint orders the steps: merge the workflow to the default branch first, then require the check.
10. Contract tests (fixtures, no network): a ruleset requiring `Review Gate` with and without `review-gate.yml` on the default
    branch (fail / pass), on a covered branch only (warn), a pinned Actions context with no workflow and with no workflows
    directory (fail), a source-less context with no workflow (warn), another app id (skip), job `name:` precedence over job id,
    `CI / build` against workflow `CI` job `build` (fail) and `build` (pass), a reusable-workflow call, a `${{ }}` name and a matrix
    job (warn), a `workflow_dispatch`-only producer (fail), a branch-filtered producer (warn), more than one page of rulesets, the
    1,000-entry cap, denied access, missing ref and transient failure (each warn), and `main()` exiting 1 on a confirmed failure.
11. Versioning: update the version in every file the doctor's parity check and the repo's manifest consistency check name
    (`review-gate/SKILL.md`, `review-gate/hooks.json`, `skills-manifest.json`), and add a note under the doctor section of
    `review-gate/SKILL.md`.

## Rollout

Author delegate opens the claude-skills PR into `main` with the `review:high` label (squash). aec picks up the new version through
the normal catalog sync; no fleet upgrade is requested, and no broad `aec upgrade` runs. Repos get the check when they next
re-vendor.

## Out of scope

Installer seed flag and workflow templates (dropped above). Applying or repairing rulesets (the org's repo-create script and its
operators own that). Branches other than `main` and `staging`. Branch protection rules that predate rulesets. Deciding whether the
doctor's CI job gets a ruleset-reading token.
