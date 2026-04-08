# AEC Quality Infrastructure Phase 2: Test Runner, Profiling & Scheduler

> Design spec for the generic test runner, always-on profiling, smart parallelization,
> OS-specific scheduler wrappers, and the `aec test` CLI command group. Builds on the
> Phase 1 foundation (`.aec.json`, port registry, test detection, report viewers).

## Problem

Phase 1 gave AEC the ability to detect test frameworks, register ports, and store test
suite configuration in `.aec.json`. But there's no automation — tests still run manually.
Developers with many projects have no way to know which projects are healthy without
visiting each one individually.

**Phase 2 adds:**
- A runner that executes scheduled test suites across all tracked projects
- Profiling that learns about each project's resource usage over time
- Smart parallelization suggestions based on profiling data
- Port and process leak detection
- Structured reports with actionable observations
- OS-native scheduling (launchd, cron, Task Scheduler)

## Core Principles

1. **Observe, don't act.** The runner never kills processes, removes containers, or modifies
   project state. It runs tests, records observations, and reports findings.

2. **Earn trust before automating.** Parallelization starts disabled. The runner profiles
   sequential runs, suggests lane groupings, and the user opts in.

3. **Randomize to reveal.** Project execution order is randomized each run to expose
   cross-project contamination that deterministic ordering would mask.

4. **Separate retention for separate purposes.** Test reports are ephemeral (default 30 days).
   Profile data is analytical (default 90 days). Each has its own retention setting.

5. **Per-suite granularity.** Prerequisites can be project-level or per-suite. Skipping is
   granular — one failed prerequisite doesn't block unrelated suites.

---

## `.aec.json` Schema Update

Add optional `prerequisites` field to individual test suites:

```json
{
  "test": {
    "suites": {
      "unit": {
        "command": "npm run test:unit",
        "cleanup": null
      },
      "integration": {
        "command": "npm run test:integration",
        "cleanup": "docker compose -f docker-compose.test.yml down",
        "prerequisites": ["docker"]
      }
    },
    "prerequisites": [],
    "scheduled": ["unit", "integration"]
  }
}
```

- Project-level `prerequisites` must ALL pass for any suite to run
- Suite-level `prerequisites` are checked per-suite; failure skips only that suite
- Both levels support the same prerequisite names (checked via `shutil.which()` or
  service-specific checks like `docker info`)

---

## Runner Script

### Location and Invocation

Lives at `~/.agents-environment-config/runner.py`. Invoked by:
- OS scheduler (launchd/cron/Task Scheduler) for automated runs
- `aec test run -g` for manual global runs
- `aec test run` for single-project runs (scoped to current directory)

### Execution Flow

```
1. Load scheduler-config.json
2. Load tracked repos from setup-repo-locations.txt
3. Filter to projects with scheduled suites in .aec.json
4. Randomize project order (record seed for reproducibility)
5. For each project (sequential by default, lanes if parallel enabled):
   a. Load .aec.json
   b. Check project-level prerequisites
      → If any fail: skip entire project, note in report, continue
   c. For each suite in test.scheduled:
      i.   Check suite-level prerequisites
           → If any fail: skip this suite, note in report, continue
      ii.  Snapshot pre-run state:
           - Listening ports (lsof -i -P -n / netstat -ano)
           - Docker containers (docker ps)
           - Process counts (zombies, stuck I/O, node/test processes)
           - Memory baseline
      iii. Run suite command, capture:
           - stdout/stderr → per-project output file
           - Exit code
           - Wall-clock duration
           - Peak memory (resource.getrusage / platform equivalent)
      iv.  Run cleanup command (if specified)
      v.   Snapshot post-run state (same metrics as pre-run)
      vi.  Diff pre/post: compute leaked processes, remaining containers,
           ports still listening, unregistered ports observed
      vii. Write profile entry
   d. Verify cleanup (check registered ports for lingering listeners)
6. Write test reports to tests/{datetime}/
7. Write profile data to profiles/{project}/{datetime}.json
8. Generate summary.txt
9. Apply retention policy (prune old reports if auto mode, prune old profiles)
10. Open summary in configured viewer (if report_viewer is set)
```

### Single-Project Mode

When invoked via `aec test run` (no `-g` flag) inside a tracked project:
- Loads only that project's `.aec.json`
- Runs ALL suites (not just `scheduled` — since the user is explicitly asking)
- Still profiles and writes reports
- Report goes to the same `tests/{datetime}/` directory with just one project

---

## Profiling System

### Profile Data

Per suite, per run. Stored at `profiles/{project}/{datetime}.json`:

