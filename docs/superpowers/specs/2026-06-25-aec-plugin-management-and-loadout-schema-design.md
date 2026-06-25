# AEC Plugin Management & the `loadout` Item-Manifest Schema — Design Spec

**Date:** 2026-06-25
**Status:** Draft v1 — pending spec-document-reviewer pass

> Design spec for adding first-class plugin management to AEC, plus the generalized,
> open item-manifest schema (`loadout`) that makes it possible. A `plugin.json` /
> `plugin.yaml` file — one instance of a broader `{item}.json/yaml` contract that any
> publisher can ship alongside a skill, agent, rule, or plugin — tells any AI tool how
> to install and use that item. AEC consumes these manifests to install plugins from
> remotes via three install strategies (Claude marketplace, per-tool installer,
> external installer + in-tool instructions), records them in the existing manifest,
> and exposes them through `install`/`uninstall`/`list`/`export`/`apply`/`outdated`.

---

## Problem

AEC tracks five item types — agents, skills, rules, packages, plugins — but only four
of them have any implementation. "Plugins" exists today as a single string in
`aec/lib/agent_blurb/profile.py` (`ITEM_TYPES`) and a policy entry; there is **no**
install, uninstall, list, search, or manifest support for plugins anywhere. The
install/uninstall/CLI surface caps at `("skill", "rule", "agent", "mcp")`
(`install_cmd.py:22`, `uninstall.py:13`, `cli.py:90`).

Worse, the existing item model doesn't fit plugins at all. Today every installable
item is a **local file** discovered from a submodule source dir via markdown
frontmatter, then copied into a scope dir (`sources.py:discover_available`,
`install_cmd.py:run_install`). Plugins live in **remote** repos and websites and have
**heterogeneous install mechanisms**:

1. **Per-tool installer** (e.g. `github.com/DietrichGebert/ponytail`) — the plugin
   repo ships tool-specific install steps; installing into Claude Code differs from
   Cursor differs from Gemini.
2. **External installer + in-tool instructions** (e.g. `impeccable.style`) — the user
   installs something *outside* the AI tool, then follows setup instructions *inside*
   the tool.
3. **Claude marketplace** — native Claude Code plugin marketplace
   (`claude plugin marketplace add` / `claude plugin install`).

A second, larger gap sits underneath this: there is **no portable, machine-readable
way for any item publisher to declare how their item is installed and used.** AEC
infers everything from frontmatter and its own hard-coded install paths. If a plugin
author wants AEC (or any other tool) to install their plugin, there is nothing to
read. The same is true, to a lesser degree, for skills/agents/rules: their install
semantics live in AEC, not with the item.

This spec solves both: it defines an **open item-manifest schema** (`loadout`) that
travels with an item and describes how to install and use it, and it builds **plugin
management in AEC** as the first full consumer of that schema.

### Non-goals

- **Packages.** The `package` item type is deferred. `package.json` is npm's reserved
  filename; a package item-manifest would collide with every Node project, and
  packages already carry native manifests (`package.json`, `pyproject.toml`). Packages
  are explicitly out of scope for the loadout schema in this spec.
- **Auto-installation without consent.** AEC never silently runs remote installers.
  This is a hard constraint (see Execution Policy).
- **A hosted plugin index / discovery service.** Discovery is the curated in-repo
  registry plus a direct-URL fallback. No network catalog.

---

## Guiding constraints

- **AEC never auto-installs anything; user optionality is core.** Every action that
  executes remote code is shown in full and gated behind explicit confirmation. Some
  install types are never executed by AEC at all (instructions-only).
- **Additive, non-breaking.** The loadout manifest is *optional*. AEC keeps reading
  existing frontmatter (`name`/`version`/`description`). Items with no loadout file
  keep working exactly as today. Loadout is a superset that adds what frontmatter
  can't express.
- **Parallel-agent-safe.** One file per item (`plugin.json`), one file per registry
  entry. No shared manifest that concurrent agents would clobber. (Consistent with the
  established `hook.json` and per-type-file conventions.)
- **Follow existing patterns.** `mcp` is the precedent: an item type whose install is a
  special-cased handler rather than a file copy. Plugins follow the same shape.

---

## Part 1 — The `loadout` item-manifest schema

### What it is

An optional, open manifest file that ships *with* an item and tells any AI tool how to
install and use it. Named by item type, following the `hook.json` precedent, in either
format:

- `plugin.json` / `plugin.yaml`
- `skill.json` / `skill.yaml`
- `agent.json` / `agent.yaml`
- `rule.json` / `rule.yaml`

JSON and YAML are interchangeable; a tool reads whichever is present (if both exist,
`.json` wins — single deterministic rule). The file lives at the item's root, or under
a `.loadout/` directory in the publisher's repo when a single repo ships multiple
items.

