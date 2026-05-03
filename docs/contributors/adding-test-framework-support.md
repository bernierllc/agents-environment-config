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

## Related Guides

- [Adding a Git Provider](adding-git-provider-support.md)
- [Adding a Hook](adding-hook-support.md)
