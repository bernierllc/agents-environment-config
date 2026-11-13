# Feedback loop: shared, introspective improvement for skills, agents, hooks, plugins, AEC and the dev process

**Status:** In progress · **Created:** 2026-11-13 · **Repos:** `bernierllc/claude-skills`, `bernierllc/agency-agents`, `bernierllc/agents-environment-config`

## Problem

The orchata skill has a self-improvement loop: when its own instructions cause rework it logs
friction to `~/.claude/orchata/friction.json`, and when a threshold trips it offers to review
the entries with the user and open a PR back to the skill. Nothing else has this. Every other
skill, every agent, every hook, AEC itself and the development process around them (tests, CI,
planning, review) fail silently: the lesson is learned in one session and lost.

The orchata loop also has two defects that block reuse:

1. **Lost writes.** The register is one JSON document rewritten on every log. Two parallel
   subagents logging at once each read, append and write: the last writer wins and the other
   entry is gone.
2. **Bound to one skill.** The protocol (schema, thresholds, verdict block, PR-back flow) lives
   in `orchata/references/friction-register.md`. Copying it into N items means N drifting
   copies.

## Decisions

### One skill: `feedback-loop` (not one per item kind)

The thing receiving feedback (a *subject*) has a `kind`; the protocol is identical for every
kind. A skill per kind (skill-feedback, hook-feedback, …) would carry N copies of the same
protocol, which is exactly the drift problem. `skill-feedback` was rejected as a name because it
reads as skills-only.

Subject kinds:

| kind | name | review target |
|---|---|---|
| `skill` | skill name (`orchata`) | PR to the skill's source repo |
| `agent` | agent name / file stem | PR to the agent's source repo |
| `hook` | `<owning-item>/<hook-id>` | PR to the owning item's source repo |
| `plugin` | plugin name | issue/PR to the plugin's source repo |
| `aec` | `aec` | issue (or PR) on the AEC repo |
| `process` | project slug; entry carries `area` = dev, test, ci, plan, review, deploy | the project itself: a plan file or issue in that repo |

### Storage: one directory per subject, append-only entries

Root: `$AGENT_FEEDBACK_HOME`, default `~/.agent-feedback/`. Not under `~/.claude/` (Codex,
Cursor, Gemini use it too) and not under AEC's home (must work without AEC).

```
~/.agent-feedback/
  config.json                                  # {"enabled": true, "opt_out": ["skill:foo", ...]}
  subjects/<kind>/<name>/entries.jsonl         # append-only; one JSON entry per line
  subjects/<kind>/<name>/state.json            # last_review, source_repo, resolutions
```

- **Entry:** `id` (12-hex sha256 of ts+kind+name+summary), `ts` (ISO-8601 UTC), `kind`, `name`,
  `severity` (high|medium|low), `summary`, optional `suggestion`, `phase`, `area`, `project`,
  `reporter` (agent|cli|hook|human).
- **Append-only** with `O_APPEND` single-line writes: parallel writers never lose an entry. This
  fixes orchata's lost-write defect.
- **State:** `last_review` (date), `source_repo`, `resolutions: {id: {status, pr?, date}}` with
  status `folded` (fix in a PR), `merged` (PR merged; counts as closed), `not-a-problem`,
  `deferred` (still open).
- **Open entry** = no resolution other than `deferred`. Threshold counts open entries dated
  after `last_review`. **Threshold** (unchanged from orchata): any high, or ≥3 medium, or ≥5
  total.
- Nested names (`hook` kind, `process` areas) are path-safe: `/` allowed as a separator,
  `..` and absolute paths rejected.
- Entries are local only. Nothing leaves the machine without the user's explicit consent at
  review time. Summaries must not contain secrets; the script refuses lines matching common
  secret prefixes.

### Toggle

- `config.json` `enabled` is the global switch; `opt_out` lists subjects (`kind:name`) to skip.
  `log` on a disabled/opted-out subject is a no-op that exits 0 (logging must never break the
  calling item).
- The switch lives with the store, not in AEC's preferences, so items read one file they
  already use and it works without AEC. `aec feedback enable|disable` writes this file (see Phase 6).

### Where the capture point lives: inside each item

Feedback is captured at the moment friction happens, so the trigger must be part of the item:
a closing `## Feedback` section in the item's own SKILL.md / agent file, delimited by
`<!-- feedback-loop:begin -->` / `<!-- feedback-loop:end -->` so upstream merges stay
mechanical. Hooks capture in their scripts (code). AEC captures in its own Python (code). AEC
never injects text into installed items or into AGENTS.md / CLAUDE.md.

### Introspection: process feedback

