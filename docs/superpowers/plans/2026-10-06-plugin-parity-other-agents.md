# Plugin management parity for non-Claude agents

Status: proposed — research done 2026-10-06; several facts UNVERIFIED (see "Verify first")
Priority: P2 (feature parity; nothing is broken, non-Claude agents just get less)
Depends on: `2026-06-25-org-config-plugin-governance.md` (org policy applies plugins through the same engine this plan generalizes)

## Problem

AEC manages Claude Code plugins end to end: install, detect installed
versions, refresh marketplaces, update, uninstall, honor
`plugins.execution`, and (with the governance plan) apply org policy. For the
other registered agents (`cursor`, `gemini`, `qwen`, `codex`) AEC only prints
or runs a one-time `per-tool` command and records the **catalog** version —
the exact staleness bug #87 fixed for Claude. After install, AEC cannot tell
what is installed, whether it is current, or whether the agent's own policy
blocked it.

## Incumbent

`aec/lib/claude_plugins.py` is the Claude-specific manager (`installed_versions`,
`refresh_marketplace`, `update_plugin`, `installed_record`, `commands_blocked`);
`aec/lib/plugin_install.py` is the agent-neutral install/uninstall engine with
`marketplace` (Claude-only), `per-tool`, and `external` install types. This
plan generalizes the first, it does not replace the second.

## What each agent offers (from official docs unless noted)

| Agent | Concept | Install / update / remove CLI | JSON / non-interactive | Who owns versions | Installed state on disk | Governance |
|---|---|---|---|---|---|---|
| Claude (baseline) | plugins + marketplaces | `claude plugin install/update/uninstall/list` | yes (`--json`) | Claude Code | `claude plugin list --json` | managed settings |
| Codex | plugins + marketplaces (`marketplace.json`) | `codex plugin add/remove/list`, `codex plugin marketplace add/list/upgrade/remove` | non-interactive; `--json` on list/marketplace (third-party source, v0.137) | marketplace upgrade refreshes catalog; per-plugin update UNVERIFIED | `~/.codex/plugins/cache/<mkt>/<plugin>/<ver>/`; `[plugins."name@mkt"]` in `~/.codex/config.toml` | marketplace policy flags; allow/block list UNVERIFIED |
| Gemini CLI | extensions (`gemini-extension.json`) | `gemini extensions install/uninstall/list/update/enable/disable` | non-interactive; JSON UNVERIFIED | extension author; `update` fetches | `~/.gemini/extensions/` | `admin.extensions.enabled` + allowlist regexes in system `settings.json` |
| Qwen Code | extensions (`qwen-extension.json`) | `qwen extensions install/uninstall/enable/disable/update` | non-interactive; JSON UNVERIFIED | UNVERIFIED | `~/.qwen/extensions/` | UNVERIFIED |
| Cursor | plugins + marketplace | `/plugin marketplace add <git-url>` only; plugin install is interactive (no CLI install, UNVERIFIED as of today) | no | marketplace-reviewed; update UNVERIFIED | `~/.cursor/plugins/cache/`, `installed.json` (community sources) | Team/Enterprise private marketplaces (Default Off / On / Required) |
| Antigravity (`agy`, **not registered in AEC**) | plugins | `agy plugin list/install/enable/disable/uninstall/import/validate/link` | UNVERIFIED | auto-updates (2.0) | `.agents/plugins/`, `~/.gemini/config/plugins/` | UNVERIFIED |

Sources: developers.openai.com/codex/cli/reference; geminicli.com/docs/extensions
and /docs/admin/enterprise-controls; qwenlm.github.io/qwen-code-docs
(extension); cursor.com/docs/plugins; antigravity.google/docs/plugins. Gemini
CLI's docs banner says Antigravity CLI replaced it on 2026-06-18 for unpaid-tier
and Google One users; paid/enterprise status UNVERIFIED.

## Portability

Qwen installs Claude Code plugins and Gemini extensions directly (it converts
`claude-plugin.json`), so a Claude `marketplace` plugin can often target Qwen
with the same content. Cursor and Codex use different manifests; Gemini and
Antigravity are UNVERIFIED. Rule: **a catalog entry declares each agent
explicitly** (`per-tool`); AEC never assumes a Claude plugin works elsewhere.

## Parity target (per agent, only what the agent's CLI can support)

