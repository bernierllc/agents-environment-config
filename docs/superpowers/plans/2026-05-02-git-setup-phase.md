# Git Setup Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an early git detection phase to `aec repo setup` that detects or initializes git, identifies the provider (GitHub first), diffs missing essentials, and offers a multi-select checklist — while refactoring submodule management to a single JSON registry.

**Architecture:** A new `aec/lib/git_providers.py` holds the `GIT_PROVIDERS` dict registry (same shape as `LANGUAGE_HOOKS`), a new `aec/lib/git_setup.py` orchestrates the interactive phase, and `aec/commands/repo.py` is updated to call the phase early and absorb the existing `_update_gitignore()` call. Submodule management is extracted from hardcoded paths in `install.py` and `push-submodules.sh` into `scripts/sync-config.json`.

**Tech Stack:** Python 3.10+, stdlib only (`pathlib`, `shutil`, `subprocess`, `json`, `os`). Shell: bash + `jq` (required for `push-submodules.sh`). Testing: pytest with real filesystem/git operations.

**Spec:** `docs/superpowers/specs/2026-05-02-git-setup-phase-design.md`

---

## File Map

### New files
- `aec/lib/git_providers.py` — `GIT_PROVIDERS` registry, `detect_git_provider()`, `scan_git_essentials()`
- `aec/lib/git_setup.py` — interactive setup orchestration, gitignore composition, essentials writing, commit strategy
- `aec/templates/gitignore/supported.json` — maps AEC language/framework keys → gitignore template filenames
- `aec/templates/git/github/README.md` — bundled README template
- `aec/templates/git/github/dependabot.yml` — bundled Dependabot config
- `aec/templates/git/github/PULL_REQUEST_TEMPLATE.md` — bundled PR template
- `aec/templates/git/github/ISSUE_TEMPLATE/bug_report.md` — bundled issue template
- `aec/templates/git/github/ISSUE_TEMPLATE/feature_request.md` — bundled issue template
- `aec/templates/git/github/workflows/ci.yml` — bundled starter CI workflow
- `aec/templates/git/github/LICENSE` — bundled MIT license (placeholder year/author)
- `aec/templates/git/github/.editorconfig` — bundled .editorconfig
- `aec/templates/git/github/CODEOWNERS` — bundled CODEOWNERS skeleton
- `tests/lib/test_git_providers.py` — registry + detection tests
- `tests/lib/test_git_setup.py` — orchestration + commit strategy tests
- `tests/templates/test_gitignore_templates.py` — supported.json + composite join tests
- `tests/commands/test_install_submodules.py` — install.py submodule loop tests
- `docs/contributors/adding-git-provider-support.md` — contributor guide
- `docs/contributors/adding-test-framework-support.md` — contributor guide

### Modified files
- `scripts/sync-config.json` — add `display_name` to existing entries; add `gitignore` submodule entry
- `scripts/push-submodules.sh:19` — replace hardcoded `SUBMODULES` array with `jq`-driven read; add `jq` guard
- `aec/commands/install.py:488-506` — replace hardcoded submodule blocks with loop over `sync-config.json`
- `aec/commands/repo.py:1046-1047` — remove `_update_gitignore()` call; add `run_git_phase()` call early; add gitignore + essentials steps after test suite detection
- `.gitmodules` — add `toptal/gitignore` submodule entry
- `docs/contributors/adding-hook-support.md` — add cross-reference links to new docs

---

## Task 1: Refactor submodule registry in sync-config.json

**Files:**
- Modify: `scripts/sync-config.json`

- [ ] **Step 1: Add `display_name` to existing entries and add `gitignore` entry**

Replace the full `submodules` block in `scripts/sync-config.json`:

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
  },
  "pr_settings": {
    "base_branch": "main",
    "title_template": "Sync {type}: {filename}",
    "body_template": "Automated sync from agents-environment-config"
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('scripts/sync-config.json')); print('valid')"
```

Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add scripts/sync-config.json
git commit -m "chore(submodules): add display_name fields and gitignore entry to sync-config"
```

---

## Task 2: Refactor install.py to iterate sync-config.json

**Files:**
- Modify: `aec/commands/install.py:488-506`
- Test: `tests/commands/test_install_submodules.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/commands/test_install_submodules.py`:

```python
"""Tests that install.py submodule loop is driven by sync-config.json."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SYNC_CONFIG_PATH = Path(__file__).parent.parent.parent / "scripts" / "sync-config.json"


class TestSyncConfigDriven:
    def test_sync_config_has_submodules(self):
        """sync-config.json must have a submodules block."""
        config = json.loads(SYNC_CONFIG_PATH.read_text())
        assert "submodules" in config
        assert len(config["submodules"]) > 0

    def test_each_submodule_has_required_fields(self):
        """Every submodule entry must have path, display_name, repo."""
        config = json.loads(SYNC_CONFIG_PATH.read_text())
        for key, entry in config["submodules"].items():
            assert "path" in entry, f"{key} missing path"
            assert "display_name" in entry, f"{key} missing display_name"
            assert "repo" in entry, f"{key} missing repo"
            assert "cursor_target" in entry, f"{key} missing cursor_target"

    def test_install_does_not_hardcode_submodule_paths(self):
        """Anti-regression guard: install.py must not have hardcoded submodule paths.

        This checks source text rather than runtime behavior because the behavioral
        path (actually running update_submodule on a real submodule) requires a full
        git checkout environment. The guard is intentional: if someone re-introduces
        hardcoded paths, this test catches it and reminds them to use sync-config.json.
        Comment lines are stripped to avoid false positives from documentation.
        """
        import inspect
        import aec.commands.install as install_mod

        source = inspect.getsource(install_mod)
        # Strip comment-only lines before checking
        code_lines = [l for l in source.splitlines() if not l.strip().startswith("#")]
        code = "\n".join(code_lines)
        assert '".claude/agents"' not in code, (
            "install.py still has hardcoded .claude/agents — refactor to use sync-config.json"
        )
        assert '".claude/skills"' not in code, (
            "install.py still has hardcoded .claude/skills — refactor to use sync-config.json"
        )

    def test_null_cursor_target_does_not_raise(self, tmp_path):
        """Submodule entries with cursor_target: null must be processed without error."""
        config = json.loads(SYNC_CONFIG_PATH.read_text())
        null_targets = [
            k for k, v in config["submodules"].items() if v["cursor_target"] is None
        ]
        assert "gitignore" in null_targets, "gitignore entry should have cursor_target: null"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/commands/test_install_submodules.py -v
```

