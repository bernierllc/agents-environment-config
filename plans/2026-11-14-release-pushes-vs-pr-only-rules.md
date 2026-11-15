# Release pushes to `main` conflict with PR-required rules

Status: planned; scheduling pending. A review-thread-resolution waiver for this repo expires
on 2026-12-14 (see the catalog's record check).

## Root cause and affected surfaces

`.github/workflows/version-bump.yml` commits `chore(release): vX.Y.Z` and runs
`git push origin main --tags` with `GITHUB_TOKEN`. A ruleset that requires pull requests on
`main` rejects that push, so this repo cannot adopt PR-required rules, review-thread
resolution, or a `staging` branch while the release flow works this way. A package-release
workflow in a sibling repo has the same shape.

Surfaces: `version-bump.yml`, `ci.yml` triggers, the merge policy in `AGENTINFO.md`,
`scripts/` release helpers, and any branch-name assumption in tests.

## S1 — Choose the release mechanism

1. Verify whether a GitHub Actions bypass actor is possible for rulesets at all
   (documentation, then a throwaway repo). Do not assume it.
2. If not: have the workflow open a release PR with the version bump and enable auto-merge,
   or use a dedicated GitHub App as the ruleset bypass actor. Pick one and record why.
3. Prove it end to end on a throwaway repo before touching this one.

## S2 — Adopt the rules

1. Create the PR-required ruleset with review-thread resolution on `main`.
2. Create a `staging` branch, point PRs at it, promote to `main` by merge commit, update
   the merge policy and `ci.yml` triggers.
3. Remove the waiver in the catalog record.

## Done when

A merge to `main` still produces a release, direct pushes to `main` are rejected, and the
catalog check reports thread resolution on.
