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
