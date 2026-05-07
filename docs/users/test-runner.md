# Test runner & scheduler

The test runner executes test suites across your tracked projects, profiles resource usage, detects port and process leaks, and generates structured reports.

## Test framework detection

During `aec setup`, AEC scans your project for test frameworks by checking for config files and parsing `package.json` / `pyproject.toml`.

### Supported frameworks

| Framework | Language | Detection |
|-----------|----------|-----------|
| Jest | TypeScript, JavaScript | `jest.config.*`, `package.json` devDependencies |
| Vitest | TypeScript, JavaScript | `vitest.config.*`, `package.json` devDependencies |
| pytest | Python | `pytest.ini`, `conftest.py`, `pyproject.toml` |
| Playwright | TypeScript, JavaScript, Python | `playwright.config.*`, `package.json` devDependencies |
| Cargo Test | Rust | `Cargo.toml` |
| Go Test | Go | `go.mod` |
| RSpec | Ruby | `.rspec`, `spec/spec_helper.rb` |

### Interactive suite selection

After detection, `aec setup` presents the detected frameworks and any test scripts found in `package.json`, then lets you choose which to include in `.aec.json`:

```
Detected test frameworks:
  ✓ Jest (jest.config.ts)
  ✓ Playwright (playwright.config.ts)

Found test scripts in package.json:
  • test:unit → npm run test:unit
  • test:integration → npm run test:integration
  • test:e2e → npm run test:e2e

Which should be included in .aec.json test suites?
[x] test:unit
[x] test:integration
[ ] test:e2e
```

### Scheduled whitelist

The `test.scheduled` array in `.aec.json` controls which suites run in automated scheduled runs. E2E suites that require browsers or heavy infrastructure can exist in `.aec.json` for documentation without being included in unattended runs.

### Extensibility

Adding a new framework requires only adding a dict entry to `TEST_FRAMEWORK_HOOKS` in `aec/lib/test_detection.py`. No other code changes needed -- same pattern as `LANGUAGE_HOOKS` for lint hooks. Additional heuristics (Deno, Turbo, `make test`, Gradle) live in `scan_extended_test_commands()` in the same module and are merged when you run `aec test schedule` (merge) or `aec test detect`.

## `aec test` commands

| Command | Scope | Description |
|---------|-------|-------------|
| `aec test run` | local | Run all suites from the current project's `.aec.json` |
| `aec test run -g` | global | Run scheduled suites across all tracked projects |
| `aec test schedule` | global | Interactive setup: pick run time, configure retention, register with OS scheduler |
| `aec test status` | local | Show this project's test config and last results |
| `aec test status -g` | global | Show schedule config, last run, next run |
| `aec test enable` | global | Re-enable scheduled runs (re-registers with OS scheduler) |
| `aec test disable` | global | Disable scheduled runs (removes OS scheduler registration, keeps config) |
| `aec test report` | local | Show this project's latest test results |
| `aec test report -g` | global | Open the full cross-project summary |
| `aec test detect` | local | Re-run test framework detection for the current project, update `.aec.json` |

**Local vs global scope:** `aec test run` (no `-g`) runs ALL suites in the current project, not just the `scheduled` ones, since the user is explicitly requesting a run. `aec test run -g` runs only the suites listed in `test.scheduled` across every tracked project.

### Examples

```bash
# Run all test suites for the current project
aec test run

# Run scheduled suites across all tracked projects
aec test run -g

# Set up automated daily test runs
aec test schedule

# Check this project's test configuration
aec test status

# Check global schedule and last run results
aec test status -g

# View latest results for this project
aec test report

# View latest cross-project summary
aec test report -g

# Re-detect test frameworks after adding a new one
aec test detect
```

## Scheduled test runs

Set up automated daily test runs with `aec test schedule`. The interactive flow prompts for:

1. Run time (default 02:00, 24h format)
2. Report retention settings
3. Profile retention settings

AEC registers the schedule with your OS-native scheduler:

| OS | Scheduler | Notes |
|----|-----------|-------|
| macOS | launchd | Runs missed jobs on wake (handles laptop sleep) |
| Linux | cron (user crontab) | Missed runs while off are skipped |
| Windows | Task Scheduler | Supports "wake to run" option |

### What runs

Only suites listed in `test.scheduled` in each project's `.aec.json`. Projects without scheduled suites are skipped. Project execution order is randomized each run to expose cross-project contamination that deterministic ordering would mask.

### Where reports go

Reports are written to `~/.agents-environment-config/tests/{datetime}/`:

```
~/.agents-environment-config/
  tests/
    2026-04-08T02:00:00Z/
      summary.txt
      my-webapp_test_output.txt
      my-api_test_output.txt
```

### How to view reports

```bash
# View latest results for the current project
aec test report

# View latest cross-project summary
aec test report -g
```

