# Release pushes to `main` conflict with PR-required rules

Status: planned; scheduling pending.

## Root cause and affected surfaces

`.github/workflows/version-bump.yml` commits `chore(release): vX.Y.Z` and runs
`git push origin main --tags` with `GITHUB_TOKEN`. A ruleset that requires pull requests on
`main` rejects that push, so this repo cannot adopt PR-required rules, review-thread
resolution, or a `staging` branch while the release flow works this way.

Surfaces: `version-bump.yml`, `ci.yml` triggers, the merge policy in `AGENTINFO.md`,
`scripts/` release helpers, and any branch-name assumption in tests.

## S1 — Choose the release mechanism

**Decided: tag-only releases.** The workflow pushes only the `vX.Y.Z` tag and the GitHub
Release; setuptools-scm reads the package version from the tag. No commit ever reaches
`main`, so the ruleset needs no bypass actor, no GitHub App and no secrets. Rulesets here
contain only branch rules, which a tag push does not trigger. Rejected: a release PR with
auto-merge (a bot commit per release, and the PR needs its own approval path) and a GitHub
App bypass actor (a credential to hold and rotate, for something a tag already does).

Consequences: `pyproject.toml` has no static `version`; `aec.lib.config.VERSION` reads the
installed metadata; `tests/test_release_tag_only.py` pins all of it. An editable install
keeps the version it was installed at until `pip install -e .` runs again.

## S2 — Adopt the rules

1. Create the PR-required ruleset with review-thread resolution on `main`.
2. Create a `staging` branch, point PRs at it, promote to `main` by merge commit, update
   the merge policy and `ci.yml` triggers.

## Done when

A merge to `main` still produces a release, direct pushes to `main` are rejected, and the
repo's ruleset requires review-thread resolution.
