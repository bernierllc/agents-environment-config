# Git Setup Phase Design

**Date:** 2026-05-02  
**Status:** Approved  
**Scope:** `aec repo setup` — new early git detection phase, provider registry, gitignore submodule, essentials checklist, commit strategy prompt, submodule registry refactor, and contributor docs.

---

## Problem

`aec repo setup` has no awareness of version control beyond appending AEC patterns to `.gitignore` unconditionally. Users get no help scaffolding standard git hygiene files (dependabot, PR templates, CI workflows, CODEOWNERS, etc.), and the `.gitignore` step fires even for non-git projects. The submodule management system is hardcoded in three separate places, making it fragile to extend.

---

## Goals

- Detect git presence early and gate all git-aware behavior on it.
- Offer a multi-select checklist of missing git essentials, diffed against what the project already has.
- Support GitHub first; make adding GitLab, Bitbucket, etc. a one-dict-entry operation using the same registry pattern as languages and test frameworks.
- Bundle gitignore templates via a `toptal/gitignore` git submodule (MIT licensed) with composite joining.
- Absorb the existing `_update_gitignore()` step — AEC patterns are only added when the user has git and consents.
- Give users control over how AEC handles git commits for files it creates.
- Refactor submodule management to a single registry so adding a submodule never requires touching Python or shell scripts.
- Add contributor docs for test frameworks and git providers.

---

## Non-Goals

- Supporting non-GitHub providers in this iteration (architecture ready for them, no implementation).
- Troubleshooting git issues for the user beyond a practical error message.
- Modifying existing git history or remote configuration.
- Branch protection rules (requires `gh` API calls with auth — deferred).

---

## New Files & Modules

| Path | Purpose |
|------|---------|
| `aec/lib/git_providers.py` | `GIT_PROVIDERS` registry + `detect_git_provider()` + `scan_git_essentials()` |
| `aec/lib/git_setup.py` | Setup orchestration: detection, `git init` offer, checklist, commit strategy, file writing |
| `aec/templates/gitignore/` | `toptal/gitignore` git submodule mount point |
| `aec/templates/gitignore/supported.json` | Maps detected language/framework keys → gitignore template names |
| `aec/templates/git/github/` | Bundled template files for GitHub essentials |
| `docs/contributors/adding-git-provider-support.md` | New contributor guide |
| `docs/contributors/adding-test-framework-support.md` | New contributor guide |

**Modified files:**

| Path | Change |
|------|--------|
| `aec/commands/repo.py` | Call `run_git_phase()` early; make `.gitignore` step conditional; add git essentials creation + commit strategy steps |
| `aec/commands/install.py` | Drive submodule loop from `sync-config.json` instead of hardcoded paths |
| `scripts/push-submodules.sh` | Read `SUBMODULES` array from `sync-config.json` via `jq` |
| `scripts/sync-config.json` | Add `gitignore` submodule entry |
| `.gitmodules` | Add `toptal/gitignore` submodule |
| `docs/contributors/adding-hook-support.md` | Add cross-references to new contributor docs |

---

## Submodule Registry Refactor

### Current state (fragile)

Adding a submodule requires touching three files:
1. `.gitmodules` (git requirement)
2. `aec/commands/install.py` — hardcoded path checks at lines 489 and 499
3. `scripts/push-submodules.sh` — hardcoded `SUBMODULES` array at line 20

### Target state (registry-driven)

`scripts/sync-config.json` becomes the single source of truth. Every submodule has one entry:

```json
{
  "submodules": {
    "agents": {
      "path": ".claude/agents",
      "display_name": "agents",
      "repo": "bernierllc/agency-agents",
      "cursor_target": ".cursor/commands/agents"
    },
    "skills": {
      "path": ".claude/skills",
      "display_name": "skills",
      "repo": "bernierllc/skills",
      "cursor_target": ".cursor/commands/skills",
      "skill_file_pattern": ["Skill.md", "SKILL.md"]
    },
    "gitignore": {
      "path": "aec/templates/gitignore",
      "display_name": "gitignore templates",
      "repo": "toptal/gitignore",
      "cursor_target": null
    }
  }
}
```

**`install.py`** iterates `submodules` entries and uses `display_name` for log output ("Updating {display_name}...", "{display_name} updated to {commit}"). When `cursor_target` is `null`, the cursor sync step is skipped for that entry — no error.

**`push-submodules.sh`** reads paths via `jq '.submodules | to_entries[].value.path'`. `jq` is a required system dependency for this script; if not found, the script prints a clear error: `"jq is required for submodule management. Install with: brew install jq (macOS) / apt install jq (Linux)"` and exits non-zero. A Python-based fallback (`python3 -c "import json,sys; ..."`) is not used — requiring `jq` is simpler and `jq` is universally available on supported platforms.

Adding a future submodule = one JSON entry + `.gitmodules` entry. No Python or shell edits required.

---

## `GIT_PROVIDERS` Registry

**File:** `aec/lib/git_providers.py`

