# Org Config Overlay — `install.preferences` and `install.prompts` Allow-Lists

**Status:** Design addendum, awaiting user approval (Task 1 of Phase 1 plan).
**Parent spec:** `2026-05-04-org-config-overlay-design.md`
**Parent plan:** `2026-05-04-org-config-overlay-phase-1.md`
**Resolves:** Open Questions #1 and #2.

This addendum locks the allow-lists referenced by the validator and overlay
applier. Until both lists are frozen, downstream tasks cannot proceed (the
validator schema embeds them, and the overlay applier dispatches on prompt IDs).

---

## 0. Threat model recap (safety criteria)

A key/prompt is "safe" for an org config to set on a user's machine **only if**
all of the following hold:

1. **No exfiltration.** Setting the value cannot cause AEC to send user data to
   an attacker-controlled host.
2. **No fetch redirection.** Setting the value cannot redirect AEC's downloads,
   updates, registry fetches, or skill resolution to attacker-controlled hosts.
3. **No silent code execution.** Setting the value cannot cause AEC to execute
   arbitrary commands or install code without an explicit, separately-gated
   user consent step.
4. **Bounded blast radius on the local filesystem.** Paths must be normalized
   and confined to user-owned locations (not `/etc`, not `/usr/local`, not
   another user's `$HOME`). A path under the user's home is acceptable.
5. **Reversible.** The user must be able to override or reset the value via
   `aec preferences` or by deleting the org config.

Anything that fails one or more criteria is **not allow-listed** — even if
hypothetical org admins would find it convenient.

---

## 1. `install.preferences` allow-list

### 1.1 Audit of all keys currently writeable to `~/.aec/prefs.json`

The preferences file has three top-level sections that hold user-set values:
`optional_rules` (set via `set_preference`), `settings` (set via `set_setting`),
and `configurable_instructions` (set via `set_instruction_config`).

Below is the complete enumeration of every key written today.

#### 1.1.1 `optional_rules.*` (booleans, written via `set_preference`)

Source of truth: `OPTIONAL_FEATURES` registry in `aec/lib/preferences.py:15-60`.

| Key | Type | Where set | Safe for org? | Notes |
|---|---|---|---|---|
| `leave-it-better` | bool | `preferences.check_pending_preferences`, `preferences set` CLI | **Yes** | Pure rule-text toggle. No code execution, no fetches. |
| `update_check` | bool | `check_pending_preferences`, `preferences set` CLI | **Yes** | Controls weekly update-check ping to GitHub. Org may want to disable to avoid noise; cannot be redirected (URL is hard-coded). |
| `port_registry_enabled` | bool | `check_pending_preferences`, `preferences set` CLI | **Yes** | Toggles local `~/projects/ports.json` tracker. No network. |
| `scheduled_tests_enabled` | bool | `check_pending_preferences`, `preferences set` CLI, `test_cmd.py:125` | **Yes (with note)** | Enables local scheduled-test runner. Runs only commands the user defines per-repo; org cannot inject the commands themselves through this key. |
| `discovery_recompare` | bool | `check_pending_preferences`, `preferences set` CLI | **Yes** | Local discovery behavior toggle. |

#### 1.1.2 `settings.*` (arbitrary JSON, written via `set_setting`)

Audited callers: `install.py` (`projects_dir`, `plans_dir`, `plans_gitignored`,
`plans_completion`, `report_viewer`, `report_retention_mode`,
`report_retention_days`), `repo.py` (`hook_mode`, plus reads of
`aec_json_gitignored`), `global_install_prompt.py`
(`global_install_multi_repo_threshold`, `skip_global_install_prompt_for`).

| Key | Type | Where set | Safe for org? | Notes |
|---|---|---|---|---|
| `projects_dir` | string (abs path) | `install._prompt_settings`, `install.py:229` | **Yes (validated)** | Must resolve under `$HOME` after `expanduser().resolve()`. Validator MUST reject paths outside `$HOME`, symlinks, and `..` traversal. |
| `plans_dir` | string (relative dir name) | `install._prompt_settings`, `install.py:247-258` | **Yes (validated)** | Plain directory name (e.g. `.plans`, `plans`). Validator MUST reject path separators (`/`, `\`), absolute paths, and `..`. |
| `plans_gitignored` | bool | `install._prompt_settings:272` | **Yes** | Per-repo `.gitignore` behavior toggle. |
| `plans_completion` | enum: `"archive"` \| `"delete"` | `install._prompt_settings:288` | **Yes (enum)** | Validator enforces enum. |
| `hook_mode` | enum: `"auto"` \| `"per-repo"` \| `"never"` | `repo.py:517` | **Yes (enum)** | Controls lint-hook installation policy. Hooks themselves are still gated by language detection and use AEC-bundled scripts; org cannot point to attacker scripts via this key. |
| `aec_json_gitignored` | bool | currently only read; no writer found in audit | **Yes** | Read-only today, but harmless to allow. |
| `report_viewer` | string (command template) OR enum (viewer key) | `install._prompt_quality_settings:450` | **Needs review — restrict** | Today this can be either a viewer key (e.g. `"open"`) detected via `viewers.detect_viewers()` OR a free-form shell command with `{file}` substitution (`install.py:438-448`). A free-form command is **NOT safe** for an org to set: it is executed by `runner.py:511-513`. **Decision: allow-list ONLY the enumerated viewer keys produced by `detect_viewers()`. Free-form command strings are NOT permitted via org overlay.** Validator must reject anything containing whitespace, `{`, `}`, or shell metacharacters. |
| `report_retention_mode` | enum: `"auto"` \| `"manual"` | `install._prompt_quality_settings:464,475` | **Yes (enum)** | |
| `report_retention_days` | int (1..3650) | `install._prompt_quality_settings:473` | **Yes (bounded)** | Validator enforces int and range. |
| `global_install_multi_repo_threshold` | int (2..50) | not currently written via CLI; read in `global_install_prompt.py:46` | **Yes (bounded)** | Already clamped at read time; validator should mirror the clamp. |
| `skip_global_install_prompt_for` | object: `{"<item_type>:<name>": true}` | `global_install_prompt.dismiss_global_install_prompt:67` | **No — exclude** | This is per-user UX state ("don't ask me again about skill X"). Allowing an org to pre-populate dismissals would silently suppress migration prompts the user has never seen. **Not allow-listed.** Org should use other mechanisms if they want to control global installs. |

#### 1.1.3 `configurable_instructions.*` (per-agent toggle objects, written via `set_instruction_config`)

| Key | Type | Where set | Safe for org? | Notes |
|---|---|---|---|---|
| `session-separation` | object `{<agent_key>: bool}` | `install._prompt_configurable_instructions:365` | **Yes** | Pure instruction-text toggle per agent. |
| (any future `CONFIGURABLE_INSTRUCTIONS` key) | object `{<agent_key>: bool}` | same callsite | **Yes (by construction)** | New keys added to `CONFIGURABLE_INSTRUCTIONS` are auto-allow-listed via the dynamic registry rule below. |

### 1.2 Final allow-list (locked)

The validator MUST embed the allow-list as a **closed schema** with the
following structure. Any key not present is rejected with a clear error.

```yaml
install:
  preferences:
    # optional_rules.*  (bool)
    leave-it-better: bool
    update_check: bool
    port_registry_enabled: bool
    scheduled_tests_enabled: bool
    discovery_recompare: bool

    # settings.*
    projects_dir: path-under-home          # string, expanduser().resolve(), must be under $HOME
    plans_dir: bare-dirname                # string, no separators, no '..', no abs
    plans_gitignored: bool
    plans_completion: enum[archive, delete]
    hook_mode: enum[auto, per-repo, never]
    aec_json_gitignored: bool
    report_viewer: enum-from-detect-viewers   # rejects free-form commands
    report_retention_mode: enum[auto, manual]
    report_retention_days: int[1..3650]
    global_install_multi_repo_threshold: int[2..50]

    # configurable_instructions.* (dynamic — keys come from CONFIGURABLE_INSTRUCTIONS)
    configurable_instructions:
      <key-from-CONFIGURABLE_INSTRUCTIONS>:
        <agent-key-from-get_all_agent_keys()>: bool
```

**Explicitly excluded from the allow-list:**

- `skip_global_install_prompt_for` — dismissal state is user-only.
- Free-form `report_viewer` command strings (only enumerated viewer keys allowed).
- Any key not enumerated above.

### 1.3 Validation rules

The validator (Task 3) MUST:

1. Reject unknown keys with a list of valid keys in the error message.
2. Type-check each value against the schema above.
3. For `projects_dir`, after `Path(value).expanduser().resolve()`, verify the
   result is `Path.home()` or under it; reject otherwise.
4. For `plans_dir`, reject if `os.sep`, `/`, `\`, or `".."` segments appear.
5. For `report_viewer`, reject any value not in
   `{v["key"] for v in detect_viewers()} ∪ {None}`.
6. For `configurable_instructions.<key>`, reject keys not in
   `CONFIGURABLE_INSTRUCTIONS`; reject agent keys not in
   `get_all_agent_keys()`.

---

## 2. `install.prompts` allow-list

### 2.1 Audit of all prompt sites in install/setup flows

Files audited: `aec/commands/install.py`, `aec/commands/setup.py`,
`aec/lib/global_install_prompt.py`, `aec/lib/preferences.py`. (The repo-level
prompts in `aec/commands/repo.py` are out of scope for Phase 1; see §3 note.)

Each row indicates whether the prompt has a stable ID **today**. Where it does
not, this addendum proposes one. Task 2 will introduce these IDs as named
constants in a new `aec/lib/prompt_ids.py` module.

| File:line | Prompt text (abbrev.) | Stable ID today? | Proposed ID | Type | Safe? | Resolved value writes to |
|---|---|---|---|---|---|---|
| `install.py:133` | "Would you like to setup your project directories now?" | No | `install.batch_project_setup.start` | yes/no | **Yes** | (no persistence — controls flow) |
| `install.py:144` | "Scan for projects: 1) git only / 2) all" | No | `install.batch_project_setup.scan_mode` | enum: `git_only` \| `all` | **Yes** | (flow only) |
| `install.py:163` | "Setup {project.name}? (Y/n/q)" | No | `install.batch_project_setup.per_project` | per-project; **NOT allow-listable** (depends on user's project list) | **No — exclude** | per project; cannot be statically pre-answered |
| `install.py:225` | "Where is your projects root directory?" | No | `install.settings.projects_dir` | path | **Yes** | `settings.projects_dir` (also covered by §1) |
| `install.py:242` | "Where should plan files go? 1/2/3" | No | `install.settings.plans_dir` | enum/string | **Yes** | `settings.plans_dir` |
| `install.py:253` | "Plans directory name" (free-form, follow-up to choice 3) | No | `install.settings.plans_dir.custom` | string | **Yes (validated as bare-dirname)** | `settings.plans_dir` |
| `install.py:268` | "Should {plans_dir}/ be tracked in git?" | No | `install.settings.plans_gitignored` | yes/no | **Yes** | `settings.plans_gitignored` |
| `install.py:285` | "When a plan is completed: 1 archive / 2 delete" | No | `install.settings.plans_completion` | enum | **Yes** | `settings.plans_completion` |
| `install.py:341` | "Keep for {agent}?" (per-agent, per-instruction) | No | `install.configurable_instructions.<key>.<agent_key>` | yes/no | **Yes** | `configurable_instructions.<key>.<agent_key>` |
| `install.py:427` | "Choose a viewer [1]" | No | `install.quality.report_viewer` | enum | **Yes (only allow-listed viewer keys)** | `settings.report_viewer` |
| `install.py:444` | "Viewer command [none]" (fallback when no detected viewers) | No | `install.quality.report_viewer.command` | string | **No — exclude** | Same risk as §1: free-form command. Not allow-listable. |
| `install.py:459` | "How should test reports be managed? 1/2" | No | `install.quality.report_retention_mode` | enum | **Yes** | `settings.report_retention_mode` |
| `install.py:466` | "Prune reports after how many days? [30]" | No | `install.quality.report_retention_days` | int | **Yes (bounded 1..3650)** | `settings.report_retention_days` |
| `setup.py:29` | "Track {cwd} as a repo?" | No | `setup.track_current_repo` | yes/no | **Yes** | (flow only, but pre-answering this means "auto-track cwd"; org should be cautious — see refactor note) |
| `global_install_prompt.py:189` | "Convert this to a global install instead?" | No | `install.global_offer.<item_type>:<name>.choice` | yes/no | **Yes (conditional)** | per-item; only meaningful per `(item_type, name)` pair |
| `global_install_prompt.py:217` | "Stop offering for this item?" | No | `install.global_offer.<item_type>:<name>.dismiss` | yes/no | **No — exclude** | Same reasoning as `skip_global_install_prompt_for` — dismissal state is user-only. |
| `preferences.py:186` | Per-`OPTIONAL_FEATURES` prompt (loop) | Yes — `feature["key"]` is the stable ID | `prefs.optional_rules.<key>` | varies | **Yes** | `optional_rules.<key>` (covered by §1) |

### 2.2 Final allow-list (locked)

The org overlay's `install.prompts` block accepts ONLY the following keys:

```yaml
install:
  prompts:
    # Flow control
    install.batch_project_setup.start: yes|no
    install.batch_project_setup.scan_mode: git_only|all

    # Settings (mirror of install.preferences, but expressed as prompt answers)
    install.settings.projects_dir: <path-under-home>
    install.settings.plans_dir: <bare-dirname-or-enum:dotplans|plans|custom>
    install.settings.plans_dir.custom: <bare-dirname>      # only when plans_dir == custom
    install.settings.plans_gitignored: yes|no
    install.settings.plans_completion: archive|delete

    # Configurable instructions (dynamic)
    install.configurable_instructions.<key>.<agent_key>: yes|no

    # Quality infrastructure
    install.quality.report_viewer: <enum-from-detect-viewers>
    install.quality.report_retention_mode: auto|manual
    install.quality.report_retention_days: <int 1..3650>

    # Optional features (dynamic — keys come from OPTIONAL_FEATURES)
    prefs.optional_rules.<key>: yes|no

    # Setup
    setup.track_current_repo: yes|no
```

**Explicitly excluded:**

- `install.batch_project_setup.per_project` — depends on local project list.
- `install.quality.report_viewer.command` — free-form shell command.
- `install.global_offer.*.dismiss` — user-only dismissal state.
- `install.global_offer.*.choice` is **technically allow-listable** but only if
  the org names a specific `(item_type, name)` pair. Phase 1 marks this as
  "deferred" and excludes it from the v1 allow-list to keep scope tight; can be
  added in a later phase if demand exists.

### 2.3 Precedence

When both `install.preferences` and `install.prompts` set the same backing
setting (e.g. `install.preferences.projects_dir` and
`install.prompts.install.settings.projects_dir`), `install.preferences` wins
and the validator emits a warning. This matches the spec's stated precedence
(direct preference write > prompt pre-answer).

---

## 3. Refactors required to enable allow-listing (Task 2 work)

The audit shows that **none of the prompts in install/setup have stable IDs
today** — they are all inline `input(...)` calls. Task 2 must:

1. **Create `aec/lib/prompt_ids.py`** containing the canonical list of prompt
   IDs as string constants. The IDs above (column "Proposed ID") are the
   authoritative names. Tests assert each constant matches the YAML allow-list.

2. **Wrap each `input(...)` call in install.py and setup.py** with a helper
   `prompt(prompt_id, prompt_text, *, type, default, validator)` that:
   - Looks up `prompt_id` in the in-memory org-overlay answers (loaded by the
     applier in Task 4).
   - If found, returns the pre-answered value (after running it through the
     prompt's validator) and prints `Console.info(f"Pre-answered by org config: {prompt_id} = {value}")`.
   - Otherwise, falls through to the existing `input(...)` behavior.

   This is a single seam for the overlay applier to plug into.

3. **Specific call-site refactors** (file:line and prompt_id mapping):

   | Refactor target | Prompt ID to thread through |
   |---|---|
   | `install.py:133` | `install.batch_project_setup.start` |
   | `install.py:144` | `install.batch_project_setup.scan_mode` |
   | `install.py:225` | `install.settings.projects_dir` |
   | `install.py:242` | `install.settings.plans_dir` |
   | `install.py:253` | `install.settings.plans_dir.custom` |
   | `install.py:268` | `install.settings.plans_gitignored` |
   | `install.py:285` | `install.settings.plans_completion` |
   | `install.py:341` | `install.configurable_instructions.<key>.<agent_key>` (dynamic) |
   | `install.py:427` | `install.quality.report_viewer` |
   | `install.py:459` | `install.quality.report_retention_mode` |
   | `install.py:466` | `install.quality.report_retention_days` |
   | `setup.py:29` | `setup.track_current_repo` |
   | `preferences.py:186` | `prefs.optional_rules.<key>` (already keyed by `feature["key"]`; the smallest refactor — just wrap the existing loop in the new helper) |

4. **Explicitly do NOT thread IDs through:**
   - `install.py:163` (per-project loop)
   - `install.py:444` (free-form viewer command — kept as fallback only when no
     viewers detected and no overlay; the overlay path skips it entirely)
   - `global_install_prompt.py:189,217` (deferred)
   - All prompts in `aec/commands/repo.py` (out of scope for Phase 1)

5. **Tests Task 2 must add:**
   - Each prompt ID constant exists and matches the YAML schema.
   - The `prompt()` helper falls through to `input()` when no overlay answer
     is present.
   - When an overlay answer is present, `input()` is NOT called and the
     pre-answered value is returned.
   - Validator rejects allow-listed-but-malformed values (path traversal,
     command injection in viewer, etc.) per §1.3.

6. **Open follow-ups for later phases (not Task 2):**
   - Decide whether to thread IDs through `repo.py` prompts.
   - Decide whether to allow per-`(item_type, name)` global-install pre-answers.
   - Consider an `install.prompts.policy: strict|lenient` knob for orgs that
     want unanswered prompts to fail rather than fall through to interactive.

---

## Summary for review

- **Preference keys allow-listed:** 16 (5 optional_rules + 10 settings + 1 dynamic configurable_instructions namespace).
- **Preference keys explicitly excluded:** 2 (`skip_global_install_prompt_for`, free-form `report_viewer` commands).
- **Prompt sites identified in scope:** 17.
- **Prompt IDs allow-listed:** 13 distinct IDs (some dynamic).
- **Prompt sites excluded:** 4 (per-project loop, free-form viewer command, two global-install dismissal prompts).
- **Refactor scope for Task 2:** new `aec/lib/prompt_ids.py`, new `prompt()` helper, ~12 callsite wraps, plus tests.