If `report_viewer` is configured (see [Report viewers](#report-viewers)), the summary opens automatically in your preferred viewer after each run.

### Managing the schedule

```bash
# Check schedule status
aec test status -g

# Temporarily disable without losing config
aec test disable

# Re-enable
aec test enable
```

The schedule configuration lives in `~/.agents-environment-config/scheduler-config.json`. You can edit it directly or use `aec test schedule` to reconfigure interactively.

## Test profiling

Every test suite execution is profiled automatically. The runner captures resource snapshots before and after each suite to track performance trends and detect leaks.

### What's profiled

| Metric | Description |
|--------|-------------|
| Duration | Wall-clock time for each suite |
| Memory | Peak memory usage during execution |
| Ports | Listening ports before and after (compared against port registry) |
| Docker containers | Containers started and remaining after cleanup |
| Process counts | Zombies, stuck I/O, node/test processes before and after |

### Where profiles are stored

Profile data lives at `~/.agents-environment-config/profiles/{project}/`:

```
~/.agents-environment-config/
  profiles/
    my-webapp/
      2026-04-08T02:00:00Z.json
      2026-04-07T02:00:00Z.json
    my-api/
      2026-04-08T02:00:00Z.json
```

Profile data has its own retention setting (`profile_retention_days`, default 90 days), separate from test report retention (default 30 days). Profiles stick around longer because they're used for parallelization analysis and trend detection.

### Port discovery

Port observations happen during every suite execution, regardless of whether the port registry is enabled:

- **Port registry ON:** Unregistered ports that appear during tests are surfaced in the report with a suggestion to register them in `.aec.json`.
- **Port registry OFF:** Observed ports are cross-referenced across all projects. Overlapping ports are flagged as potential problems for parallel development.

### Process leak detection

The runner takes before/after process snapshots for each suite. Only increases are reported -- decreases are just cleanup working correctly. Leaked processes are logged with PID, command, and elapsed time for debugging.

The runner never kills anything. If leaks are detected, you can:
- Fix cleanup commands in `.aec.json`
- Run `scripts/cleanup-hung-processes.sh` manually
- Ignore harmless leaks

## Smart parallelization

By default, projects run sequentially in randomized order. After enough profiling data accumulates, the runner suggests parallel lane groupings.

### How it works

1. **Sequential first.** The runner profiles each project's resource usage over multiple runs.
2. **After 3 runs**, the runner analyzes profiles to compute lane groupings where no two projects in the same lane share ports, both use Docker heavily, or would exceed memory limits together.
3. **Suggestion in report.** The proposed lanes appear in the test summary:
   ```
   Suggested lanes based on port/resource analysis:
     Lane 1: my-api, my-portfolio (no shared ports, low memory)
     Lane 2: my-webapp, my-service (no shared ports, both use docker)
   Enable with: aec config set parallel_enabled true
   ```
4. **User opts in.** Parallelization is never automatic:
   ```bash
   aec config set parallel_enabled true
   ```
5. **Lanes run concurrently.** Projects within the same lane still run sequentially to avoid resource conflicts.

## Test prerequisites

Prerequisites gate test execution. They exist at two levels in `.aec.json`:

### Project-level prerequisites

If any project-level prerequisite fails, ALL suites for that project are skipped.

```json
{
  "test": {
    "prerequisites": ["docker"],
    "suites": { ... }
  }
}
```

### Per-suite prerequisites

Suite-level prerequisites are checked individually. A failed prerequisite skips only that suite -- other suites still run.

```json
{
  "test": {
    "suites": {
      "unit": { "command": "npm run test:unit" },
      "integration": {
        "command": "npm run test:integration",
        "cleanup": "docker compose -f docker-compose.test.yml down",
        "prerequisites": ["docker"]
      }
    }
  }
}
```

In this example, `unit` runs regardless of Docker availability, while `integration` is skipped if Docker isn't present. Prerequisites are checked via `shutil.which()` or service-specific checks (e.g., `docker info`).

## Report viewers

After scheduled test runs, AEC can automatically open the report in your preferred viewer. You configure this during `aec install` when opting into scheduled tests, or anytime with `aec config set report_viewer <key>`.

### Available viewers by OS

**macOS:**

| Key | Viewer | Command |
|-----|--------|---------|
| `cursor` | Cursor | `cursor {file}` |
| `vscode` | VS Code | `code {file}` |
| `open` | Default App | `open {file}` |
| `nano` | nano | `nano {file}` |
| `vim` | vim | `vim {file}` |

**Linux:**

| Key | Viewer | Command |
|-----|--------|---------|
| `vscode` | VS Code | `code {file}` |
| `xdg` | Default App | `xdg-open {file}` |
| `nano` | nano | `nano {file}` |
| `vim` | vim | `vim {file}` |

**Windows:**

| Key | Viewer | Command |
|-----|--------|---------|
| `vscode` | VS Code | `code {file}` |
| `notepad` | Notepad | `notepad {file}` |
| `start` | Default App | `start {file}` |

### Custom command

Select "Other" during the interactive prompt to enter a custom command. Include `{file}` as a placeholder for the report path:

```bash
aec config set report_viewer "my-editor {file}"
```
