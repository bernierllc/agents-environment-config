# Headless prompts — every AEC prompt answerable without a TTY

**Status:** Approved — Tier 1 (Now)
**Created:** 2026-08-18
**Branch:** `feat/headless-prompts`

## Problem

AEC has **75 interactive callsites** across 19 files (`input()`, `typer.prompt`,
`typer.confirm`). An agent driving AEC on a user's behalf cannot:

1. **Know what will be asked** before running a command — there is no way to
   enumerate the questions, their types, defaults, or valid choices.
2. **Answer them** — only `--yes` exists, and only on some commands. `--yes`
   collapses every question to one blunt "accept", which is wrong for
   value-bearing prompts (paths, times, retention days, multi-selects).
3. **Fail safely** — with stdin closed, most callsites raise `EOFError`
   (uncaught → traceback) or silently take a default and perform a side effect
   the user never approved. `aec test schedule -g` under `/dev/null` registers
   an OS-level launchd/cron job with no confirmation.

The goal is that an agent can ask AEC "what will you ask me?", supply the
answers, and run the command unattended — while a human running the same
command interactively sees no change at all.

## Existing seam (reuse, do not rebuild)

`aec/lib/prompts.py` already defines the right interface:

```python
prompt(prompt_id, prompt_text, *, type="string", default=None, validator=None) -> str
```

with stable IDs in `aec/lib/prompt_ids.py`, a type vocabulary in
`aec/lib/org_config/allow_lists.py` (`yes_no`, `enum[a,b]`, `int[1..3650]`,
`path`, `bare-dirname`), and an in-process pre-answer registry populated by
`aec/lib/org_config/apply.py:apply_prompts()`.

It was built for org-config overlays and wired into **4 callsites** (2 in
`install.py`, 1 in `setup.py`, 1 in `preferences.py`). The remaining 71 bypass
it. This plan finishes the job and generalizes the answer source beyond org
policy.

### Latent bug found while surveying

`prompts._coerce()` returns a real `bool`/`int` for `type="bool"`/`"int"`,
but every callsite does `.strip().lower()` on the result. A JSON overlay
answer of `true` for `install.settings.plans_gitignored` would raise
`AttributeError: 'bool' object has no attribute 'strip'`. The seam must always
return a **normalized string**. Fixed in Phase 1.

## Design

### 1. Answer sources and precedence (`aec/lib/prompts.py`)

Highest wins:

1. Org-config overlay answers (existing `set_overlay_answers`)
2. Explicit answers: `--answers <file.json>` or `AEC_ANSWERS=<file.json>` or
   `AEC_ANSWER_<PROMPT_ID>` env var (dots → underscores, uppercased)
3. Interactive `input()` — only when stdin is a TTY and `--non-interactive`
   was not passed
4. Declared default — only when `--defaults` (or the existing `--yes`) is
   explicitly passed

`prompt()` always returns `str`. Booleans normalize to `"y"`/`"n"`, ints to
their decimal string, so no callsite parsing changes.

### 2. Non-interactive behavior — fail loud, never guess

Non-interactive means: `--non-interactive`, `AEC_NONINTERACTIVE=1`, or
`not sys.stdin.isatty()`.

| Case | Behavior |
|---|---|
| Answer available | Use it. Validate against the declared type; invalid → error naming the ID and the expected type. |
| No answer, `--defaults`/`--yes` passed, prompt not sensitive | Use declared default, log `Console.info("defaulted: <id> = <value>")`. |
| No answer, no `--defaults` | **Exit non-zero** with the prompt ID, its type, its default, and the exact `--answers` key to set. |
| No answer, prompt is `sensitive` | **Always exit non-zero**, even with `--defaults`/`--yes`. |

Per repo policy (no fallback shims, no silent masks) the default posture is
strict failure, not silent defaulting. The error is written to be
agent-actionable — it names the missing key and how to supply it.

`sensitive: true` covers prompts that must never be machine-answered by
accident: the org key-fingerprint confirmations (`aec/commands/org.py:148,192`),
the unsigned-config risk acknowledgement (`org.py:270`), and destructive
removals (`org.py:486`, `untrack.py:22`, `agent_tools.py:320`). These can still
be answered explicitly via `--answers`, but never by `--yes`.

### 3. Catalog for discovery (`aec/lib/prompt_catalog.py`)

An agent must know the questions *before* running the command, so the catalog
is declarative data, not runtime introspection. One entry per prompt ID:

```python
"test.schedule.global.time": PromptSpec(
    command="test schedule -g",
    summary="Daily run time for the global scheduled test job",
    type="time24",
    default="02:00",
    sensitive=False,
)
```

Prompt *text* stays at the callsite (it carries runtime f-string context);
the catalog carries everything an answerer needs. Drift is prevented by a
test that AST-scans every `prompt()` call in `aec/` and asserts the ID set
matches the catalog exactly, in both directions.

### 4. Discovery command (`aec prompts`)

- `aec prompts list [--command <cmd>] [--json]` — every prompt: ID, command,
  type, default, choices, sensitive, summary
- `aec prompts template <cmd>` — skeleton answers JSON pre-filled with
  defaults, ready to edit and pass to `--answers`
- `aec prompts check <file.json>` — validate an answers file (unknown IDs,
  type violations) without running anything

Agent workflow becomes:
`aec prompts template install > a.json` → edit → `aec install --answers a.json --non-interactive`

### 5. Global CLI options (`aec/cli.py`)

`--answers PATH`, `--non-interactive`, `--defaults` registered once on the
root parser, wired through both the typer and the argparse code paths that
`cli.py` maintains in parallel.

### 6. The one non-prompt blocker: the schedule REPL

`aec/lib/test_schedule_repo.py:146` is an interactive command loop
(`schedule>`), not a prompt — it cannot be expressed as an answers map. It
gets non-interactive flags instead, and the REPL stays for humans:

`aec test schedule --add <suite> --remove <suite> --merge --new "NAME :: CMD" --list`

## Phases

Split by **file ownership** so the callsite conversions can run as parallel
agents without shared-file collisions (per repo parallel-agent policy).

### Phase 1 — Engine (single agent, no parallelism)
Everything else depends on this landing first.
- `aec/lib/prompts.py`: answer sources, precedence, always-string return,
  `_coerce` bool bug fix, non-interactive detection, strict-failure errors,
  type validation.
- `aec/lib/prompt_catalog.py`: `PromptSpec` + catalog seeded with the 11
  existing static IDs.
- `aec/cli.py`: three global options.
- Tests: precedence, normalization, strict failure, sensitive-prompt refusal,
  env-var answers, invalid-type errors.

### Phase 2 — Callsite conversion (parallel, one agent per file group)
Each agent converts its files to `prompt()` + adds catalog entries + tests.
No two agents touch the same file.

| Agent | Files | Callsites |
|---|---|---|
| A | `aec/commands/repo.py` | 15 |
| B | `aec/commands/install_cmd.py`, `aec/commands/install.py` | 10 |
| C | `aec/commands/skills.py`, `aec/commands/apply_cmd.py` | 8 |
| D | `aec/commands/configure_agent.py`, `aec/commands/agent_tools.py` | 9 |
| E | `aec/commands/uninstall.py`, `aec/commands/untrack.py` | 7 |
| F | `aec/commands/org.py`, `aec/lib/org_config/apply.py` | 7 |
| G | `aec/commands/test_cmd.py`, `aec/commands/test_detect_impl.py` | 5 |
| H | `aec/commands/discover_catalog.py`, `aec/commands/discover.py` | 5 |
| I | `aec/commands/upgrade.py`, `aec/lib/dep_approval_prompt.py`, `aec/lib/global_install_prompt.py` | 8 |

`aec/lib/prompt_catalog.py` is touched by every agent → **catalog entries are
appended as one-entry-per-file modules** (`aec/lib/prompt_catalog/<area>.py`)
aggregated by `__init__.py`, so no agent edits a shared file. This mirrors the
"separate files per concern for parallel agent safety" rule.

### Phase 3 — Discovery + REPL
- `aec prompts list|template|check`
- `aec test schedule` non-interactive flags
- Drift test (AST scan vs. catalog)
- `docs/` page: headless usage for agents

## Verification

- Every command in `aec --help` runs to completion under
  `< /dev/null --non-interactive --answers <template>` in CI, or exits
  non-zero with a named missing prompt ID. No tracebacks, no silent side
  effects.
- Interactive behavior is byte-identical: a regression test drives the old
  and new code paths with scripted stdin and diffs the output.
- The drift test keeps catalog and callsites in sync.

## Open question

Roadmap placement — this is a prerequisite for the Tier-3 "AEC packages +
agent-native onboarding" initiative ("today users and their agents drive AEC
by remembering commands"), but it is independently useful now.