```python
GIT_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "github": {
        "display_name": "GitHub",
        "detect_files": [".github/"],
        "detect_commands": ["gh"],
        "detect_env_vars": ["GITHUB_TOKEN", "GH_TOKEN"],
        "essentials": {
            ".gitignore": {
                "display": ".gitignore (language-aware, with AEC patterns)",
                "check": lambda d: (d / ".gitignore").exists(),
                "template": None,  # built dynamically from supported.json
            },
            "README.md": {
                "display": "README.md",
                "check": lambda d: (d / "README.md").exists(),
                "template": "github/README.md",
            },
            "dependabot": {
                "display": "Dependabot config (.github/dependabot.yml)",
                "check": lambda d: (d / ".github/dependabot.yml").exists(),
                "template": "github/dependabot.yml",
            },
            "pr_template": {
                "display": "PR template (.github/PULL_REQUEST_TEMPLATE.md)",
                "check": lambda d: (d / ".github/PULL_REQUEST_TEMPLATE.md").exists(),
                "template": "github/PULL_REQUEST_TEMPLATE.md",
            },
            "issue_templates": {
                "display": "Issue templates (.github/ISSUE_TEMPLATE/)",
                "check": lambda d: (d / ".github/ISSUE_TEMPLATE").exists(),
                "template": "github/ISSUE_TEMPLATE/",
            },
            "ci_workflow": {
                "display": "CI workflow (.github/workflows/ci.yml)",
                "check": lambda d: (d / ".github/workflows").exists(),
                "template": "github/workflows/ci.yml",
            },
            "license": {
                "display": "LICENSE file",
                "check": lambda d: any(d.glob("LICENSE*")),
                "template": "github/LICENSE",
            },
            "editorconfig": {
                "display": ".editorconfig",
                "check": lambda d: (d / ".editorconfig").exists(),
                "template": "github/.editorconfig",
            },
            "codeowners": {
                "display": "CODEOWNERS (.github/CODEOWNERS)",
                "check": lambda d: (d / ".github/CODEOWNERS").exists(),
                "template": "github/CODEOWNERS",
            },
        },
    },
    # To add GitLab, Bitbucket, etc: add an entry here with the same shape.
    # See docs/contributors/adding-git-provider-support.md
}
```

**Detection function** (`detect_git_provider(project_dir) -> str | None`):
- If no `.git/` directory: return `None`
- Iterate `GIT_PROVIDERS`; check `detect_files`, then `detect_commands` (`shutil.which`), then `detect_env_vars` (`os.environ`)
- First match wins; return provider key
- No match: return `"unknown"`

**Scan function** (`scan_git_essentials(project_dir, provider_key) -> dict`):
- Returns `{"item_key": "found" | "missing"}` for every entry in `GIT_PROVIDERS[provider_key]["essentials"]`

---

## Setup Flow

```
aec repo setup
│
├── [existing] Path input + validation
├── [existing] Repo exists / clone / create
│
├── ── GIT PHASE (new, runs early) ──────────────────────────────
│   │
│   ├── detect_git_provider(project_dir)
│   │   ├── .git/ present → identify provider (github / unknown)
│   │   └── no .git/ → "Do you intend to use GitHub? (Y/n)"
│   │       ├── yes → "Want AEC to run git init? (Y/n)"
│   │       │   ├── success → provider = "github", git_enabled = True
│   │       │   └── failure → print practical steps
│   │       │               + "Ask {agent_name} to help troubleshoot"
│   │       │                 (agent_name = first key from detect_agents(),
│   │       │                  fallback "your AI agent" if none detected)
│   │       │               → git_enabled = False, skip git phase
│   │       └── no  → git_enabled = False, skip git phase
│   │
│   ├── provider == "unknown":
│   │   → "Git detected but provider not identified — skipping git essentials.
│   │      To add support for your provider, see
│   │      docs/contributors/adding-git-provider-support.md"
│   │   → git_enabled = False
│   │
│   └── git_enabled == True:
│       ├── scan_git_essentials(project_dir, provider)
│       ├── Display found items (informational)
│       ├── Multi-select checklist of MISSING items
│       │   "Select items for AEC to create
│       │    (comma-separated numbers, 'all', or 'none') [all]: "
│       └── Store → git_config {provider, items_to_create}
│
├── [existing] Create directories
├── [existing] Migrate legacy plans
├── [existing] Copy agent files
├── [existing] Copy optional rules
├── [existing] Setup lint hooks
├── [existing] Create .aec.json
├── [existing] Detect test suites   ← language/framework data now available
├── [existing] Register ports
├── [existing] Sync installed section
├── [existing] Save .aec.json
│
├── ── GITIGNORE STEP (absorbed from former step 9) ─────────────
│   │  (placed here so detected languages/frameworks from test suite
│   │   detection are available for composite gitignore joining)
│   └── if git_enabled and ".gitignore" in git_config.items_to_create:
│       ├── composite gitignore from detected languages via supported.json
│       ├── append AEC patterns (former _update_gitignore behavior)
│       └── write / merge into existing .gitignore
│       (skipped entirely if not git_enabled or user did not select it)
│
├── ── GIT ESSENTIALS CREATION (new) ────────────────────────────
│   └── if git_enabled and items_to_create (excluding .gitignore,
│       which was already written in the GITIGNORE STEP above):
│       ├── create each selected file from bundled templates
│       └── commit preference prompt:
│           "How should AEC handle git commits for files it created?"
│           1. One commit at the end [default]
│           2. Incremental commits per file
│           3. Stage only (git add, you commit)
│           4. No git operations
│           → execute chosen strategy
│           → on failure: print git error + "Ask {agent_name} to help"
│             where agent_name = first key from detect_agents(),
│             fallback to "your AI agent" if none detected
│
├── [existing] Manage .aec.json gitignore
├── [existing] Inject port registry info
├── [existing] Log setup
└── [existing] Raycast scripts + Discovery scan
```

