# AEC Version Check & Update Notification

## Problem

Users running AEC on their machines have no way to know when a newer version is available. They must manually check the GitHub repo.

## Solution

Add an automatic version check that queries GitHub Releases API weekly, caches the result, and shows a colored banner when a newer version exists.

## Design Decisions

- **Version source**: GitHub Releases API (`/repos/bernierllc/agents-environment-config/releases/latest`)
- **Check frequency**: Once per 7 days (cached in `~/.agents-environment-config/version-check.json`)
- **Notification**: Colored warning banner after command output with update instructions
- **Opt-out**: Via existing preferences system (`aec preferences set update_check off`)
- **Dependencies**: None new — uses `urllib.request` and `json` from stdlib
- **Error handling**: All failures silently return None — version check never breaks commands

## Components

### 1. `aec/lib/version_check.py`

Core module with:
- `check_for_update() -> Optional[dict]` — main entry point
- `parse_version(v: str) -> tuple` — parses `v2.1.0` or `2.1.0` into `(2, 1, 0)`
- Cache read/write with 7-day TTL
- GitHub API fetch with 5-second timeout

Returns `None` if up-to-date or on error. Returns `{"latest_version", "current_version", "release_url"}` if update available.

### 2. CLI Integration (`aec/cli.py`)

Hook into the existing `_cli_callback` to run the check and print the banner after command output. Respects the `update_check` preference.

Banner format:
```
Warning: Update available: aec v2.0.0 -> v2.1.0
  Run: cd <repo-path> && git pull && pip install -e .
  Release notes: https://github.com/bernierllc/agents-environment-config/releases/tag/v2.1.0
```

### 3. Preferences Integration

Register `update_check` as an optional feature (default: enabled). Users disable with `aec preferences set update_check off`.

### 4. Release Workflow

Manual for now:
```bash
# Bump version in __init__.py, config.py, pyproject.toml
# Commit and push
gh release create v2.1.0 --title "v2.1.0" --notes "Changelog here"
```

## Cache File Format

`~/.agents-environment-config/version-check.json`:
```json
{
  "last_check": "2026-03-04T22:00:00+00:00",
  "latest_version": "2.1.0",
  "release_url": "https://github.com/bernierllc/agents-environment-config/releases/tag/v2.1.0"
}
```

## Validated

Tested against real GitHub API with the `v2.0.0` release created on 2026-03-04. Confirmed:
- API returns correct release data
- Version parsing handles `v` prefix
- Comparison correctly detects newer versions
- Caching works with TTL
- No new dependencies needed
