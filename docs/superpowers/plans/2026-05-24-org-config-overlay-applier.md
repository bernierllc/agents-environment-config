# Org Config Overlay — Applier (Phase 3) Implementation Plan

> Status: COMPLETE (2026-05-24). All tasks A1–A7 shipped on branch `claude/manifest-features-launch-joqf5`, plus an end-to-end integration test. Implements the overlay *applier* that Phases 1–2 deferred: turning verified, conflict-resolved org policy into real environment changes.

**Goal:** Apply enrolled org policy to the user's environment — preferences, pre-answered prompts, and item installs/blocks — honoring multi-org conflict resolution (P7), managed-vs-guided mode, and rotation lockout. Unlocks the two Phase 2 descopes (`aec install --org-config`, managed/guided apply).

**Reuses (do not rebuild):**
- `aec/lib/apply_core.py` — `DesiredItem` → `plan_apply` → `execute_apply` (the install engine).
- `aec/lib/preferences.py` — `load_preferences`/`save_preferences` (sections: `settings`, `optional_rules`, `configurable_instructions`).
- `aec/lib/prompts.py` — the `prompt(prompt_id, ...)` seam (every install/setup callsite already routes through it).
- `aec/lib/org_config/{reconcile,conflicts,resolutions,rotation,discovery}.py` — Phase 2 multi-org + trust state.

**Out of scope:** new prompt IDs; per-project (`projects[]`) overlays; `enrollment_script`; branding. Blocked-item *removal* of MCP servers beyond manifest (filesystem MCP teardown) is best-effort.

---

## Conventions
TDD, `pytest`, `tmp_path` + injected `home_dir`, conventional commits, full suite (`--cov-fail-under=65`) green before each commit. Reset the two stray submodule bumps before pushing.

## Tasks

### A1 — Effective policy computation (pure, the heart)
New `aec/lib/org_config/effective.py`:
```python
@dataclass(frozen=True)
class EffectivePolicy:
    items: dict[str, tuple[str, ItemPolicy]]   # "type/name" -> (winning_org_id, policy)
    preferences: dict[str, object]             # merged settings/prefs
    prompts: dict[str, object]                 # prompt_id -> answer
    default_sources: dict[str, str]            # type -> stance
    custom_sources: list[CustomSource]
    install_mode: Optional[str]
    held: tuple[str, ...]                       # subjects held pending resolution (P7)
```
`effective_policy(paths) -> EffectivePolicy`:
- discover orgs; `open_conflicts(paths)` → held subjects (map conflict→subject string).
- For each category, merge across orgs; for any subject with a **resolved** conflict apply the decision (`honor:<org>` picks that org's value; `skip` drops it); **open** conflict → add to `held`, omit.
- Subject→conflict mapping mirrors `conflicts.py` subjects (`type/name`, `preference.<k>`, `sources.default.<t>`, `install.mode`).
- [x] Tests: single org passthrough; two-org agreement merges; open stance conflict → item held + excluded; resolved `honor:acme` → acme's value wins; `skip` → omitted; custom_sources unioned.

### A2 — Prompt registry wired into the seam
Extend `aec/lib/prompts.py`: module-level registry + `set_overlay_answers(dict)` / `clear_overlay_answers()`. `prompt()` consults it by `prompt_id`, runs `validator`, emits `Console.info("Pre-answered by org config: <id>")`, else falls through to `input()`.
- [x] Tests: registered id returns pre-answer (no stdin); unregistered falls through; validator applied; bool/int coercion via `type`.

### A3 — Apply preferences + prompts
`apply.py`: `apply_preferences(policy)` writes merged prefs into the right `prefs.json` sections via `save_preferences` (key→section routing using `KNOWN_PREFERENCE_KEYS`); `apply_prompts(policy)` calls `set_overlay_answers`.
- [x] Tests: org `projects_dir` lands in `settings.projects_dir`; optional_rules routed; prompts registered.

### A4 — Apply items (install intents + blocked removal)
`apply.py`: `compile_desired_items(policy, scope)` → `DesiredItem`s for `required/recommended/pinned` (pinned → exact version); run `plan_apply`/`execute_apply`. `blocked` → uninstall if present (manifest + filesystem) via existing uninstall primitive. `silent`/`recommended` honor mode.
- [x] Tests: required → install plan entry; pinned → version_spec; blocked present → removal; blocked absent → noop; held items never appear.

### A5 — Orchestrator + mode + lockout
`apply.py`: `apply_org_policy(paths, *, mode_override=None, prompt=...)`:
- run `run_propagation_gate`; if any org **locked** → refuse with message (exit non-zero).
- compute `effective_policy`; `install_mode` managed → apply silently; guided → show diff/plan and prompt y/N before applying.
- print P7 summary: "N applied, M held pending `aec org resolve`".
- [x] Tests: managed applies silently; guided declined → no changes; locked → refuses; held count surfaced.

### A6 — CLI surface
- `aec org apply [--dry-run]` command (drives A5).
- Wire `aec install --org-config <url|path>` = `perform_enroll` then `apply_org_policy` (closes Phase 2 descope).
- [x] Tests: `aec org apply` dry-run prints plan; `--org-config` enroll+apply.

### A7 — Docs
Update `docs/users/org-configs.md` + `docs/orgs/authoring-org-configs.md`: how policy is applied, managed vs guided, blocked-item removal, `aec org apply`.

## Definition of done
Enrolled (and conflict-resolved) org policy applies via `aec org apply` and `aec install --org-config`: preferences written, prompts pre-answered, required/pinned installed, blocked removed, conflicting items held (P7), guided prompts / managed silent, rotation-locked orgs refused. Suite green ≥65%.