### Common base (all item types)

| Field | Required | Description |
|---|---|---|
| `schema` | yes | Opaque loadout schema version identifier, e.g. `loadout/v1`. **Never fetched over the network** — AEC validates the file against its *vendored* schema and uses this field only to select which schema version to validate against. (Phase 2 may publish a resolvable URL, but resolution is never required.) |
| `item_type` | yes | `plugin` \| `skill` \| `agent` \| `rule` |
| `name` | yes | Stable identifier (kebab-case) |
| `version` | yes | Semver |
| `description` | yes | One-line summary |
| `source` | yes | Canonical install source (repo URL, marketplace ref, or download page) |
| `homepage` | no | Human-facing docs/landing page |
| `author` | no | `{ name, url }` |
| `license` | no | SPDX identifier |
| `supports` | no | List of AI-tool keys this item works with: `claude`, `cursor`, `gemini`, `qwen`, `codex`. Omitted ⇒ "all". Intersected at install time with `detect_agents()`. |
| `usage` | no | Free-text post-install instructions surfaced to the user after a successful install. |

For `skill`/`agent`/`rule`, the base is sufficient and overlaps existing frontmatter;
the loadout file is purely additive enrichment (publisher metadata, `supports`,
`usage`). AEC continues to discover these via frontmatter today; loadout adoption for
them is a later phase.

### Plugin extension

Plugins add an `install_type` and per-type `install` / `uninstall` blocks. Exactly one
install strategy per plugin.

```jsonc
{
  "schema": "loadout/v1",
  "item_type": "plugin",
  "name": "ponytail",
  "version": "1.0.0",
  "description": "Lazy-senior-dev review/build discipline for AI coding agents.",
  "source": "https://github.com/DietrichGebert/ponytail",
  "homepage": "https://github.com/DietrichGebert/ponytail",
  "author": { "name": "Dietrich Gebert", "url": "https://github.com/DietrichGebert" },
  "license": "MIT",
  "supports": ["claude", "cursor", "gemini"],
  "usage": "Type /ponytail in your agent to toggle modes.",

  "install_type": "per-tool",
  "install": { ...see below... },
  "uninstall": { ...see below... }
}
```

#### `install_type: "marketplace"` (Claude marketplace)

```jsonc
"install": {
  "marketplace": "DietrichGebert/ponytail",   // repo or marketplace ref
  "plugin": "ponytail"                          // plugin name within the marketplace
}
// AEC runs (confirm-then-run):
//   claude plugin marketplace add <marketplace>
//   claude plugin install <plugin>
```

`marketplace` plugins are Claude-only; `supports` is implicitly `["claude"]`. If
`claude` is not in `detect_agents()`, AEC skips the install with a note (mirroring the
per-tool "supported but not detected ⇒ skipped" rule) rather than running the commands.

#### `install_type: "per-tool"` (e.g. ponytail)

```jsonc
"install": {
  "tools": {
    "claude": { "run": ["bash", "-c", "curl -fsSL https://.../install-claude.sh | bash"] },
    "cursor": { "run": ["bash", "-c", "..."] },
    "gemini": { "steps": "Manual: copy X to ~/.gemini/..." }   // no `run` ⇒ instructions-only for this tool
  }
}
```

AEC computes `targets = supports ∩ detect_agents()`, then for each target tool either
runs its `run` array (confirm-then-run) or prints its `steps` text (instructions-only).
A tool present in `supports` but absent from `detect_agents()` is skipped with a note.

#### `install_type: "external"` (e.g. impeccable.style)

```jsonc
"install": {
  "external": {
    "download": "https://impeccable.style/#downloads",   // what to install outside the tool
    "instructions": "1. Download X. 2. In your agent, run /impeccable setup. 3. ..."
  }
}
```

AEC **never** executes the external step. It prints the download location + the
in-tool instructions verbatim and records the install as `instructions-only`.

#### `uninstall` block

Mirrors `install` per type: `marketplace` ⇒ `claude plugin uninstall <plugin>`;
`per-tool` ⇒ per-tool `run`/`steps`; `external` ⇒ `instructions` text. If `uninstall`
is omitted, AEC removes only its own manifest record and tells the user manual cleanup
may be required.

### Validation

A JSON Schema is the source of truth, vendored in this repo at
`docs/loadout/schema/plugin.schema.json` (and `skill`/`agent`/`rule` siblings). The
schema version lives in each file's `schema` field, not in the directory path. AEC
validates every loadout file it reads (vendored or fetched) against the vendored schema
before acting on it, and reports schema errors clearly rather than half-installing.

### Documentation deliverable (Phase 1, this repo)

