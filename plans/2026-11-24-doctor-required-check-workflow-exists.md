# Review-gate doctor fails when a ruleset requires `Review Gate` and the default branch cannot publish it

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
  returns nothing, so `main()` cannot turn a remote finding into an exit code. It has no check that the gate can report at all.
  That gap is what remains.

## Problem

Rulesets applied before any workflow exists require checks that cannot report. `Review Gate` runs on `pull_request_target`; the
shipped `review-gate.yml` records (in its header, with a live run as evidence) that GitHub takes that workflow file from the
repository **default branch**, whatever the PR base, and a PR cannot supply it. So the workflow must already be merged to the
default branch before any PR can pass. A new repo whose default branch has no gate deadlocks the first PR and the first promotion
for every ordinary (non-bypass) merge (seen on two new repos on 2026-11-23). The create-time script now prevents the order mistake
for repos it creates. Nothing detects the same state afterwards: a workflow renamed or deleted, a ruleset added by hand, a repo
created some other way. A bypass list does not make the required check satisfiable, so the check runs on those rulesets too.

## Root cause

A required status check is a name in a ruleset; whether anything can produce that name is a separate fact nobody compares.

## Scope decision: the known contract only

A general "can any workflow publish context X" analyzer is not part of this plan. Producers can be job names, reusable-workflow
calls, matrices, expressions, PR-supplied workflows (`pull_request` runs from the PR's merge commit, so a baseline branch
inventory proves neither presence nor absence) or Checks API calls with an explicit name. Getting that wrong yields false FAILs
and false assurance, so it is a separate plan. This plan hard-fails only on the one contract the review-gate skill itself owns:
`Review Gate`, produced by a `pull_request_target` workflow, which is read from the default branch only. For that context the
default branch inventory is sufficient evidence, because nothing else can supply the workflow.

## Where it can run

`review-gate-doctor.yml` (the optional CI job) states it has no token that can read rulesets, so its ruleset checks are warnings
there. This check therefore runs where `gh` can read rulesets and repository contents (an operator's shell, or a post-create step
in an org's repo-create flow); in the CI job it stays a warning that says why it was skipped. Opting the CI job into a token is a
separate decision for the repo owner. Minimum permissions: ruleset reads need Metadata read, workflow reads need Contents read.

## Correct fix (claude-skills PR, normal gates)

1. `remote_checks` returns a result and `main()` exits 1 on a confirmed remote failure (it returns nothing today).
2. For every **enforcing** ruleset (paginate the listing) that covers one of the doctor's `MERGE_BRANCHES` (`main`, `staging`, via
   `ruleset_covered_branches`), read its `required_status_checks`. Other branches are out of scope and the output says so.
3. Only the context `Review Gate` is analyzed. If it is pinned to an `integration_id` other than 15368 (GitHub Actions), skip it
   (an installed app reports it). Pinned to 15368, or with no `integration_id`, it is analyzed. Every other required context is
   listed once as "producer not verified (generic producer analysis is out of scope)": a WARN, never a FAIL.
4. List `.github/workflows/` on the **default branch** once and read the files. The listing is complete only below the Contents API
   cap of 1,000 entries; at the cap, after a partial fetch failure, or on a rate limit, the result is a WARN.
5. The default branch can publish `Review Gate` when `.github/workflows/review-gate.yml` (or `.yaml`, the installer's path) exists
   there, or any workflow file there mentions the string `Review Gate` (an older template version published it from a
   differently named job, and a workflow can also create a check with an explicit name). A mention is deliberately lenient: a
   false pass is acceptable, a false FAIL is not.
6. **FAIL** (exit 1, naming the context, the default branch and the fix: "merge review-gate.yml to <default branch> before
   requiring the check") when the default-branch inventory is complete and readable and nothing there can publish `Review Gate`.
   That holds even when the workflow exists only on `staging` or another covered branch: it will not load until it reaches the
   default branch, and the message says so.
7. Absence of `.github/workflows/` (a 404 on the listing) counts as the empty inventory only when the repository and the default
   branch are already known readable; the helper keeps the HTTP status. Denied access, a missing ref and a transient failure are
   each a WARN that names the status.
8. `install-workflow.py`'s closing hint orders the steps: merge the workflow to the default branch first, then require the check.
9. Contract tests (fixtures, no network): a ruleset requiring `Review Gate` with `review-gate.yml` on the default branch (pass),
   without it (fail), on a covered branch only (fail, default branch named), a differently named job that mentions `Review Gate`
   (pass), a non-Actions integration id (skip), a source-less context (analyzed), another required context (warn, not verified),
   more than one page of rulesets, the 1,000-entry cap, denied access, missing ref and transient failure (each warn), an absent
   workflows directory on a readable repo (fail), and `main()` exiting 1 on a confirmed failure and 0 on warnings only.
10. Versioning: update the version in every file the doctor's parity check and the repo's manifest consistency check name
    (`review-gate/SKILL.md`, `review-gate/hooks.json`, `skills-manifest.json`), and add a note under the doctor section of
    `review-gate/SKILL.md`.

## Rollout

Author delegate opens the claude-skills PR into `main` with the `review:high` label (squash). aec picks up the new version through
the normal catalog sync; no fleet upgrade is requested, and no broad `aec upgrade` runs. Repos get the check when they next
re-vendor.

## Out of scope

Installer seed flag and workflow templates (dropped above). General producer inference for arbitrary required contexts, including
reusable-workflow traversal, matrix and expression names, event eligibility, merge queues and PR-supplied workflows (a separate
plan; those contexts WARN today). Applying or repairing rulesets (the org's repo-create script and its operators own that).
Branches other than `main` and `staging`. Branch protection rules that predate rulesets. Deciding whether the doctor's CI job gets
a ruleset-reading token.
