# Optional Feature Preferences

AEC includes optional rules that you can enable or disable per-machine. Preferences persist across CLI runs and affect which rules get copied into your projects during `aec repo setup`.

## Available Features

| Feature | Description | Default |
|---------|-------------|---------|
| `leave-it-better` | Instructs AI agents to track and fix bugs, lint issues, or broken tests they discover while working | Enabled |

## CLI Commands

### List preferences

```bash
aec preferences list
```

Shows all optional features and their current status (enabled, disabled, or not yet set).

### Enable or disable a feature

```bash
aec preferences set leave-it-better on
aec preferences set leave-it-better off
```

Values accepted: `on`/`off`, `true`/`false`, `yes`/`no`, `1`/`0`.

### Reset a preference

```bash
aec preferences reset leave-it-better
```

Removes the stored preference so you'll be prompted again on your next CLI run.

## How It Works

### Storage

Preferences are stored in JSON at:

```
~/.agents-environment-config/preferences.json
```

The file structure:

```json
{
  "schema_version": "1.0",
  "optional_rules": {
    "leave-it-better": {
      "enabled": true,
      "asked_at": "2025-01-15T10:30:00Z"
    }
  }
}
```

### Auto-Prompt

When you run any `aec` command, a pre-command callback checks for unanswered optional features. If any exist, you'll be prompted before the command runs. Once you answer, the preference is saved and you won't be asked again.

To re-trigger the prompt, use `aec preferences reset <feature>`.

### Effect on Project Setup

When you run `aec repo setup`, enabled optional rules are copied into the target project alongside the standard rules. Disabled optional rules are skipped. This means each project gets exactly the rules you've opted into.

## Quality infrastructure settings

These settings are prompted during `aec install` and manageable via `aec config set <key> <value>`:

| Setting | Default | Description |
|---------|---------|-------------|
| `aec_json_gitignored` | `false` | Whether `.aec.json` is added to `.gitignore` during setup |
| `port_registry_enabled` | prompted | Whether the port registry is active |
| `scheduled_tests_enabled` | prompted | Whether scheduled test runs are enabled (wired in Phase 2/3) |
| `report_viewer` | prompted | Key for the report viewer command, or `null` for no auto-open |
| `report_retention_mode` | prompted | `auto` (prune after N days) or `manual` |
| `report_retention_days` | `30` | Days to keep reports (only used when `report_retention_mode` is `auto`) |
| `profile_retention_days` | `90` | Days to keep profile data in `profiles/` (separate from report retention) |
| `parallel_enabled` | `false` | Enable parallel lane execution (opt in after reviewing suggested lanes) |

## Catalog install preferences

These live under `settings` in `~/.agents-environment-config/preferences.json` (edit the file directly; AEC merges unknown keys under `settings`).

| Setting | Default | Description |
|---------|---------|-------------|
| `global_install_multi_repo_threshold` | `3` | Minimum number of *other* repos that must already record this item before the global migration prompt appears (clamped between 2 and 50). Default 3 means the prompt runs when the new install would be the **4th** distinct tracked repo. |
| `skip_global_install_prompt_for` | `{}` | Map of `"<type>:<name>"` (for example `skill:my-skill`) to `true` when you asked AEC never to offer global migration for that item again. |

## Local configuration directory

AEC tracks which projects you've set up and your preferences in `~/.agents-environment-config/`:

```
~/.agents-environment-config/
├── README.md                    # Explains why this directory exists
├── preferences.json             # User settings and optional feature toggles
├── ports-registry.json          # Central port registry (all projects)
├── scheduler-config.json        # Test schedule, execution, and retention config
├── runner.py                    # Generic test runner script
├── tracked-repos.json           # Tracked project locations
├── installed-skills.json        # Globally installed skills
├── installed-agents.json        # Globally installed agents
├── installed-rules.json         # Globally installed rules
├── dismissed-skills.json        # Skills dismissed during discovery
├── dismissed-agents.json        # Agents dismissed during discovery
├── dismissed-rules.json         # Rules dismissed during discovery
├── catalog-hashes.json          # Pre-computed hashes for AEC catalog items
├── tests/                       # Test reports (one directory per run)
│   └── {datetime}/
│       ├── summary.txt
│       └── {project}_test_output.txt
└── profiles/                    # Profile data (one directory per project)
    └── {project}/
        └── {datetime}.json
```

`preferences.json` stores:

- **Settings**: Projects root directory, plans directory name, git tracking preference, plan completion behavior (archive/delete)
- **Quality infrastructure**: Port registry toggle, scheduled test toggle, report viewer, retention settings, profile retention, parallelization
- **Catalog installs**: Multi-repo global migration threshold and per-item "do not ask again" map
- **Discovery**: Re-compare policy for dismissed items (auto vs manual)
- **Optional rules**: Feature toggles like "Leave It Better"

This directory enables:

- **Cascading updates**: Update all tracked projects at once
- **Re-run detection**: Detects if a project was already set up
- **Inventory**: List all configured projects
- **Consistent settings**: Plans directory and completion behavior applied across all projects
- **Port conflict detection**: Central registry prevents port collisions across projects