Expected: `test_install_reads_submodules_from_config` FAILS (hardcoded strings still present)

- [ ] **Step 3: Refactor install.py**

In `aec/commands/install.py`, find the submodule update block (lines 478–506). Replace the hardcoded agents/skills blocks with a loop. First, add the import at the top of the file (with other imports):

```python
import json
```

Then replace lines 488–506:

```python
            # Update each submodule defined in sync-config.json
            sync_config_path = repo_root / "scripts" / "sync-config.json"
            if sync_config_path.exists():
                sync_config = json.loads(sync_config_path.read_text())
                for key, entry in sync_config.get("submodules", {}).items():
                    sub_path = entry["path"]
                    display = entry.get("display_name", key)
                    if (repo_root / sub_path).exists():
                        Console.print(f"  Updating {display}...")
                        success, result = update_submodule(repo_root, sub_path, dry_run)
                        if success:
                            Console.success(f"{display.capitalize()} updated to {result}")
                        else:
                            Console.warning(f"{display}: {result}")
            else:
                Console.warning("scripts/sync-config.json not found — skipping submodule updates")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/commands/test_install_submodules.py -v
```

Expected: All PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
python3 -m pytest --tb=short -q
```

Expected: no new failures

- [ ] **Step 6: Commit**

```bash
git add aec/commands/install.py tests/commands/test_install_submodules.py
git commit -m "refactor(install): drive submodule updates from sync-config.json"
```

---

## Task 3: Refactor push-submodules.sh to read from sync-config.json

**Files:**
- Modify: `scripts/push-submodules.sh:19`
- Test: `tests/scripts/test_push_submodules.sh` (shellcheck)

- [ ] **Step 1: Add jq guard and replace hardcoded SUBMODULES array**

In `scripts/push-submodules.sh`, replace line 19 (`SUBMODULES=(".claude/agents" ".claude/skills")`) with:

```bash
# Require jq for JSON parsing
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for submodule management."
  echo "Install with: brew install jq (macOS) / apt install jq (Linux)"
  exit 1
fi

# Read submodule paths from sync-config.json
SYNC_CONFIG="$REPO_ROOT/scripts/sync-config.json"
if [ ! -f "$SYNC_CONFIG" ]; then
  echo "scripts/sync-config.json not found — cannot determine submodules"
  exit 1
fi

mapfile -t SUBMODULES < <(jq -r '.submodules | to_entries[].value.path' "$SYNC_CONFIG")
```

- [ ] **Step 2: Verify shell syntax**

```bash
bash -n scripts/push-submodules.sh && echo "syntax ok"
```

Expected: `syntax ok`

- [ ] **Step 3: Verify shellcheck passes**

```bash
shellcheck scripts/push-submodules.sh
```

Expected: no errors (warnings about SC2207 style are acceptable if mapfile is flagged — use the `-e SC2207` flag if needed, but `mapfile` is the correct approach here)

- [ ] **Step 4: Verify the script no longer contains hardcoded paths**

```bash
grep -n '\.claude/agents\|\.claude/skills' scripts/push-submodules.sh
```

Expected: no output

- [ ] **Step 5: Commit**

```bash
git add scripts/push-submodules.sh
git commit -m "refactor(push-submodules): read submodule paths from sync-config.json via jq"
```

---

## Task 4: Add toptal/gitignore submodule

**Files:**
- Modify: `.gitmodules`
- Create: `aec/templates/gitignore/` (submodule mount)
- Create: `aec/templates/gitignore/supported.json`
- Test: `tests/templates/test_gitignore_templates.py`

- [ ] **Step 1: Add the submodule**

```bash
git submodule add https://github.com/toptal/gitignore.git aec/templates/gitignore
```

Expected: submodule cloned to `aec/templates/gitignore/`

- [ ] **Step 2: Verify the submodule structure**

After cloning, check the actual template file layout:

```bash
ls aec/templates/gitignore/templates/ | head -20
```

Note the exact filenames (e.g., `Node.gitignore`, `Python.gitignore`). You will need these for `supported.json`.

- [ ] **Step 3: Create supported.json**

Create `aec/templates/gitignore/supported.json`. The keys are AEC language/framework keys (matching `LANGUAGE_HOOKS` and `TEST_FRAMEWORK_HOOKS`). The values are lists of template filenames as they appear in `aec/templates/gitignore/templates/`. Verify the exact casing against what you saw in Step 2 before writing:

```json
{
  "languages": {
    "typescript": ["Node.gitignore", "TypeScript.gitignore"],
    "python": ["Python.gitignore"],
    "rust": ["Rust.gitignore"],
    "go": ["Go.gitignore"],
    "ruby": ["Ruby.gitignore"]
  },
  "frameworks": {
    "nextjs": ["NextJs.gitignore", "Node.gitignore"],
    "jest": ["Node.gitignore"],
    "pytest": ["Python.gitignore"]
  }
}
```

**Important:** Adjust the filenames to match what actually exists in `aec/templates/gitignore/templates/`. Run `ls aec/templates/gitignore/templates/` and correct any casing mismatches.

- [ ] **Step 4: Write the failing test**

Create `tests/templates/test_gitignore_templates.py`:

```python
"""Tests for gitignore template bundling."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SUPPORTED_JSON = REPO_ROOT / "aec" / "templates" / "gitignore" / "supported.json"
TEMPLATES_DIR = REPO_ROOT / "aec" / "templates" / "gitignore" / "templates"


class TestSupportedJson:
    def test_supported_json_exists(self):
        assert SUPPORTED_JSON.exists(), "supported.json must exist"

    def test_supported_json_is_valid(self):
        data = json.loads(SUPPORTED_JSON.read_text())
        assert "languages" in data
        assert "frameworks" in data

    def test_all_referenced_templates_exist(self):
        """Every filename in supported.json must exist in templates/."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("gitignore submodule not initialized — run: git submodule update --init")
        data = json.loads(SUPPORTED_JSON.read_text())
        missing = []
        for section in ("languages", "frameworks"):
            for key, filenames in data[section].items():
                for fname in filenames:
                    if not (TEMPLATES_DIR / fname).exists():
                        missing.append(f"{section}.{key}: {fname}")
        assert not missing, f"Missing template files: {missing}"


