# Testing

How to run tests and the patterns used in the test suite.

## Running Tests

```bash
python -m pytest tests/ --no-header -q
```

For verbose output:

```bash
python -m pytest tests/ -v
```

Also validate rule parity and installation health:

```bash
aec rules validate
aec doctor
```

## Fixtures

Defined in `tests/conftest.py`:

| Fixture | What It Provides |
|---------|-----------------|
| `temp_dir` | A fresh `tempfile.TemporaryDirectory` as a `Path`, cleaned up automatically |
| `mock_home` | Monkeypatches `Path.home()` to return `temp_dir`, isolating tests from the real home directory |
| `mock_repo_root` | Creates a minimal repo structure inside `temp_dir` with `.git/`, `CLAUDE.md`, `.cursor/rules/`, `.agent-rules/`, and `.claude/` directories |
| `clean_env` | Removes `PROJECTS_DIR`, `GITHUB_ORGS`, and `NO_COLOR` environment variables to prevent test pollution |

## Mocking Strategy

- **Paths and environment**: Use `monkeypatch` to override `Path.home()`, env vars, and `input()`. This keeps tests isolated without modifying the real filesystem.
- **File I/O**: Use real file operations against `temp_dir`. No mocking of reads/writes -- tests create actual files and verify actual output.
- **External services**: Mocks are only allowed for third-party services we don't control. If we own the code, we test it directly.

## Test Organization

- **Classes group related tests**: Each test file uses classes to group tests by feature or component (e.g., `TestPreferences`, `TestDoctor`).
- **Descriptive method names**: Test methods describe the behavior being tested (e.g., `test_set_preference_creates_entry`, `test_detect_agents_finds_installed`).
- **One assertion per behavior**: Each test verifies a single behavior. Multiple related assertions in one test are acceptable when they verify the same operation.

## Testing Policy

From the project's CLAUDE.md:

> If we own it or write it, we test it directly -- we do NOT mock it in tests. Do NOT mock the database or the internal API. Use real file I/O with temp dirs. Mocks are only allowed for external third-party services.

This means:
- Test the actual `preferences.py` functions, not a mock of them
- Test real symlink operations in temp directories
- Test CLI commands via their underlying functions
- Only mock things like external HTTP calls or system commands we don't control
