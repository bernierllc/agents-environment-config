# pr-merge-flow honours `pr_open_mode`

**Status:** planned (Tier 2) · **Origin:** PR #100 review (Codex P2, 2026-09-30)
**Priority:** Medium. It affects only users who set `pr_open_mode=draft`; the
default (`ready`, or unset) is unaffected.

## Root cause

Two settings decide the same thing and disagree. `aec install` asks for
`settings.pr_open_mode` (`ready` | `draft`, stored in
`~/.agents-environment-config/preferences.json`), and `aec/commands/rules.py`
renders the git-workflow rule with draft-first wording when it is `draft`. The
`pr-merge-flow` skill (claude-skills) says "PRs open ready for review, never
as drafts" (rule 5), and its PreToolUse guard (`scripts/pr-guard.py`,
`draft_violation`) blocks `gh pr create --draft` and `gh pr ready --undo`
unconditionally. A user who chose draft mode and installs the skill can no
longer open the drafts their rules tell them to open.

## Correct fix (claude-skills, `pr-merge-flow`)

1. **Guard:** `draft_violation` returns False when
   `preferences.json → settings.pr_open_mode == "draft"`. Read it the way aec
   does (`$HOME/.agents-environment-config/preferences.json`; absent, unreadable
   or any other value means `ready`), so the guard keeps failing closed toward
   the documented default.
2. **Skill text:** rule 5 states the default and the setting: "PRs open ready
   for review unless `pr_open_mode` is `draft`". The guard bullet says the same.
3. **Tests:** guard tests for unset, `ready`, `draft` and corrupt
   preferences.json (only `draft` allows `--draft`).
4. Minor version bump (1.1.0), regenerate `skills-manifest.json`, then bump the
   `.claude/skills` submodule here and regenerate `.cursor/commands`.

## Affected surfaces

claude-skills: `pr-merge-flow/SKILL.md`, `pr-merge-flow/scripts/pr-guard.py`,
its tests, `skills-manifest.json`. This repo: `.claude/skills` submodule ref,
`.cursor/commands/skills/pr-merge-flow.md` (generated).

## Considered and rejected

- Rendering the skill per user the way rules are rendered: skills are installed
  as copied directories, not rendered; one runtime read in the guard is smaller
  and keeps the skill identical for every user.

## Done when

With `pr_open_mode=draft`, `gh pr create --draft` passes the guard and the skill
text matches the rendered git-workflow rule; with any other value it is still
blocked.
