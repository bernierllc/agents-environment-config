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

**Note:** Submodule entries in `scripts/sync-config.json` are only for third-party template source repos (e.g., `github/gitignore`). Standard provider additions use bundled files only — you do not need a submodule entry.

## Step 3: Add tests

Add a test class to `tests/lib/test_git_providers.py`:

```python
class TestDetectGitLabProvider:
    def test_detects_via_dot_gitlab(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitlab").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("aec.lib.git_providers.shutil.which", return_value=None):
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

## Related Guides

- [Adding a Test Framework](adding-test-framework-support.md)
- [Adding a Hook](adding-hook-support.md)