`docs/loadout/` containing:
- `README.md` — what loadout is, why publishers should ship it, the file-naming rule.
- `schema/plugin.schema.json`, `schema/skill.schema.json`, `schema/agent.schema.json`,
  `schema/rule.schema.json` — JSON Schema definitions.
- `schema/` — the JSON Schema files above.
- `examples/` — annotated `plugin.json`, `plugin.yaml`, and one of each other item type
  in both formats.
- The AEC `README.md` links to `docs/loadout/` and suggests publishers adopt it.

---

## Part 2 — Plugin management in AEC

### Discovery: hybrid registry + URL fallback

- **Curated registry (blessed plugins).** `plugins/<name>/plugin.json` vendored in this
  repo — one directory per plugin, parallel-safe. Discovered by a new
  `_discover_available_plugins()` added to `sources.py:discover_available`, so
  `list`/`search`/`info`/`outdated` pick plugins up with no per-command special casing.
- **URL fallback (arbitrary plugins).** `aec install plugin <url>` fetches
  `plugin.json` / `plugin.yaml` from the repo root or `.loadout/` (and recognizes a
  `.claude-plugin/marketplace.json` as an implicit `marketplace` plugin). If no loadout
  manifest is found, AEC prints what it inspected and stops — **no guessing**.

Both paths converge on a validated loadout `plugin.json`; everything downstream is
identical.

**Known limitation (Phase 1):** the `plugin.json` / `.loadout/plugin.json` convention
means a URL install exposes **one plugin per repo**. Multi-plugin repos via URL are out
of scope for Phase 1 (the curated registry can still vendor each separately). Stated so
it isn't mistaken for a gap later.

### Install handlers

New module `aec/lib/plugin_install.py` (parallel to how `mcp` is special-cased inside
`install_cmd.py`). `run_install` gains a `plugin` branch that delegates here:

```
run_install(item_type="plugin", name|url) →
  load + validate loadout manifest (vendored or fetched)
  resolve targets = supports ∩ detect_agents()
  dispatch on install_type:
    marketplace → confirm-then-run claude commands
    per-tool    → for each target: confirm-then-run `run`, or print `steps`
    external    → print instructions only
  record install in manifest_v2 (+ resolved targets, version, install_type)
  print `usage` text if present
```

### Execution policy (per-type, overridable)

| install_type | Default behavior |
|---|---|
| `marketplace` | confirm-then-run |
| `per-tool` (`run` present) | confirm-then-run |
| `per-tool` (`steps` only) | instructions-only |
| `external` | instructions-only (never executable) |

"Confirm-then-run" shows the exact command(s), target tool, and source, then requires
explicit `y/N` (auto-yes via `--yes`, consistent with existing installs). A new
preferences key lets a user force any executable type down to instructions-only (e.g.
`aec config set plugins.execution instructions-only`). Preferences follow the existing
`config_cmd.py` pattern.

### Uninstall

`aec uninstall plugin <name>` reads the recorded manifest entry, runs the loadout
`uninstall` block under the same per-type policy, then removes the manifest record.

### Manifest & command integration

- `manifest_v2.ITEM_TYPES` gains `"plugins"`; default manifest dict gains a `plugins`
  bucket. New `record_plugin_install(...)` storing `version`, `installedAt`,
  `install_type`, and resolved `targets`. `remove_install` already handles arbitrary
  item types.
- `install_cmd.VALID_TYPES` / `uninstall.VALID_TYPES` gain `"plugin"`;
  `TYPE_TO_PLURAL` gains `"plugin": "plugins"`.
- `list`, `export`, `apply` iterate `ITEM_TYPES`, so plugins flow through once added.
  `apply` re-runs the install handler for each recorded plugin (portable manifest =
  reproducible plugin set). This satisfies the "support installation through the
  manifest features we support" requirement. **Interactivity:** `apply` prompts once
  up front ("apply N plugins?"), then runs each plugin's handler with assume-yes for
  confirm-then-run types so it doesn't stop on every plugin; `external` plugins still
  print instructions only. `--yes` skips the up-front prompt too. (Confirm this matches
  how `apply` handles other item types during implementation; match the existing
  behavior if it differs.)
- `outdated`: compares installed version to the registry `plugin.json` version. For
  URL-only plugins with no tracked registry entry, reports **"version unknown"** rather
  than diffing a remote.

### CLI / help / docs

- `cli.py` help strings updated: `Type: skill, rule, agent, mcp, or plugin` across
  `install`, `uninstall`, `info`.
- Standardize on `aec install plugin <name|url>` (not the draft-spec `aec add plugin`
  from the agent-blurb design; reconcile that doc).
- `README.md`, `AGENTINFO.md`, and `docs/` updated to document plugin commands and link
  the loadout schema docs.

---