```json
{
  "timestamp": "2026-04-08T02:00:00Z",
  "project": "earnlearn",
  "suite": "unit",
  "duration_seconds": 45.2,
  "exit_code": 0,
  "memory_peak_mb": 512,
  "ports_observed": [3333, 5433],
  "ports_registered": [3333, 5433],
  "ports_unregistered": [],
  "docker_containers_started": ["earnlearn-test-db"],
  "docker_containers_remaining": [],
  "ports_still_listening": [],
  "processes_before": {
    "zombies": 0,
    "stuck_io": 0,
    "node_processes": 12
  },
  "processes_after": {
    "zombies": 0,
    "stuck_io": 0,
    "node_processes": 15
  },
  "processes_leaked": 3,
  "leaked_details": [
    {"pid": 42310, "command": "node jest.config.ts", "elapsed": "00:02:15"}
  ]
}
```

### Port Discovery

Runs during every suite execution regardless of port registry setting:

- **Port management ON:** Diffs observed ports against registry. Unregistered ports
  surfaced in summary: "Ports 9229, 9230 appeared during earnlearn tests — consider
  registering them in .aec.json"

- **Port management OFF:** Cross-references observed ports across all projects' profiles.
  Overlapping ports surfaced: "earnlearn and neverhub both use port 5434 during tests —
  parallel development and testing would likely cause port problems"

### Process Leak Detection

Before/after snapshots per suite using platform-specific methods:

**macOS/Linux:**
- Zombies: `ps aux | awk '$8=="Z"'`
- Stuck I/O: `ps aux | awk '$8~/^D/'` (node/npm only)
- Test processes: `pgrep -f "jest|vitest|pytest|playwright|cargo.test|go.test"`

**Windows:**
- Not Responding: `Get-Process | Where-Object { $_.Responding -eq $false }`
- Test processes: `Get-CimInstance Win32_Process` filtered by command line

**Reporting rules:**
- Only report increases (before → after). Decreases are ignored.
- Record leaked process details (PID, command, elapsed time) for debugging
- Never kill — just report

### Smart Parallelization

After `min_profile_runs_for_parallel` sequential runs (default 3):

1. Analyze profiles across all runs for each project:
   - Which ports does it use?
   - Does it use Docker?
   - What's its peak memory?
   - Does it leak processes?

2. Compute lane groupings where no two projects in a lane:
   - Share observed ports
   - Both use Docker heavily (configurable threshold)
   - Would exceed a memory ceiling together

3. Store proposed plan in `scheduler-config.json`:
   ```json
   {
     "parallelization_plan": {
       "computed_at": "2026-04-10T02:00:00Z",
       "based_on_runs": 3,
       "lanes": [
         ["barevents", "mbernier.com"],
         ["earnlearn", "neverhub"]
       ]
     }
   }
   ```

4. Surface in report summary:
   ```
   Suggested lanes based on port/resource analysis:
     Lane 1: barevents, mbernier.com (no shared ports, low memory)
     Lane 2: earnlearn, neverhub (no shared ports, both use docker)
   Enable with: aec config set parallel_enabled true
   ```

5. User opts in via `aec config set parallel_enabled true`

6. When parallel is enabled, runner executes lanes concurrently using
   `concurrent.futures.ThreadPoolExecutor` (projects within a lane still run sequentially)

---

## Report Generation

### Directory Structure

```
~/.agents-environment-config/
  tests/
    2026-04-08T02:00:00Z/
      summary.txt
      earnlearn_test_output.txt
      barevents_test_output.txt
  profiles/
    earnlearn/
      2026-04-08T02:00:00Z.json
      2026-04-07T02:00:00Z.json
    barevents/
      2026-04-08T02:00:00Z.json
```

### Summary Format

```
AEC Test Report — 2026-04-08 02:00:00 UTC
Execution order: barevents, earnlearn, mbernier.com, neverhub (seed: 42)
Note: 12 days of reports exist in ~/.agents-environment-config/tests/

──────────────────────────────────────────

barevents
  ✓ unit         23.4s   passed
  ⊘ integration  skipped (prerequisite: docker not available)

earnlearn
  ✓ unit         45.2s   passed
  ✗ integration  12.1s   FAILED (exit code 1)
    → see earnlearn_test_output.txt

mbernier.com
  ✓ unit         8.3s    passed

neverhub
  ⊘ skipped entirely (no scheduled suites)

──────────────────────────────────────────

Port observations:
  earnlearn: ports 9229, 9230 appeared during tests — not registered in AEC
  barevents: all observed ports match AEC registry ✓

Process observations:
  earnlearn integration: 3 node processes leaked (PIDs: 42310, 42311, 42312)
  all other suites: clean ✓

Parallelization (3/3 profiling runs complete):
  Suggested lanes based on port/resource analysis:
    Lane 1: barevents, mbernier.com (no shared ports, low memory)
    Lane 2: earnlearn, neverhub (no shared ports, both use docker)
  Enable with: aec config set parallel_enabled true
```

