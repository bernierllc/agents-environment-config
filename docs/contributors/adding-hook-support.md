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