## Part 3 — Phasing & roadmap

One spec, three phases. Only Phase 1 is built now; Phases 2–3 are the committed
follow-on captured here and in `plans/ROADMAP.md`.

### Phase 1 — this repo (build now)
1. Loadout schema first draft in `docs/loadout/` (JSON Schema + YAML/JSON examples for
   plugin/skill/agent/rule).
2. Plugin un/install in AEC: discovery (registry + URL), three handlers, per-type
   execution policy, manifest/list/export/apply/outdated/uninstall wiring, CLI + help +
   README + AGENTINFO updates.
3. At least one vendored blessed plugin entry (`plugins/ponytail/plugin.json`) plus one
   `external` example, exercised end to end.

### Phase 2 — extract the open standard (after Phase 1 verified)
> The `github.com/mbernier/loadout` repo already exists and is cloned locally at
> `~/projects/loadout`. No action there until Phase 2 — listed here so the destination
> is known.
1. ~~Create `github.com/mbernier/loadout`.~~ (done — cloned at `~/projects/loadout`)
2. Move schema + docs there; add a polished standalone README.
3. Repoint AEC's README/docs links to the new repo; keep a thin pointer in
   `docs/loadout/`.

### Phase 3 — adoption
1. Add loadout files (`skill.json`/`agent.json`/`rule.json` as appropriate) to our own
   item repos (agency-agents, claude-skills, etc.).
2. Open PRs against the plugins AEC ships, adding a `plugin.json` and linking the
   loadout repo, suggesting adoption for tool-managed install.

---

## Testing

Per project standards (real filesystem/HTTP, no mocks for internal code; third-party
boundaries mocked only with a validating fixture).

- **Schema validation:** every example file in `docs/loadout/examples/` validates
  against its JSON Schema. Invalid fixtures fail with clear errors. The schema files
  themselves are validated as well-formed JSON Schema.
- **Discovery:** `_discover_available_plugins()` finds vendored registry entries;
  malformed `plugin.json` is reported, not silently skipped.
- **URL fallback:** given a temp git repo / local dir containing a `plugin.json`, AEC
  loads and validates it; a repo with no loadout file produces the "nothing to install"
  message and a non-zero exit.
- **Handlers:** each `install_type` is driven end-to-end against a fake AI tool. The
  marketplace and per-tool handlers' executed commands are asserted (via a recording
  shim that stands in for the real `claude`/installer binary, with its own test proving
  the shim matches the documented command shape). The `external` handler asserts
  instructions are printed and **nothing is executed**.
- **Target resolution:** `supports ∩ detect_agents()` is asserted across combinations
  (tool supported but not detected ⇒ skipped; detected but unsupported ⇒ skipped).
- **Execution policy:** the `instructions-only` preference downgrades an otherwise
  executable type and nothing runs.
- **Manifest round-trip:** install → `export` → fresh-machine `apply` reproduces the
  plugin set; `uninstall` removes the record and runs the uninstall block.
- **Outdated:** registry version bump is reported; URL-only plugin reports "version
  unknown".

---

## Affected surfaces (punch list)

- `aec/lib/sources.py` — `_discover_available_plugins`, hook into `discover_available`.
- `aec/lib/plugin_install.py` — **new**: loadout load/validate, three handlers, target
  resolution, execution policy.
- `aec/lib/loadout.py` — **new**: loadout file locate/parse (json|yaml)/validate.
- `aec/lib/manifest_v2.py` — `ITEM_TYPES`, default dict, `record_plugin_install`.
- `aec/commands/install_cmd.py` — `VALID_TYPES`, `TYPE_TO_PLURAL`, `plugin` branch.
- `aec/commands/uninstall.py` — `VALID_TYPES`, plugin uninstall path.
- `aec/commands/{list_cmd,export_cmd,apply_cmd,outdated,info,search}.py` — plugin
  coverage (mostly free if they iterate `ITEM_TYPES`; verify each).
- `aec/commands/preferences.py` / `config_cmd.py` — `plugins.execution` preference.
- `aec/cli.py` — help strings.
- `plugins/<name>/plugin.json` — **new** vendored registry (ponytail + one external).
- `docs/loadout/**` — **new** schema + examples + README.
- `README.md`, `AGENTINFO.md`, `docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md`
  (reconcile `aec add plugin` → `aec install plugin`).
- `plans/ROADMAP.md` — Phase 2/3 entries.

---

## Open questions

- **Schema versioning:** v1 only for now; the `schema` field carries the version so
  future breaking changes are detectable. No migration tooling in this spec.
- **Fetching for URL installs:** Phase 1 supports git repos and local paths. Whether to
  support arbitrary HTTP-hosted `plugin.json` (non-git) is deferred unless a real plugin
  needs it.
