# Archived Plans

Plans that have shipped are moved here so the active `plans/` directory stays
focused on in-flight and pending work. Each archived plan retains a status
header noting the shipping PR and date.

## How to archive a plan

```bash
git mv docs/superpowers/plans/<file>.md docs/superpowers/plans/archive/<file>.md
```

Before moving, prepend a status line at the very top of the file:

```
> Status: shipped via PR #<N> on YYYY-MM-DD
```

## Pending physical moves (2026-05-19 PM audit)

The status headers below have already been prepended in-place; the files still
sit in `docs/superpowers/plans/` and need to be moved into this directory by
the maintainer (the PM-agent environment had no shell access to `git mv`):

- `2026-03-30-plan-review-skill.md` — shipped (no PR# captured)
- `2026-04-04-brew-aligned-cli-redesign.md` — shipped multi-commit
- `2026-05-02-git-setup-phase.md` — PR #39
- `2026-05-04-org-config-overlay-phase-1.md` — PR #47 + #48
- `2026-05-12-aec-agent-blurb.md` — PR #50
- `2026-05-19-org-config-overlay-phase-2.md` — PR #54 (skeleton, superseded)
- `2026-05-24-org-config-overlay-phase-2-remaining.md` — PR #54
- `2026-05-24-org-config-overlay-applier.md` — PR #54

To complete the archive:

```bash
cd /Users/mattbernier/projects/agents-environment-config
git mv docs/superpowers/plans/2026-03-30-plan-review-skill.md            docs/superpowers/plans/archive/
git mv docs/superpowers/plans/2026-04-04-brew-aligned-cli-redesign.md    docs/superpowers/plans/archive/
git mv docs/superpowers/plans/2026-05-02-git-setup-phase.md              docs/superpowers/plans/archive/
git mv docs/superpowers/plans/2026-05-04-org-config-overlay-phase-1.md   docs/superpowers/plans/archive/
git mv docs/superpowers/plans/2026-05-12-aec-agent-blurb.md              docs/superpowers/plans/archive/
git commit -m "docs(plans): archive shipped plans"
```