class TestCompositeJoin:
    def test_composite_join_single_language(self):
        """Composite join for a single language returns non-empty, deduped content."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("gitignore submodule not initialized — run: git submodule update --init")
        from aec.lib.git_setup import build_composite_gitignore

        result = build_composite_gitignore(["python"], [], REPO_ROOT / "aec" / "templates")
        assert result, "composite gitignore must not be empty"
        assert "# AEC" in result, "must include AEC section"
        lines = result.splitlines()
        assert len(lines) == len(set(lines)), "lines must be deduplicated"

    def test_composite_join_multi_language(self):
        """Composite join for multiple languages includes content from each."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("gitignore submodule not initialized — run: git submodule update --init")
        from aec.lib.git_setup import build_composite_gitignore

        result = build_composite_gitignore(["python", "typescript"], [], REPO_ROOT / "aec" / "templates")
        assert result
        assert "# AEC" in result

    def test_composite_join_submodule_missing(self, tmp_path):
        """When submodule is missing, falls back to AEC patterns only."""
        from aec.lib.git_setup import build_composite_gitignore

        result = build_composite_gitignore(["python"], [], tmp_path)
        assert "# AEC" in result
        assert result  # non-empty
```

- [ ] **Step 5: Run tests to verify they fail with correct messages**

```bash
python3 -m pytest tests/templates/test_gitignore_templates.py -v
```

Expected: `TestCompositeJoin` tests fail with `ImportError` (module doesn't exist yet). `TestSupportedJson` passes or skips if submodule not initialized.

- [ ] **Step 6: Commit submodule + supported.json**

```bash
git add .gitmodules aec/templates/gitignore aec/templates/gitignore/supported.json
git add tests/templates/test_gitignore_templates.py
git commit -m "feat(templates): add toptal/gitignore submodule and supported.json mapping"
```

---

## Task 5: Create GIT_PROVIDERS registry

**Files:**
- Create: `aec/lib/git_providers.py`
- Test: `tests/lib/test_git_providers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/lib/test_git_providers.py`:

```python
"""Tests for aec.lib.git_providers registry and detection functions."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGitProvidersRegistry:
    def test_github_entry_exists(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        assert "github" in GIT_PROVIDERS

    def test_each_provider_has_required_keys(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        required = {"display_name", "detect_files", "detect_commands", "detect_env_vars", "essentials"}
        for key, provider in GIT_PROVIDERS.items():
            for field in required:
                assert field in provider, f"{key} missing {field}"

    def test_each_essential_has_required_keys(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        for pkey, provider in GIT_PROVIDERS.items():
            for ekey, essential in provider["essentials"].items():
                assert "display" in essential, f"{pkey}.{ekey} missing display"
                assert "check" in essential, f"{pkey}.{ekey} missing check"
                assert "template" in essential, f"{pkey}.{ekey} missing template"
                assert callable(essential["check"]), f"{pkey}.{ekey} check must be callable"

    def test_all_non_none_template_paths_exist(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        templates_dir = Path(__file__).parent.parent.parent / "aec" / "templates" / "git"
        missing = []
        for pkey, provider in GIT_PROVIDERS.items():
            for ekey, essential in provider["essentials"].items():
                tpl = essential["template"]
                if tpl is not None:
                    path = templates_dir / tpl
                    if not path.exists():
                        missing.append(f"{pkey}.{ekey}: {tpl}")
        assert not missing, f"Missing template files: {missing}"

    def test_github_has_nine_essentials(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        assert len(GIT_PROVIDERS["github"]["essentials"]) == 9


class TestDetectGitProvider:
    def test_returns_none_when_no_git_dir(self, tmp_path):
        from aec.lib.git_providers import detect_git_provider
        assert detect_git_provider(tmp_path) is None

    def test_returns_unknown_when_git_but_no_signals(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "unknown"

    def test_detects_github_via_dot_github_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".github").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "github"

    def test_detects_github_via_gh_command(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/gh" if cmd == "gh" else None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "github"

    def test_detects_github_via_env_var(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                result = detect_git_provider(tmp_path)
        assert result == "github"


class TestScanGitEssentials:
    def test_all_missing_when_empty_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import scan_git_essentials
        result = scan_git_essentials(tmp_path, "github")
        assert all(v == "missing" for v in result.values())

    def test_gitignore_found_when_exists(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitignore").write_text("node_modules/")
        from aec.lib.git_providers import scan_git_essentials
        result = scan_git_essentials(tmp_path, "github")
        assert result[".gitignore"] == "found"
        assert result["README.md"] == "missing"

    def test_returns_dict_with_all_nine_keys(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import scan_git_essentials
        result = scan_git_essentials(tmp_path, "github")
        assert len(result) == 9
        assert all(v in ("found", "missing") for v in result.values())
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/lib/test_git_providers.py -v
```

Expected: All fail with `ModuleNotFoundError`

- [ ] **Step 3: Create aec/lib/git_providers.py**

```python
"""Git provider registry for aec repo setup."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

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
                "check": lambda d: (d / ".github" / "dependabot.yml").exists(),
                "template": "github/.github/dependabot.yml",
            },
            "pr_template": {
                "display": "PR template (.github/PULL_REQUEST_TEMPLATE.md)",
                "check": lambda d: (d / ".github" / "PULL_REQUEST_TEMPLATE.md").exists(),
                "template": "github/.github/PULL_REQUEST_TEMPLATE.md",
            },
            "issue_templates": {
                "display": "Issue templates (.github/ISSUE_TEMPLATE/)",
                "check": lambda d: (d / ".github" / "ISSUE_TEMPLATE").exists(),
                "template": "github/.github/ISSUE_TEMPLATE/",
            },
            "ci_workflow": {
                "display": "CI workflow (.github/workflows/ci.yml)",
                "check": lambda d: (d / ".github" / "workflows").exists(),
                "template": "github/.github/workflows/ci.yml",
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
                "check": lambda d: (d / ".github" / "CODEOWNERS").exists(),
                "template": "github/.github/CODEOWNERS",
            },
        },
    },
    # To add GitLab, Bitbucket, etc: add an entry here with the same shape.
    # See docs/contributors/adding-git-provider-support.md
}


def detect_git_provider(project_dir: Path) -> Optional[str]:
    """Detect the git provider for a project directory.

    Returns provider key (e.g. "github"), "unknown" if git exists but
    provider unrecognized, or None if no .git directory found.
    """
    if not (project_dir / ".git").exists():
        return None

    for provider_key, provider in GIT_PROVIDERS.items():
        # Check detect_files
        for f in provider["detect_files"]:
            if (project_dir / f).exists():
                return provider_key
        # Check detect_commands
        for cmd in provider["detect_commands"]:
            if shutil.which(cmd) is not None:
                return provider_key
        # Check detect_env_vars
        for var in provider["detect_env_vars"]:
            if os.environ.get(var):
                return provider_key

    return "unknown"