Kind `process` captures friction in how the work itself runs, scoped to a project: slow or flaky
CI, tests that missed a regression, a plan that was wrong about the code, a review loop that
took three rounds. Capture points are built into the skills that own those moments (orchata
retro, ship, pr-merge-flow, playwright-test-runner, plan-review, resume). `feedback.py report
--kind process --name <project>` summarizes by area so the user and their agents can see trends
and turn them into plan files.

## Phases

Each phase is one dispatchable unit (one Tracker row) and one PR.

### P1 — `feedback-loop` skill (claude-skills)

- `feedback-loop/SKILL.md` v1.0.0: when to log, what counts as friction per kind, the review
  conversation (verdict block attributed to the subject and to past runs, Y / N / Never), the
  PR-back / issue / plan-file flow per kind, folding and pruning rules (lifted from orchata).
- `feedback-loop/scripts/feedback.py` (stdlib only): `log`, `status`, `review`, `resolve`,
  `mark-reviewed`, `report`, `config`, `import-orchata`.
- Tests: `scripts/test_feedback_loop.py` (picked up by CI's `unittest discover`), covering
  parallel appends, thresholds, resolutions, disabled/opt-out no-op, path safety, orchata import.
- Manifest regenerated.

### P2 — adopt in our own skills (claude-skills)

Bernier-authored skills get the feedback section (minor bump each):

- `orchata`: replace the private register with `feedback-loop` (kind `skill`, name `orchata`);
  `import-orchata` migrates `~/.claude/orchata/friction.json` on first run; retro also logs
  `process` feedback for the project.
- `ship`, `pr-merge-flow`, `playwright-test-runner`, `plan-review`, `resume`: also log `process`
  feedback for their area (ci, review, test, plan).
- Every other Bernier skill: the standard section.
- **Hooks we ship** (typecheck-on-edit, pr-merge-flow, git-conventions, verification-writer,
  api-verification-writer, playwright-test-generator): log kind `hook` when the hook itself
  malfunctions (crash, missing tool, timeout, unparseable input), never when it correctly
  blocks. Logging is best-effort and never changes the hook's exit code.

### P3 — third-party skills: upstream sync, then adopt (claude-skills)

Upstream: `anthropics/skills` (this repo is a fork).

1. For each `author: Anthropic` skill: add `source: anthropics/skills` (plus `source_path`)
   frontmatter; diff against upstream; merge upstream changes logically (keep our local
   fixes); bump version. **Commit 1.**
2. Add the standard feedback section; bump again. **Commit 2.**

### P4 — agents: upstream sync, then adopt (agency-agents)

Upstream: `msitarzewski/agency-agents` (already recorded in each agent's `source:`).

1. Merge upstream changes for `source: msitarzewski/agency-agents` agents (respecting the fork's
   frontmatter schema; `scripts/add-metadata.py`), add agents new upstream, bump versions.
   **Commit 1.**
2. Add the standard feedback section (kind `agent`) to every agent; bump. **Commit 2.**

### P5 — hooks

Covered inside P2 for hooks we author. AEC's part is in P6 (hook installs need no schema
change: hook feedback is attributed to the owning item, whose source AEC already knows).

### P6 — AEC (agents-environment-config)

- **No AEC preference.** The store's `config.json` is the only switch. A second switch in AEC's
  preferences would drift from it, and a new `OPTIONAL_FEATURES` entry prompts every existing
  user on their next run. `aec feedback enable|disable|opt-out|opt-in` writes that one file.
- **`aec feedback ...`** hands everything to the installed `feedback.py` (one implementation of
  the store), found via `AGENT_FEEDBACK_BIN`, then `~/.claude/skills/feedback-loop/`, then
  `~/.agent-tools/skills/feedback-loop/`. Missing skill: exit 1 with
  `aec install skill feedback-loop`.
- **Self-capture (AEC runs without an agent):** `main()` logs `aec:aec` on an unhandled crash
  (high; summary = command name, exception type, innermost AEC function; no argument values or
  paths) and on an unanswered prompt (medium). AEC writes the entry itself (stdlib, the store's
  format) so a crash is captured even without the skill; `tests/test_feedback.py` checks the
  real `feedback.py` reads it. Best-effort: never masks the original error. Respects
  `enabled` and `opt_out`.
- **Surfacing:** at exit, at most once a day and off under `AEC_NO_UPDATE_CHECK`, AEC asks
  `feedback.py status aec:aec` (which owns the threshold) and prints one line when it is due:
  `aec has feedback due (...): run aec feedback review aec:aec`. Review offers a GitHub issue on
  the AEC repo, created only on explicit consent.

## Done when

- `feedback-loop` is in claude-skills main and installable via `aec install skill feedback-loop`.
- orchata logs through it; its old register is migrated.
- All skills and agents carry the feedback section; third-party items are synced with upstream
  and record their `source`.
- Our hooks log their own malfunctions.
- `aec feedback status` works; an AEC crash produces an `aec` entry; `aec feedback disable` stops it.
