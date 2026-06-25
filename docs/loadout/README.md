# loadout

A `loadout` file is a portable manifest that travels with an AEC item (plugin, skill, agent, or rule) and tells any AI tool how to install and use it.

## File naming

Follows the same pattern as `hook.json`:

| Item type | JSON | YAML |
|-----------|------|------|
| plugin    | `plugin.json` | `plugin.yaml` |
| skill     | `skill.json`  | `skill.yaml`  |
| agent     | `agent.json`  | `agent.yaml`  |
| rule      | `rule.json`   | `rule.yaml`   |

Place the file at the item's root, or under a `.loadout/` directory when a single repo ships multiple items. If both `.json` and `.yaml` are present, **`.json` wins** — one deterministic rule.

## Common base fields

All item types share these fields:

| Field | Required | Description |
|-------|----------|-------------|
| `schema` | yes | Schema version identifier. Always `loadout/v1`. Never fetched over the network — used only to select the vendored schema to validate against. |
| `item_type` | yes | `plugin` \| `skill` \| `agent` \| `rule` |
| `name` | yes | Stable kebab-case identifier, e.g. `my-plugin` |
| `version` | yes | Semver string |
| `description` | yes | One-line summary |
| `source` | yes | Canonical install source (repo URL, marketplace ref, or download page) |
| `homepage` | no | Human-facing docs or landing page |
| `author` | no | `{ name, url }` |
| `license` | no | SPDX identifier, e.g. `MIT` |
| `supports` | no | List of AI tools this item works with: `claude`, `cursor`, `gemini`, `qwen`, `codex`. Omit to mean "all tools". |
| `usage` | no | Free-text post-install instructions shown to the user after a successful install. |

## Plugin install types

Plugins extend the base with `install_type` (required) and an `install` block (required). `uninstall` is optional; if omitted, AEC removes only its manifest record and tells the user manual cleanup may be needed.

### `marketplace` — Claude marketplace

AEC runs `claude plugin marketplace add <marketplace>` then `claude plugin install <plugin>`. Implicitly Claude-only.

```json
{
  "schema": "loadout/v1",
  "item_type": "plugin",
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Does something useful.",
  "source": "https://github.com/example/my-plugin",
  "install_type": "marketplace",
  "install": {
    "marketplace": "example/my-plugin",
    "plugin": "my-plugin"
  }
}
```

### `per-tool` — tool-specific install scripts

AEC computes `targets = supports ∩ detect_agents()`, then for each target either runs its `run` array (confirm-then-run) or prints its `steps` text (instructions-only). Tools in `supports` but not detected are skipped with a note.

```json
{
  "schema": "loadout/v1",
  "item_type": "plugin",
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Does something useful.",
  "source": "https://github.com/example/my-plugin",
  "supports": ["claude", "cursor"],
  "install_type": "per-tool",
  "install": {
    "tools": {
      "claude": { "run": ["bash", "-c", "curl -fsSL https://example.com/install-claude.sh | bash"] },
      "cursor": { "steps": "Manual: copy X to ~/.cursor/extensions/my-plugin" }
    }
  }
}
```

### `external` — out-of-tool install

AEC never executes external steps. It prints the download location and instructions verbatim and records the install as `instructions-only`.

```json
{
  "schema": "loadout/v1",
  "item_type": "plugin",
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Does something useful.",
  "source": "https://example.com",
  "install_type": "external",
  "install": {
    "external": {
      "download": "https://example.com/#downloads",
      "instructions": "1. Download and install. 2. In your agent, run /my-plugin setup."
    }
  }
}
```

## Why ship a loadout file

- **Any AEC-aware tool** can install your item without custom logic — one file, all tools.
- **`supports`** lets you declare which AI tools you've tested, so AEC skips gracefully on unsupported ones.
- **`usage`** surfaces post-install instructions at exactly the right moment, without the user hunting for docs.
- **Validated before use** — AEC validates every loadout file against the vendored schema before acting, so schema errors surface as clear messages rather than half-installs.

## Schema version

The `schema` field (`loadout/v1`) identifies which vendored schema to validate against. It is **never resolved over the network**. For Phase 1 the schemas live here in `docs/loadout/schema/`. The canonical published home (matching each schema's `$id`) will be the `mbernier/loadout` repository in a later phase.