def scan_git_essentials(project_dir: Path, provider_key: str) -> Dict[str, str]:
    """Scan which git essentials are present or missing.

    Returns dict mapping essential key -> "found" | "missing".
    """
    provider = GIT_PROVIDERS[provider_key]
    return {
        key: ("found" if essential["check"](project_dir) else "missing")
        for key, essential in provider["essentials"].items()
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/lib/test_git_providers.py -v
```

Expected: All pass except `test_all_non_none_template_paths_exist` — this test is intentionally red here because the bundled template files don't exist until Task 6. This is expected TDD sequencing: the test documents the contract; Task 6 fulfills it. Do not panic at the red test; continue to Task 6.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/git_providers.py tests/lib/test_git_providers.py
git commit -m "feat(git-providers): add GIT_PROVIDERS registry with detect and scan functions"
```

---

## Task 6: Create bundled GitHub template files

**Files:**
- Create: `aec/templates/git/github/` (all template files listed below)

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p aec/templates/git/github/.github/ISSUE_TEMPLATE
mkdir -p aec/templates/git/github/.github/workflows
mkdir -p aec/templates/git/github
```

Note: Files that go into `.github/` in the user's project are stored at `aec/templates/git/github/.github/` here so that `_resolve_dest` can strip the `github/` provider prefix and produce the correct destination path (e.g. `.github/dependabot.yml`). Files that go at the project root (README.md, LICENSE, .editorconfig) are stored directly in `aec/templates/git/github/`.

- [ ] **Step 2: Create README.md template**

Create `aec/templates/git/github/README.md`:

```markdown
# Project Name

Brief description of what this project does.

## Getting Started

### Prerequisites

List prerequisites here.

### Installation

```bash
# Installation steps
```

## Usage

Describe how to use the project.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) if present.

## License

See [LICENSE](LICENSE).
```

- [ ] **Step 3: Create dependabot.yml template**

Create `aec/templates/git/github/.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

- [ ] **Step 4: Create PULL_REQUEST_TEMPLATE.md**

Create `aec/templates/git/github/.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Summary

<!-- What does this PR do? -->

## Changes

- 

## Test Plan

- [ ] Tests added or updated
- [ ] Manual verification steps documented

## Related Issues

Closes #
```

- [ ] **Step 5: Create issue templates**

Create `aec/templates/git/github/.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug report
about: Report a bug
title: '[BUG] '
labels: bug
---

## Description

<!-- What went wrong? -->

## Steps to Reproduce

1. 
2. 

## Expected Behavior

## Actual Behavior

## Environment

- OS:
- Version:
```

Create `aec/templates/git/github/.github/ISSUE_TEMPLATE/feature_request.md`:

```markdown
---
name: Feature request
about: Suggest a new feature
title: '[FEAT] '
labels: enhancement
---

## Problem

<!-- What problem does this solve? -->

## Proposed Solution

## Alternatives Considered
```

- [ ] **Step 6: Create CI workflow template**

Create `aec/templates/git/github/.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "Add your test command here"
```

- [ ] **Step 7: Create LICENSE template**

Create `aec/templates/git/github/LICENSE`:

```
MIT License

Copyright (c) YEAR AUTHOR

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 8: Create .editorconfig template**

Create `aec/templates/git/github/.editorconfig`:

```ini
root = true

[*]
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
charset = utf-8

[*.{js,ts,jsx,tsx,json,yml,yaml,md}]
indent_style = space
indent_size = 2

[*.py]
indent_style = space
indent_size = 4

[Makefile]
indent_style = tab
```

- [ ] **Step 9: Create CODEOWNERS template**

Create `aec/templates/git/github/.github/CODEOWNERS`:

```
# CODEOWNERS
# Each line is a file pattern followed by one or more owners.
# https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

# Global owner (fallback for everything)
# * @your-username
```

- [ ] **Step 10: Run the template path test**

```bash
python3 -m pytest tests/lib/test_git_providers.py::TestGitProvidersRegistry::test_all_non_none_template_paths_exist -v
```

Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add aec/templates/git/
git commit -m "feat(templates): add bundled github essential templates"
```

---

## Task 7: Create git_setup.py orchestration module

**Files:**
- Create: `aec/lib/git_setup.py`
- Test: `tests/lib/test_git_setup.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/lib/test_git_setup.py`:

```python
"""Tests for aec.lib.git_setup orchestration."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent


class TestBuildCompositeGitignore:
    def test_aec_section_always_present(self, tmp_path):
        from aec.lib.git_setup import build_composite_gitignore
        result = build_composite_gitignore([], [], tmp_path)
        assert "# AEC" in result

    def test_falls_back_gracefully_when_submodule_missing(self, tmp_path):
        from aec.lib.git_setup import build_composite_gitignore
        result = build_composite_gitignore(["python"], [], tmp_path)
        assert "# AEC" in result
        assert result  # non-empty

    def test_deduplicates_lines(self, tmp_path):
        """When two languages share templates (e.g. nextjs + node both → Node.gitignore),
        lines must not be duplicated in the output."""
        templates_dir = REPO_ROOT / "aec" / "templates"
        if not (templates_dir / "gitignore" / "templates").exists():
            pytest.skip("gitignore submodule not initialized")
        from aec.lib.git_setup import build_composite_gitignore
        result = build_composite_gitignore(["typescript"], ["jest"], templates_dir)
        lines = [l for l in result.splitlines() if l and not l.startswith("#")]
        assert len(lines) == len(set(lines)), "non-comment lines must be deduplicated"


class TestWriteGitEssentials:
    def test_creates_readme_from_template(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "README.md", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "README.md").read_text()

    def test_creates_github_dir_structure(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "dependabot", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / ".github" / "dependabot.yml").exists()

    def test_creates_issue_template_dir(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "issue_templates", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / ".github" / "ISSUE_TEMPLATE").is_dir()

    def test_does_not_overwrite_existing_file(self, tmp_path):
        existing_content = "# My existing README\n"
        (tmp_path / "README.md").write_text(existing_content)
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "README.md", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / "README.md").read_text() == existing_content


class TestExecuteCommitStrategy:
    def _make_git_repo(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        return tmp_path

    def test_one_commit_strategy_creates_single_commit(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        (repo / ".gitignore").write_text("*.pyc")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md", ".gitignore"], strategy="one_commit")
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
        )
        assert len(log.stdout.strip().splitlines()) == 1

    def test_incremental_strategy_creates_one_commit_per_file(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        (repo / ".gitignore").write_text("*.pyc")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md", ".gitignore"], strategy="incremental")
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
        )
        assert len(log.stdout.strip().splitlines()) == 2

    def test_stage_only_strategy_stages_but_does_not_commit(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md"], strategy="stage_only")
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
        )
        assert "A  README.md" in status.stdout
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
        )
        assert log.stdout.strip() == ""

    def test_none_strategy_makes_no_git_changes(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md"], strategy="none")
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
        )
        assert "README.md" in status.stdout
        assert status.stdout.startswith("??"), "file should be untracked, not staged"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/lib/test_git_setup.py -v
```