---

## Gitignore Templates

**Submodule:** `toptal/gitignore` mounted at `aec/templates/gitignore/` (MIT license).

**`supported.json`** maps AEC-detected keys to gitignore.io template names:

```json
{
  "languages": {
    "typescript": ["node", "typescript"],
    "python": ["python"],
    "rust": ["rust"],
    "go": ["go"],
    "ruby": ["ruby"]
  },
  "frameworks": {
    "nextjs": ["nextjs", "node"],
    "jest": ["node"],
    "pytest": ["python"]
  }
}
```

**Composite join:** for each detected language/framework, look up template names, read the corresponding files from the submodule, deduplicate lines, concatenate with section headers (matching gitignore.io's format), then append AEC-specific patterns at the end with a `# AEC` section comment.

**Credit:** Template files sourced from [gitignore.io](https://www.toptal.com/developers/gitignore) / [toptal/gitignore](https://github.com/toptal/gitignore) (MIT License).

---

## Error Handling

| Scenario | Behavior |
|---------|---------|
| `git init` fails | Print stderr + practical install hint (`brew install git` / `apt install git`) + "Ask {agent_name} to help troubleshoot if this doesn't help." (`agent_name` = first key from `detect_agents()`, fallback `"your AI agent"`). Set `git_enabled = False`, continue setup. |
| Unknown git provider | Print message with link to `docs/contributors/adding-git-provider-support.md`. Set `git_enabled = False`, continue setup. |
| Existing non-empty file | `check` lambda returns "found" → never appears in checklist → never overwritten. |
| Commit/stage failure | Print git error verbatim + "Ask {agent_name} to help troubleshoot." (`agent_name` resolved same as above.) Continue setup. |
| Non-git project opting out | `git_enabled = False` for this run only. Not persisted to `.aec.json` or preferences. |
| gitignore submodule missing | Warn user submodule not initialized, suggest `aec install`, fall back to AEC patterns only. |

---

## Testing

All tests use real filesystem operations (temp directories, real git repos). Mocks only for external processes (`subprocess` in `git init` failure path) and `shutil.which` in provider detection.

**`tests/lib/test_git_providers.py`**
- Registry integrity: every entry has required keys; all `check` lambdas callable; all non-`None` template paths exist on disk
- `detect_git_provider()`: temp dirs with/without `.github/`, `gh` on PATH, env vars set
- `scan_git_essentials()`: returns correct found/missing splits against real file presence

**`tests/lib/test_git_setup.py`**
- `git init` success and failure paths (failure via mocked subprocess)
- Checklist display: found items shown informational, missing items selectable
- Each commit strategy verified via `git log` / `git status` on a real temp repo
- `.gitignore` composite join: correct content for single and multi-language projects

**`tests/templates/test_gitignore_templates.py`**
- `supported.json` references only template files that exist in the submodule
- Composite join produces non-empty, deduplicated output per detected language

**`tests/commands/test_install_submodules.py`**
- Submodule loop in `install.py` is driven by `sync-config.json`, not hardcoded
- Adding a JSON entry causes it to be processed without touching Python
- `cursor_target: null` entries are skipped for cursor sync without error

**`tests/scripts/test_push_submodules.sh`** (shellcheck + functional)
- Script reads submodule paths from `sync-config.json` via `jq`, not from hardcoded array
- Script exits with a clear error message if `jq` is not installed
- Validated via `shellcheck scripts/push-submodules.sh` in CI

---

## Contributor Docs

**`docs/contributors/adding-git-provider-support.md`** — covers:
- `GIT_PROVIDERS` dict shape and all required fields
- `essentials` entry format (`display`, `check`, `template`)
- Adding bundled template files to `aec/templates/git/{provider}/`
- Note: submodule entries in `sync-config.json` are only for third-party template sources (e.g., `toptal/gitignore`). Standard provider additions use bundled files only and do not require a submodule entry.
- Test requirements

**`docs/contributors/adding-test-framework-support.md`** — covers:
- `TEST_FRAMEWORK_HOOKS` dict shape and detection fields (`detect_files`, `detect_package_json`, `detect_pyproject`)
- Helper function pattern for new manifest formats
- Test requirements

**`docs/contributors/adding-hook-support.md`** — updated to add cross-reference links to both new docs.
