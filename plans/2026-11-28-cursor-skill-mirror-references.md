# Cursor skill mirrors: relative references resolve, and the mirror's audience is explicit

**Status:** planned. Scheduling pending.

**Incumbent (checked 2026-11-28):** `scripts/sync-agents-skills.py` (`map_skill_path`, the `SKILL.md` / `Skill.md` scan) already
generates `.cursor/commands/skills/<skill>.md` from each pinned skill. It copies only the `SKILL.md` text. This plan changes that
generator; it adds no new module.

## Problem

1. The mirror of a skill is one Markdown file, but most skills link to siblings with relative paths (`references/…`, `PROVENANCE.md`,
   `scripts/…`). Under `.cursor/commands/skills/` those paths do not exist, so Cursor reads a command whose checklists and helper
   scripts cannot be opened. Measured on the pin to claude-skills 5b810e0: `orchata.md` links 7 references,
   `adversarial-review.md` 3, `nevar-security-review.md` 3 plus `PROVENANCE.md` and `scripts/finding_id.py`; none resolve.
   Found by the review of aec #197 (P2 on `.cursor/commands/skills/nevar-security-review.md`).
2. Nothing says who the mirror is for. `aec/` never reads `.cursor/commands/skills` (grep, 2026-11-28), so `aec install` does not
   distribute it; it is this repo's own Cursor view of its pinned submodule. The same review raised (P1) that a Nevar-specific skill
   lands in it. Whether a skill belongs in a generic catalog is claude-skills' decision; the mirror should not widen it.

## Root cause

The generator treats a skill as one file. A skill is a directory: `SKILL.md` plus resources it references by relative path.

## Correct fix

1. In the generator, rewrite each relative Markdown link in a mirrored skill to the path that resolves from the mirror's location
   to the pinned source (`../../../.claude/skills/<skill>/<path>`), leaving absolute URLs and in-page anchors alone. The resources
   stay single-sourced in the submodule; nothing is copied.
2. Add a test that walks every `.cursor/commands/skills/**/*.md`, extracts relative links and asserts each resolves to an existing
   file in the checkout (behaviour, not a byte comparison).
3. Regenerate all mirrors in one PR (a generated-files change: take the generator's output, never merge by hand) and check the
   mirror count did not shrink.
4. State the mirror's audience in the generator docstring and in `AGENTINFO.md`: this repo's own Cursor view, not distributed.

## Affected surfaces

`scripts/sync-agents-skills.py`, every file under `.cursor/commands/skills/`, a new test under `tests/`, `AGENTINFO.md`. The
pre-commit sync hook that runs the generator.

## Done when

The new test passes on a fresh checkout, no mirror contains an unresolved relative link, and the generator docstring names the
audience.