Expected: All fail with `ModuleNotFoundError`

- [ ] **Step 3: Create aec/lib/git_setup.py**

```python
"""Git setup orchestration for aec repo setup."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .git_providers import GIT_PROVIDERS, detect_git_provider, scan_git_essentials

AEC_GITIGNORE_PATTERNS = [
    ".aec.json",
    ".aec-local/",
]

_TEMPLATES_ROOT: Optional[Path] = None


def get_templates_root() -> Path:
    """Return the absolute path to aec/templates/."""
    global _TEMPLATES_ROOT
    if _TEMPLATES_ROOT is None:
        _TEMPLATES_ROOT = Path(__file__).parent.parent / "templates"
    return _TEMPLATES_ROOT


def build_composite_gitignore(
    languages: List[str],
    frameworks: List[str],
    templates_dir: Path,
) -> str:
    """Build a composite .gitignore from detected languages and frameworks.

    Reads templates from the toptal/gitignore submodule, deduplicates lines,
    and appends AEC-specific patterns. Falls back to AEC patterns only if the
    submodule is not initialized.
    """
    supported_json = templates_dir / "gitignore" / "supported.json"
    gitignore_templates_dir = templates_dir / "gitignore" / "templates"

    template_files: List[str] = []

    if supported_json.exists() and gitignore_templates_dir.exists():
        supported = json.loads(supported_json.read_text())
        seen_templates: set = set()

        for lang in languages:
            for tpl in supported.get("languages", {}).get(lang, []):
                if tpl not in seen_templates:
                    template_files.append(tpl)
                    seen_templates.add(tpl)

        for fw in frameworks:
            for tpl in supported.get("frameworks", {}).get(fw, []):
                if tpl not in seen_templates:
                    template_files.append(tpl)
                    seen_templates.add(tpl)
    elif languages or frameworks:
        print(
            "  Warning: gitignore template submodule not initialized.\n"
            "  Run `aec install` to initialize it for language-aware .gitignore generation.\n"
            "  Falling back to AEC patterns only."
        )

    sections: List[str] = []
    seen_lines: set = set()

    for tpl_name in template_files:
        tpl_path = gitignore_templates_dir / tpl_name
        if not tpl_path.exists():
            continue
        name = tpl_name.replace(".gitignore", "")
        section_lines = [f"### {name} ###"]
        for line in tpl_path.read_text(encoding="utf-8").splitlines():
            if line not in seen_lines:
                seen_lines.add(line)
                section_lines.append(line)
        sections.append("\n".join(section_lines))

    aec_section = "\n### AEC ###\n" + "\n".join(AEC_GITIGNORE_PATTERNS)
    sections.append(aec_section)

    return "\n\n".join(sections) + "\n"


def write_git_essential(
    project_dir: Path,
    essential_key: str,
    provider_key: str,
    templates_dir: Path,
) -> bool:
    """Copy a bundled template into the project directory.

    Returns True if written, False if skipped (already exists).
    Does not overwrite existing files.
    """
    essential = GIT_PROVIDERS[provider_key]["essentials"][essential_key]
    template_rel = essential["template"]
    if template_rel is None:
        return False

    src = templates_dir / "git" / template_rel
    is_dir = template_rel.endswith("/")

    if is_dir:
        # Copy directory of templates
        src_dir = templates_dir / "git" / template_rel.rstrip("/")
        if not src_dir.exists():
            return False
        dest_dir = _resolve_dest(project_dir, provider_key, essential_key)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src_file in src_dir.iterdir():
            dest_file = dest_dir / src_file.name
            if not dest_file.exists():
                shutil.copy2(src_file, dest_file)
        return True
    else:
        dest = _resolve_dest(project_dir, provider_key, essential_key)
        if dest.exists():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True


def _resolve_dest(project_dir: Path, provider_key: str, essential_key: str) -> Path:
    """Resolve the destination path for an essential from its template path."""
    essential = GIT_PROVIDERS[provider_key]["essentials"][essential_key]
    template_rel = essential["template"]
    if template_rel is None:
        raise ValueError(f"No template for {essential_key}")
    # Strip provider prefix to get the in-project relative path
    rel = template_rel[len(f"{provider_key}/"):]
    return project_dir / rel


def execute_commit_strategy(
    project_dir: Path,
    files: List[str],
    strategy: str,
    agent_name: str = "your AI agent",
) -> None:
    """Execute the user's chosen commit strategy for created files.

    strategy: "one_commit" | "incremental" | "stage_only" | "none"
    """
    if strategy == "none" or not files:
        return

    def _stage(f: str) -> bool:
        result = subprocess.run(
            ["git", "add", f], cwd=project_dir, capture_output=True, text=True
        )
        return result.returncode == 0

    def _commit(msg: str) -> bool:
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=project_dir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"\n  Git commit failed: {result.stderr.strip()}")
            print(f"  Ask {agent_name} to help troubleshoot.")
        return result.returncode == 0

    if strategy == "stage_only":
        for f in files:
            _stage(f)

    elif strategy == "one_commit":
        for f in files:
            _stage(f)
        _commit("chore: add git essentials via aec setup")

    elif strategy == "incremental":
        for f in files:
            if _stage(f):
                _commit(f"chore: add {f} via aec setup")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/lib/test_git_setup.py -v
```

Expected: All pass (gitignore submodule tests skip if not initialized)

- [ ] **Step 5: Commit**

```bash
git add aec/lib/git_setup.py tests/lib/test_git_setup.py
git commit -m "feat(git-setup): add git_setup orchestration module"
```

---

## Task 8: Integrate git phase into repo.py

**Files:**
- Modify: `aec/commands/repo.py`

The spec requires tests for `_run_git_phase()` logic (git init failure, unknown provider path, multi-select parsing). These go in a new test file since they test functions in `repo.py`.

- [ ] **Step 1: Write failing tests for `_run_git_phase`**

Create `tests/commands/test_repo_git_phase.py`:

```python
"""Tests for _run_git_phase and _create_git_essentials in repo.py."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _make_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


class TestRunGitPhase:
    def test_returns_git_disabled_when_user_declines_github(self, tmp_path):
        from aec.commands.repo import _run_git_phase

        with patch("builtins.input", return_value="n"):
            result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is False
        assert result["provider"] is None
        assert result["items_to_create"] == []

    def test_returns_unknown_provider_with_git_disabled(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.commands.repo import _run_git_phase

        with patch("aec.commands.repo.detect_git_provider", return_value="unknown"):
            result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is False
        assert result["provider"] == "unknown"

    def test_git_init_failure_returns_git_disabled(self, tmp_path):
        from aec.commands.repo import _run_git_phase

        failed = MagicMock()
        failed.returncode = 1
        failed.stderr = "not a git repository"

        with patch("builtins.input", side_effect=["y", "y"]):
            with patch("subprocess.run", return_value=failed):
                result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is False

    def test_multi_select_parses_comma_separated_numbers(self, tmp_path):
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase

        # Patch detect_git_provider to return "github" so we get to the checklist
        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value={
                ".gitignore": "missing",
                "README.md": "missing",
                "dependabot": "missing",
                "pr_template": "found",
                "issue_templates": "found",
                "ci_workflow": "found",
                "license": "found",
                "editorconfig": "found",
                "codeowners": "found",
            }):
                with patch("builtins.input", return_value="1,2"):
                    result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is True
        assert ".gitignore" in result["items_to_create"]
        assert "README.md" in result["items_to_create"]
        assert len(result["items_to_create"]) == 2

    def test_multi_select_all_selects_everything_missing(self, tmp_path):
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase

        all_missing = {k: "missing" for k in [
            ".gitignore", "README.md", "dependabot", "pr_template",
            "issue_templates", "ci_workflow", "license", "editorconfig", "codeowners",
        ]}
        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value=all_missing):
                with patch("builtins.input", return_value="all"):
                    result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is True
        assert len(result["items_to_create"]) == 9

    def test_eoferror_on_input_defaults_to_all(self, tmp_path):
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase

        all_missing = {k: "missing" for k in [
            ".gitignore", "README.md", "dependabot", "pr_template",
            "issue_templates", "ci_workflow", "license", "editorconfig", "codeowners",
        ]}
        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value=all_missing):
                with patch("builtins.input", side_effect=EOFError):
                    result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is True
        assert len(result["items_to_create"]) == 9
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/commands/test_repo_git_phase.py -v
```