| Capability | Claude today | Target |
|---|---|---|
| Install via agent CLI under `plugins.execution` | yes | codex, gemini, qwen (cursor: instructions-only) |
| Record the version the agent reports | yes | every agent with a verifiable read path |
| Detect installed state | `claude plugin list --json` | per-agent read path (CLI `--json` if verified, else on-disk) |
| Update | `claude plugin update` | codex (`marketplace upgrade`+reinstall if no per-plugin update), gemini, qwen |
| Uninstall | `claude plugin uninstall` | codex `remove`, gemini/qwen `uninstall`; cursor manual |
| Report "unchecked" honestly | yes (#87 rule) | same rule: unknown unless the agent confirmed current |
| Org policy (`items.plugins`) | governance plan | same pass, targets resolved per agent |
| Surface agent-side governance blocks | n/a | gemini allowlist, cursor marketplace mode: warn before install |

Cursor stays instructions-only until a CLI install exists; that is a documented
ceiling, not a gap to paper over.

## Design

1. **One adapter per agent behind a small interface**, in
   `aec/lib/plugin_managers/` (`claude.py` = today's `claude_plugins.py` moved,
   `codex.py`, `gemini.py`, `qwen.py`, `cursor.py`). Each exposes the same few
   functions: `installed_versions()`, `update(plugin_id)`, `refresh()`,
   `uninstall_cmd(...)`, and a `capabilities` set so callers skip what an agent
   cannot do instead of branching on agent names. `commands_blocked()` stays
   shared. No base-class hierarchy: plain functions in modules, looked up by agent
   name.
2. **Loadout schema:** extend `install_type: marketplace` to name its agent
   (`install.agent`, default `claude`) so Codex marketplace plugins don't need
   `per-tool` free text; keep `per-tool` for extensions. Schema + validator +
   `docs/loadout` updated together (contract change; punch list below).
3. **Manifest record:** `record_plugin_install` already keeps `pluginId` and
   `targets`; make it per-target (`{agent: {version, pluginId}}`) so one plugin
   installed to two agents records two versions. Migration: existing records are
   single-target Claude → wrap, never rewrite in place without a manifest version
   bump.
4. **`aec update` / `upgrade` / `outdated`** iterate the adapters of agents that
   have plugin records, apply the #87 rule (unchecked unless confirmed), and honor
   `plugins.execution` and `--dry-run`.
5. **Governance preflight** (gemini allowlist, cursor marketplace mode): read
   once, warn with the fix before running an install that would be blocked. Warn,
   never bypass.
6. **Registry:** decide whether to register Antigravity (`agy`) as a supported
   agent; separate decision, tracked here because plugin support is its main
   draw. Do not build an `agy` adapter until it is registered.

## Verify first (blocking, ~1 session)

Run real `--help` / `--json` on installed CLIs and record results in this file
before writing adapters. Anything still UNVERIFIED after that is cut from scope.

- Codex: per-plugin update command; `--json` shape of `plugin list`; managed
  allow/block list.
- Gemini: `extensions list --json`; extension-enablement file name; paid/enterprise
  status after the Antigravity switch.
- Qwen: versioning/update semantics; JSON output; governance.
- Cursor: any CLI install path; `installed.json` format (community-sourced).
- Antigravity: JSON output, governance.

## Affected surfaces (contract change punch list)

- `aec/lib/claude_plugins.py` (moved), `aec/lib/plugin_install.py`,
  `aec/lib/manifest_v2.py` (per-target records)
- `aec/commands/{install_cmd,apply_cmd,upgrade,update,outdated,uninstall}.py`
  (every caller of `claude_plugins`, `installed_record`, `record_plugin_install`)
- `aec/lib/org_config/apply.py::apply_plugins` (governance plan)
- loadout schema: `docs/loadout/schema/plugin.schema.json`, validator, examples,
  `plugins/*/plugin.json`
- `agents.json` / agent registry (Antigravity decision)
- README plugin section (the confirm-before-run exception for update)

## Tests

Real fake-CLI scripts on `PATH` (shell scripts that emit the documented JSON),
not mocks of our own code; one per adapter proving install, installed-version
read, update, uninstall, and the `instructions-only` guarantee. A schema test
asserts every `plugins/*/plugin.json` validates and that each declared agent has
an adapter. A manifest migration test covers single-target → per-target records.

## Out of scope

Hosting our own marketplaces; converting plugin formats between agents;
auto-update scheduling.
