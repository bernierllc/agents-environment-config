# Adding Hook Support

This guide explains how to add new languages or agent hook support to the AEC lint hooks feature.

## Adding a New Language

Edit `aec/lib/hooks.py` and add an entry to `LANGUAGE_HOOKS`:

```python
LANGUAGE_HOOKS = {
    # ...existing languages...
    "elixir": {
        "display_name": "Elixir",
        "detect_files": ["mix.exs"],
        "command": "mix compile --warnings-as-errors 2>&1 | head -20",
    },
}
```

**Fields:**
- `display_name`: Human-readable name shown in prompts
- `detect_files`: List of files to check for in the project root. If any exist, the language is detected.
- `command`: Shell command to run after file edits. Should be piped through `| head -20` to limit output.

Then add tests to `tests/test_hooks.py`:

```python
def test_detects_elixir(self, temp_dir):
    (temp_dir / "mix.exs").write_text("")
    from aec.lib.hooks import detect_languages
    assert "elixir" in detect_languages(temp_dir)
```

## Adding Hook Support for a New Agent

Two things are needed:

### 1. Add to `AGENT_HOOK_CONFIGS` in `aec/lib/hooks.py`

```python
AGENT_HOOK_CONFIGS = {
    # ...existing agents...
    "new-agent": {
        "config_path": ".new-agent/hooks.json",
        "config_format": "json",
        "template": lambda commands: {
            "hooks": {
                "afterEdit": [
                    {"command": cmd} for cmd in commands
                ],
            },
        },
    },
}
```

**Fields:**
- `config_path`: Relative path from project root to the agent's hook config file
- `config_format`: Currently only `"json"` is supported
- `template`: A callable that takes a list of command strings and returns the complete config dict

### 2. Add `supports_hooks: true` to `agents.json`

```json
"new-agent": {
    "display_name": "New Agent",
    ...
    "supports_hooks": true
}
```

Then run `python3 scripts/generate-agent-config.py` to regenerate the shell config.

### Testing

Add tests to `tests/test_hooks.py`:

```python
def test_new_agent_config(self):
    from aec.lib.hooks import generate_hook_config
    result = generate_hook_config("new-agent", ["my-lint-cmd"])
    assert "hooks" in result
```

## Related Guides

- [Adding a Git Provider](adding-git-provider-support.md) — add GitLab, Bitbucket, or other providers to the git essentials checklist
- [Adding a Test Framework](adding-test-framework-support.md) — add new test framework detection

## Declaring directories for item hooks

In an item's `hooks.json`, declare resources that installation should create:

```json
{
  "version": "1.0.0",
  "directories": {"reports": "docs/reports"},
  "hooks": [{
    "id": "check-reports",
    "event": "on_file_edit",
    "command": "test -d {directory:reports}",
    "description": "Check the reports directory",
    "when": {"repo_has": ["docs/reports"]}
  }]
}
```

AEC asks for each resource location and whether to install the item's hooks. It
creates declared directories even when hooks are declined. Defaults must be
repository-relative paths; answers cannot escape the repository or replace a
file. Directory keys are shared across items: related skills should use the same
key, such as `verification`, rather than creating separate competing locations.

Locations are saved in `.aec/directories.json`; include this file in the project
so teammates and scripts use the same paths. Hook consent is saved in the item's
installation state. Reinstall, upgrade, and repair retain both choices. Explicit
answers can change hook consent. Saved directory locations are stable: a
conflicting answer fails before any resource/config write. Reuse the saved path
or omit the directory answer; individual installs cannot migrate all existing
hooks and runtime readers to a new location.

`{directory:reports}` in a generic hook command renders as a shell-quoted path.
Place it outside shell quotes; concatenate quoted fragments if needed. Matching
`when` paths are remapped to the selected location. Scripts that open the resource
must also read `.aec/directories.json` (defaulting only when the setting is absent).
Raw per-agent overrides do not support placeholders.

`when` remains detection, not a list of paths to manufacture. Do not declare source
folders such as `src/app` as resources. Unmet conditions are reported visibly.