Expected: All fail with `ImportError` (functions don't exist yet in repo.py)

- [ ] **Step 3: Add imports at the top of repo.py**

Near the other `aec.lib` imports in `aec/commands/repo.py`, add (note `..lib` prefix — `repo.py` is in `aec/commands/`, not `aec/lib/`):

```python
from ..lib.git_providers import detect_git_provider, scan_git_essentials, GIT_PROVIDERS
from ..lib.git_setup import build_composite_gitignore, write_git_essential, execute_commit_strategy, get_templates_root
from ..lib.config import detect_agents
```

Check if `detect_agents` is already imported at the top of `repo.py` before adding this line — it may already be available at module scope.

- [ ] **Step 4: Add _run_git_phase() function**

Add the following function to `aec/commands/repo.py` (place it near the other private `_` helper functions, before `setup()`):

```python
def _run_git_phase(project_dir: Path) -> dict:
    """Run early git detection and essentials checklist.

    Returns git_config dict with keys:
        git_enabled: bool
        provider: str | None
        items_to_create: list[str]
    """
    # detect_agents is imported at module level (from ..lib.config import detect_agents)
    def _agent_name() -> str:
        agents = detect_agents()
        return next(iter(agents.keys()), "your AI agent") if agents else "your AI agent"

    provider = detect_git_provider(project_dir)

    if provider is None:
        # No git detected
        Console.print("\n  Git not detected in this project.")
        try:
            response = input("  Do you intend to use GitHub? (Y/n): ").strip().lower()
        except EOFError:
            response = "n"

        if response in ("", "y", "yes"):
            try:
                use_init = input("  Want AEC to run git init? (Y/n): ").strip().lower()
            except EOFError:
                use_init = "y"

            if use_init in ("", "y", "yes"):
                result = subprocess.run(
                    ["git", "init"], cwd=project_dir, capture_output=True, text=True
                )
                if result.returncode == 0:
                    Console.success("git init completed.")
                    provider = "github"
                else:
                    Console.warning(f"git init failed: {result.stderr.strip()}")
                    Console.print(
                        "  Make sure git is installed: brew install git (macOS) / apt install git (Linux)"
                    )
                    Console.print(f"  Ask {_agent_name()} to help troubleshoot if this doesn't help.")
                    return {"git_enabled": False, "provider": None, "items_to_create": []}
        else:
            return {"git_enabled": False, "provider": None, "items_to_create": []}

    if provider == "unknown":
        Console.warning(
            "Git detected but provider not identified — skipping git essentials.\n"
            "  To add support for your provider, see:\n"
            "  docs/contributors/adding-git-provider-support.md"
        )
        return {"git_enabled": False, "provider": "unknown", "items_to_create": []}

    # Provider known — scan and show checklist
    Console.print(f"\n  Git detected: {GIT_PROVIDERS[provider]['display_name']}")
    scan = scan_git_essentials(project_dir, provider)

    found = [k for k, v in scan.items() if v == "found"]
    missing = [k for k, v in scan.items() if v == "missing"]

    if found:
        Console.print("\n  Already present:")
        for key in found:
            display = GIT_PROVIDERS[provider]["essentials"][key]["display"]
            Console.print(f"    ✓ {display}")

    if not missing:
        Console.success("All git essentials are present.")
        return {"git_enabled": True, "provider": provider, "items_to_create": []}

    Console.print("\n  Missing git essentials:")
    for i, key in enumerate(missing, 1):
        display = GIT_PROVIDERS[provider]["essentials"][key]["display"]
        Console.print(f"    [{i}] {display}")

    try:
        response = input(
            "\n  Select items for AEC to create\n"
            "  (comma-separated numbers, 'all', or 'none') [all]: "
        ).strip().lower()
    except EOFError:
        response = "all"

    if response in ("", "all"):
        items_to_create = missing
    elif response == "none":
        items_to_create = []
    else:
        selected = []
        for part in response.split(","):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(missing):
                    selected.append(missing[idx])
            except ValueError:
                pass
        items_to_create = selected

    return {"git_enabled": True, "provider": provider, "items_to_create": items_to_create}
```

- [ ] **Step 5: Add _create_git_essentials helper**

Add directly after `_run_git_phase()`:

```python
def _create_git_essentials(
    project_dir: Path,
    git_config: dict,
    detected_languages: List[str],
    detected_frameworks: List[str],
    dry_run: bool,
) -> None:
    """Create selected git essentials and execute the commit strategy."""
    if not git_config.get("git_enabled") or not git_config.get("items_to_create"):
        return

    # detect_agents and get_templates_root are imported at module level
    templates_dir = get_templates_root()
    provider = git_config["provider"]
    items = git_config["items_to_create"]
    agent_name = next(iter(detect_agents().keys()), "your AI agent")

    # Handle .gitignore separately (composite join)
    created_files: List[str] = []
    if ".gitignore" in items:
        if not dry_run:
            content = build_composite_gitignore(detected_languages, detected_frameworks, templates_dir)
            gitignore_path = project_dir / ".gitignore"
            if gitignore_path.exists():
                existing = gitignore_path.read_text()
                if "# AEC" not in existing:
                    gitignore_path.write_text(existing + "\n" + content)
                    Console.success(".gitignore updated with language patterns and AEC section")
                    created_files.append(".gitignore")
            else:
                gitignore_path.write_text(content)
                Console.success(".gitignore created")
                created_files.append(".gitignore")
        else:
            Console.info("Would create/update .gitignore with language-aware patterns")

    # Create all other selected essentials
    other_items = [i for i in items if i != ".gitignore"]
    for key in other_items:
        if dry_run:
            display = GIT_PROVIDERS[provider]["essentials"][key]["display"]
            Console.info(f"Would create: {display}")
            continue
        written = write_git_essential(project_dir, key, provider, templates_dir)
        if written:
            tpl = GIT_PROVIDERS[provider]["essentials"][key]["template"]
            rel = tpl[len(f"{provider}/"):] if tpl else key
            Console.success(f"Created: {rel}")
            created_files.append(rel)

    if dry_run or not created_files:
        return

    # Commit strategy
    Console.print("\n  How should AEC handle git commits for files it created?")
    Console.print("    1. One commit at the end [default]")
    Console.print("    2. Incremental commits per file")
    Console.print("    3. Stage only (git add, you commit)")
    Console.print("    4. No git operations")
    try:
        choice = input("  Choice [1]: ").strip()
    except EOFError:
        choice = "1"

    strategy_map = {"1": "one_commit", "2": "incremental", "3": "stage_only", "4": "none", "": "one_commit"}
    strategy = strategy_map.get(choice, "one_commit")
    execute_commit_strategy(project_dir, created_files, strategy, agent_name)
```

- [ ] **Step 6: Wire into setup() — add git phase call and remove _update_gitignore**

In the `setup()` function in `repo.py`:

After the repo-exists/clone/create block (around line 1029), add the git phase call:

```python
    # Run git setup phase (early — gates all later git-aware behavior)
    git_config = _run_git_phase(project_dir)
```

Find and remove (or comment out) the existing `_update_gitignore` call at line 1047:

```python
    # Update .gitignore  ← DELETE THIS BLOCK
    _update_gitignore(project_dir, dry_run)  ← DELETE THIS LINE
```

After the `_save_aec_json()` call (which happens after test suite detection), add the gitignore + essentials steps. You'll need to pass detected languages/frameworks from the test suite detection result. Find where test suites are detected and capture the language/framework data, then add after `.aec.json` is saved:

```python
    # Git essentials creation (runs after test suite detection so language data is available)
    _create_git_essentials(
        project_dir,
        git_config,
        detected_languages=detected_languages,  # from existing detect_languages() call
        detected_frameworks=detected_frameworks,  # from existing test suite detection
        dry_run=dry_run,
    )
```

**Note:** You will need to look at the exact variable names used in the existing test suite detection block and adapt accordingly. Read lines 1048–1080 carefully before making changes.

- [ ] **Step 7: Run the new git phase tests**

```bash
python3 -m pytest tests/commands/test_repo_git_phase.py -v
```

Expected: All pass

- [ ] **Step 8: Run the full test suite**

```bash
python3 -m pytest --tb=short -q
```

Expected: All existing tests pass; no regressions

- [ ] **Step 9: Commit**

```bash
git add aec/commands/repo.py tests/commands/test_repo_git_phase.py
git commit -m "feat(setup): integrate git phase into repo setup flow"
```

---

## Task 9: Add toptal/gitignore composite join tests (complete the template test suite)

This task completes the `tests/templates/test_gitignore_templates.py` tests that were skipped in Task 4 because `git_setup.py` didn't exist yet.

- [ ] **Step 1: Run the full template test suite**

```bash
python3 -m pytest tests/templates/test_gitignore_templates.py -v
```

Expected: All pass or skip (skip only if submodule not initialized)

- [ ] **Step 2: Initialize submodule if tests are skipping**

```bash
git submodule update --init aec/templates/gitignore
python3 -m pytest tests/templates/test_gitignore_templates.py -v
```

Expected: All pass

- [ ] **Step 3: Verify supported.json template filenames against actual submodule**

```bash
ls aec/templates/gitignore/templates/ | grep -E "^(Node|Python|Rust|Go|Ruby|TypeScript|NextJs)\.gitignore$"
```

If any filenames differ, update `aec/templates/gitignore/supported.json` to match, then re-run tests.

- [ ] **Step 4: Commit any supported.json corrections**

```bash
git add aec/templates/gitignore/supported.json
git commit -m "fix(templates): correct gitignore template filenames in supported.json"
```

---

## Task 10: Contributor docs

**Files:**
- Create: `docs/contributors/adding-git-provider-support.md`
- Create: `docs/contributors/adding-test-framework-support.md`
- Modify: `docs/contributors/adding-hook-support.md`

- [ ] **Step 1: Create adding-git-provider-support.md**

Create `docs/contributors/adding-git-provider-support.md`:

```markdown
# Adding Git Provider Support

This guide explains how to add support for a new git provider (GitLab, Bitbucket, etc.) to AEC's git setup phase.

## Overview

Git providers are registered in `aec/lib/git_providers.py` as entries in the `GIT_PROVIDERS` dict. This mirrors the pattern used for languages (`LANGUAGE_HOOKS`) and test frameworks (`TEST_FRAMEWORK_HOOKS`).

## Step 1: Add a provider entry to `GIT_PROVIDERS`

Edit `aec/lib/git_providers.py` and add an entry:

```python
GIT_PROVIDERS: Dict[str, Dict[str, Any]] = {
    # ...existing entries...
    "gitlab": {
        "display_name": "GitLab",
        "detect_files": [".gitlab/", ".gitlab-ci.yml"],
        "detect_commands": ["glab"],
        "detect_env_vars": ["GITLAB_TOKEN", "CI_JOB_TOKEN"],
        "essentials": {
            ".gitignore": {
                "display": ".gitignore (language-aware, with AEC patterns)",
                "check": lambda d: (d / ".gitignore").exists(),
                "template": None,
            },
            "readme": {
                "display": "README.md",
                "check": lambda d: (d / "README.md").exists(),
                "template": "gitlab/README.md",
            },
            # Add more essentials as needed
        },
    },
}
```

**Required fields for each provider:**
- `display_name`: Human-readable name shown in prompts
- `detect_files`: Files/dirs that indicate this provider. Checked first.
- `detect_commands`: CLI tool names (`shutil.which` check). Checked second.
- `detect_env_vars`: Environment variable names. Checked third.
- `essentials`: Dict of essential items (see below).

**Required fields for each essential:**
- `display`: Human-readable description shown in the checklist
- `check`: `lambda d: bool` — returns `True` if the essential already exists in project dir `d`
- `template`: Relative path under `aec/templates/git/` to the bundled template file, or `None` if built dynamically (only `.gitignore` uses `None`)

## Step 2: Add bundled template files

Create `aec/templates/git/{provider_key}/` and populate with your template files:

```
aec/templates/git/gitlab/
  README.md
  .gitlab-ci.yml
  ...
```

**Note:** Submodule entries in `scripts/sync-config.json` are only for third-party template source repos (e.g., `toptal/gitignore`). Standard provider additions use bundled files only — you do not need a submodule entry.

## Step 3: Add tests

Add a test class to `tests/lib/test_git_providers.py`:

```python
class TestDetectGitLabProvider:
    def test_detects_via_dot_gitlab(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitlab").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "gitlab"
```

Also verify the registry integrity tests (`test_each_provider_has_required_keys`, `test_all_non_none_template_paths_exist`) pass with your new entry.

## Step 4: Run the tests

```bash
python3 -m pytest tests/lib/test_git_providers.py -v
```

All tests must pass.
```

- [ ] **Step 2: Create adding-test-framework-support.md**

Create `docs/contributors/adding-test-framework-support.md`:

```markdown
# Adding Test Framework Support

This guide explains how to add a new test framework to AEC's detection system.

## Overview

Test frameworks are registered in `aec/lib/test_detection.py` as entries in the `TEST_FRAMEWORK_HOOKS` dict. Detection can use config files, `package.json` devDependencies, or `pyproject.toml` sections.

## Step 1: Add an entry to `TEST_FRAMEWORK_HOOKS`

Edit `aec/lib/test_detection.py`:

```python
TEST_FRAMEWORK_HOOKS: Dict[str, Dict[str, Any]] = {
    # ...existing entries...
    "mocha": {
        "display_name": "Mocha",
        "languages": ["typescript", "javascript"],
        "detect_files": [".mocharc.yml", ".mocharc.js", ".mocharc.json"],
        "detect_package_json": {"devDependencies": ["mocha"]},
        "default_command": "npx mocha",
        "default_cleanup": None,
    },
}
```

**Required fields:**
- `display_name`: Human-readable name shown in prompts
- `languages`: List of language keys this framework applies to (from `LANGUAGE_HOOKS`)
- `detect_files`: Config files that indicate this framework is present
- `default_command`: Command to run the test suite

**Optional detection fields** (at least one of `detect_files`, `detect_package_json`, or `detect_pyproject` is required):
- `detect_package_json`: Dict with keys `devDependencies` and/or `scripts` — lists of package names to look for
- `detect_pyproject`: Dict with keys like `"tool.pytest"` mapped to `True` — checks for `[tool.pytest]` table
- `default_cleanup`: Command to run after tests (or `None`)

## Step 2: Add tests

Add a test to `tests/lib/test_test_detection.py` (or the equivalent test file):

```python
def test_detects_mocha(self, temp_dir):
    (temp_dir / ".mocharc.yml").write_text("spec: test/**/*.spec.js")
    from aec.lib.test_detection import detect_test_frameworks
    result = detect_test_frameworks(temp_dir)
    keys = [f["key"] for f in result]
    assert "mocha" in keys
```

## Step 3: Run the tests

```bash
python3 -m pytest tests/lib/test_test_detection.py -v
```

All tests must pass.
```

- [ ] **Step 3: Update adding-hook-support.md with cross-references**

Open `docs/contributors/adding-hook-support.md` and append at the end:

```markdown
## Related Guides

- [Adding a Git Provider](adding-git-provider-support.md) — add GitLab, Bitbucket, or other providers to the git essentials checklist
- [Adding a Test Framework](adding-test-framework-support.md) — add new test framework detection
```

- [ ] **Step 4: Commit**

```bash
git add docs/contributors/adding-git-provider-support.md \
        docs/contributors/adding-test-framework-support.md \
        docs/contributors/adding-hook-support.md
git commit -m "docs(contributors): add git provider and test framework contributor guides"
```

---

## Task 11: Final verification

- [ ] **Step 1: Run the full test suite**

```bash
python3 -m pytest --tb=short -q
```

Expected: 100% pass

- [ ] **Step 2: Verify shellcheck**

```bash
shellcheck scripts/push-submodules.sh
```

Expected: no errors

- [ ] **Step 3: Verify sync-config.json is valid JSON**

```bash
python3 -c "import json; json.load(open('scripts/sync-config.json')); print('valid')"
```

- [ ] **Step 4: Verify no hardcoded submodule paths remain**

```bash
grep -rn '\.claude/agents\|\.claude/skills' aec/commands/install.py scripts/push-submodules.sh
```

Expected: no output

- [ ] **Step 5: Smoke test the git provider registry**

```bash
python3 -c "
from aec.lib.git_providers import GIT_PROVIDERS, detect_git_provider, scan_git_essentials
from pathlib import Path
print('Providers:', list(GIT_PROVIDERS.keys()))
print('Essentials:', list(GIT_PROVIDERS['github']['essentials'].keys()))
"
```

Expected: `Providers: ['github']`, `Essentials: ['.gitignore', 'README.md', ...]` (9 items)

- [ ] **Step 6: Final commit**

```bash
git add -A
git status  # verify only expected files
git commit -m "feat(git-setup): complete git setup phase implementation"
```