### Conditional Sections

- "Note: N days" line — only when retention mode is `manual`
- "Port observations" — only when unregistered or conflicting ports observed
- "Process observations" — only when process count increases detected
- "Parallelization" — only after `min_profile_runs_for_parallel` runs complete

---

## `scheduler-config.json`

Central config for the runner. Lives at `~/.agents-environment-config/scheduler-config.json`.
Generated by `aec test schedule`, updated by the runner as it learns.

```json
{
  "version": "1.0.0",
  "schedule": {
    "enabled": true,
    "time": "02:00",
    "timezone": "local"
  },
  "execution": {
    "mode": "sequential",
    "randomize_order": true,
    "parallel_enabled": false,
    "parallelization_plan": null,
    "min_profile_runs_for_parallel": 3
  },
  "retention": {
    "report_mode": "auto",
    "report_days": 30,
    "profile_days": 90
  },
  "last_run": {
    "timestamp": "2026-04-08T02:00:15Z",
    "projects_run": 4,
    "suites_passed": 6,
    "suites_failed": 1,
    "suites_skipped": 2,
    "seed": 42
  }
}
```

### Field Reference

| Field | Type | Default | Description |
|---|---|---|---|
| `schedule.enabled` | bool | true | Whether the OS scheduler is active |
| `schedule.time` | string | "02:00" | 24h format run time |
| `schedule.timezone` | string | "local" | Timezone for schedule (always local) |
| `execution.mode` | string | "sequential" | "sequential" or "parallel" |
| `execution.randomize_order` | bool | true | Shuffle project order each run |
| `execution.parallel_enabled` | bool | false | User opt-in for parallel lanes |
| `execution.parallelization_plan` | object/null | null | Computed lane groupings |
| `execution.min_profile_runs_for_parallel` | int | 3 | Runs needed before suggesting lanes |
| `retention.report_mode` | string | "auto" | "auto" or "manual" |
| `retention.report_days` | int | 30 | Days to keep test reports (auto mode) |
| `retention.profile_days` | int | 90 | Days to keep profile data |
| `last_run` | object/null | null | Stats from most recent run |

---

## `aec test` CLI Commands

### Command Group

| Command | Scope | Description |
|---|---|---|
| `aec test run` | local (default) | Run this project's test suites from `.aec.json` |
| `aec test run -g` | global | Run ALL tracked projects' scheduled suites |
| `aec test schedule` | global only | Interactive setup: pick run time, confirm retention, register with OS scheduler |
| `aec test status` | both | No flag: show this project's test config. `-g`: show schedule config, last run, next run |
| `aec test enable` | global only | Enable scheduled runs (re-registers with OS scheduler) |
| `aec test disable` | global only | Disable scheduled runs (removes OS scheduler registration, keeps config) |
| `aec test report` | both | No flag: show this project's latest results. `-g`: open full summary |
| `aec test detect` | local only | Re-run test framework detection for current project, update `.aec.json` |

All commands support `--help`.

### `aec test schedule` Flow

1. Check if `scheduled_tests_enabled` preference is True — if not, prompt to enable
2. Prompt for run time (default 02:00, 24h format)
3. Show current retention settings, offer to change
4. Show profile retention setting, offer to change
5. Write `scheduler-config.json`
6. Call OS-specific scheduler wrapper to register
7. Confirm: "Scheduled test runs enabled at 02:00 daily. Run `aec test status` to check."

### `aec test run` Behavior

- **Local mode** (no `-g`): runs ALL suites from current project's `.aec.json` (not just
  `scheduled` — user is explicitly asking). Still profiles and writes reports.
- **Global mode** (`-g`): runs only `scheduled` suites across all tracked projects.
  Same code path as what the OS scheduler invokes.
- Both modes show real-time output to terminal.

### `aec test status` Output

**Local (in a project):**
```
earnlearn test configuration:
  Suites: unit, integration, e2e
  Scheduled: unit, integration
  Prerequisites: docker
  Last run: 2026-04-08 02:00 — unit ✓, integration ✗
```

**Global (`-g`):**
```
AEC Test Schedule:
  Status: enabled
  Time: 02:00 daily
  Last run: 2026-04-08 02:00:15 UTC
  Next run: 2026-04-09 02:00 (estimated)
  Projects: 8 tracked, 5 with scheduled suites
  Parallel: disabled (3/3 profiling runs complete — suggestion available)
  Retention: auto (reports: 30 days, profiles: 90 days)
```

---

## OS Scheduler Wrappers

Thin, OS-specific modules in `aec/lib/schedulers/`. Shared interface:

```python
def register(runner_path: Path, hour: int, minute: int) -> str:
    """Register the runner with the OS scheduler. Returns status message."""

def unregister() -> str:
    """Remove the runner from the OS scheduler. Returns status message."""

def is_registered() -> bool:
    """Check if the runner is currently registered."""

def get_next_run() -> Optional[str]:
    """Return the next scheduled run time, or None."""
```

### macOS — `schedulers/macos.py`

- Generates launchd plist at `~/Library/LaunchAgents/com.aec.test-runner.plist`
- `StartCalendarInterval` for the configured time
- `launchctl load` / `launchctl unload`
- launchd runs missed jobs on wake (handles laptop sleep)

### Linux — `schedulers/linux.py`

- Manages user crontab entry via `crontab -l` / `crontab -`
- Entry: `0 2 * * * /usr/bin/python3 ~/.agents-environment-config/runner.py`
- Tagged with `# AEC test runner` comment for identification
- Missed runs while off are skipped (standard cron)

### Windows — `schedulers/windows.py`

- `schtasks /Create` / `schtasks /Delete`
- Task name: `AEC_TestRunner`
- Supports "wake to run" option

### Wrapper Selection

`aec test schedule` uses `IS_MACOS`/`IS_LINUX`/`IS_WINDOWS` from `aec/lib/config.py`
to call the correct wrapper. Same pattern as existing platform detection.

---

## Cleanup Verification

After each suite's cleanup command runs, the runner verifies cleanup worked:

**Port cleanup:**
- Check if any of the project's registered ports still have listeners
- Flag in profile: `ports_still_listening: [5433]`
- Report: "port 5433 (test-database) still listening after cleanup"

**Process cleanup:**
- Diff pre/post process snapshots
- Only report increases (decreases are ignored — just cleanup working)
- Record leaked PIDs with command and elapsed time

**Docker cleanup:**
- Diff pre/post `docker ps` output
- Flag new containers that appeared during the suite and weren't removed
- `docker_containers_remaining` in profile

**The runner never kills anything.** Users can:
- Fix their cleanup commands in `.aec.json`
- Run the existing `cleanup-hung-processes.sh` manually
- Ignore harmless leaks

---

## New Configuration Settings

| Setting | Default | Description |
|---|---|---|
| `profile_retention_days` | `90` | Days to keep profile data in `profiles/` |
| `parallel_enabled` | `false` | Enable parallel lane execution |

Manageable via `aec config set <key> <value>` and documented in `--help`.

(Other settings — `report_retention_mode`, `report_retention_days`, `report_viewer`,
`scheduled_tests_enabled` — were added in Phase 1.)

---

## File Changes Summary

### New Files

| File | Purpose |
|---|---|
| `~/.agents-environment-config/runner.py` | Generic test runner script |
| `~/.agents-environment-config/scheduler-config.json` | Schedule and execution config |
| `aec/lib/schedulers/__init__.py` | Scheduler wrapper package |
| `aec/lib/schedulers/macos.py` | launchd plist management |
| `aec/lib/schedulers/linux.py` | crontab management |
| `aec/lib/schedulers/windows.py` | Task Scheduler management |
| `aec/lib/runner.py` | Runner logic (imported by runner.py script) |
| `aec/lib/profiler.py` | Profiling: snapshots, diffs, port/process detection |
| `aec/lib/reports.py` | Report generation: summary.txt, per-project output |
| `aec/lib/prerequisites.py` | Prerequisite checking (shutil.which, docker info, etc.) |
| `aec/commands/test_cmd.py` | `aec test` command handlers |
| `tests/test_runner.py` | Runner execution tests |
| `tests/test_profiler.py` | Profiling and snapshot tests |
| `tests/test_reports.py` | Report generation tests |
| `tests/test_prerequisites.py` | Prerequisite checking tests |
| `tests/test_schedulers.py` | OS scheduler wrapper tests |
| `tests/test_test_cmd.py` | CLI command tests |

### Modified Files

| File | Change |
|---|---|
| `aec/cli.py` | Register `test` command group |
| `aec/lib/config.py` | Add path constants for tests/, profiles/, scheduler-config |
| `aec/lib/aec_json.py` | Support per-suite `prerequisites` field in update_test_section |
| `aec/lib/__init__.py` | Export new modules |
| `README.md` | Document `aec test` commands, scheduling, profiling |

---

## Phase 3 Preview (Not in Scope)

Phase 3 will add:
- `aec test report` interactive browser (navigate between runs, diff reports)
- Trend analysis across profile data (is earnlearn getting slower? are leaks increasing?)
- Cross-project contamination analysis (correlate execution order with anomalies)
- Optional cleanup automation (opt-in to let the runner kill leaked processes)
- CI integration (run `aec test run` in CI, post results to PR)
