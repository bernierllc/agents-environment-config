# Authoring an Org Config (Phase 1)

This guide is for the IT/admin authoring an org config for distribution to your team. It covers **Phase 1** schema only — fields documented elsewhere as Phase 2+ are explicitly listed at the end so you don't ship a config that depends on un-shipped functionality.

## File shape

An org config is a single YAML file with a frontmatter/body split:

```yaml
---
# frontmatter: identity + trust
schema_version: "1.0"
org_id: "acme"
org_name: "Acme Corp"
config_version: "3.2.0"
description: "Standard AEC configuration for Acme engineering"
trust:
  mode: "unsigned"
---

# body: sources, items, install
sources:
  default: { skills: keep, rules: keep, agents: replace, mcps: keep }
  custom: []
items:
  skills: {}
  rules: {}
  agents: {}
  mcps: {}
```

The frontmatter is delimited by `---` lines. Both blocks must be valid YAML.

## Frontmatter fields

| Field | Required | Notes |
|---|---|---|
| `schema_version` | yes | Must be `"1.0"` for Phase 1. |
| `org_id` | yes | Stable identifier; lowercase letters, digits, hyphens. Used as the on-disk filename. |
| `org_name` | yes | Human-readable name shown in `aec org status` and `aec doctor`. |
| `config_version` | yes | Semver; bumped each time the config changes. Surfaced to users. |
| `description` | no | One-line summary. |
| `trust.mode` | yes | Phase 1: must be `"unsigned"`. `pinned_key` and `dns_anchor` arrive in Phase 2 and are rejected at validation today. |

## Sources

`sources.default` controls how AEC's built-in catalog interacts with your org's choices, per item type:

- `keep` — your org's `items` block is additive on top of the built-in catalog.
- `replace` — your org's `items` block is the only source for that type; the built-in catalog is hidden.
- `deny` — the built-in catalog is hidden and no items of that type may be added.

Reserved source IDs (always available, do not declare):

- `aec.default.skills`
- `aec.default.rules`
- `aec.default.agents`
- `aec.default.mcps`

`sources.custom[]` lets you pull from your own Git repos:

```yaml
custom:
  - id: "acme-skills"
    url: "https://github.com/acme-corp/aec-skills.git"
    ref: "v1.4.0"
    contributes: ["skills"]
```

`id` must be unique and not collide with reserved IDs. `contributes` is a non-empty subset of `["skills", "rules", "agents", "mcps"]`.

## Items

`items.<type>.<name>` is a per-item policy:

```yaml
items:
  skills:
    "secure-coding-v2":
      source: "aec.default.skills"
      stance: required
      version: ">=2.0.0"
```

Required fields: `source` (must be a reserved or declared custom ID) and `stance`.

### Stance vocabulary (closed)

| Stance | Meaning |
|---|---|
| `required` | Item must be installed; AEC will install or warn loudly if missing. |
| `recommended` | Suggested at install time; user can decline. |
| `blocked` | Item must not be installed; AEC removes/refuses it. |
| `pinned` | Item must be installed at exactly the declared `version`. |
| `silent` | No prompts about this item; useful for org-internal experiments. |

`version` is optional except when stance is `pinned` (then required).

## install.preferences (closed allow-list)

Use this block to set AEC-wide defaults for users in your org. **Only the keys in the closed allow-list are accepted** — any other key is rejected at enrollment.

The runtime list of accepted keys lives in [`aec/lib/org_config/allow_lists.py`](../../aec/lib/org_config/allow_lists.py) (`PREFERENCES_ALLOW_LIST`). At time of writing it includes: `leave-it-better`, `update_check`, `port_registry_enabled`, `scheduled_tests_enabled`, `discovery_recompare`, `projects_dir`, `plans_dir`, `plans_gitignored`, `plans_completion`, `hook_mode`, `aec_json_gitignored`, `report_viewer`, `report_retention_mode`, `report_retention_days`, `global_install_multi_repo_threshold`. Plus the dynamic `configurable_instructions.<key>.<agent>` namespace.

## install.prompts (closed allow-list)

Pre-answer interactive prompts. Same closed-allow-list pattern; see `PROMPTS_ALLOW_LIST` in [`allow_lists.py`](../../aec/lib/org_config/allow_lists.py).

## install.agents

```yaml
install:
  agents:
    enabled:  ["claude", "cursor"]
    disabled: ["qwen", "gemini", "codex"]
```

Restricts which agent surfaces AEC will configure for users in your org.

## What's deferred to later phases

Do **not** ship configs that depend on the following — they will be rejected (or silently ignored) by today's validator:

- `trust.mode: pinned_key` or `dns_anchor` → **Phase 2**
- Hosted refresh / `aec org sync` → **Phase 2**
- More than one enrolled org per user → **Phase 3**
- `projects[]` per-project overlays → **Phase 4**
- `install.mode: guided`/`auto`/etc. selection → **Phase 4**
- `enrollment_script` execution → **Phase 4**
- `branding` block (`display_name`, `welcome_message`, `doctor_footer`) → **Phase 5**
- `refresh.ttl` and `aec daemon-check` → **Phase 5**

If you author with these fields today, the file may parse but the behaviors won't fire. Write Phase 1 configs that work today, and bump `config_version` when later phases let you add more.

## Distribution

AEC never hosts org configs. Distribute the YAML through a channel your team trusts: an internal Git repo, a wiki page with a download link, or your IT package channel. Until Phase 2 ships signing, **only enroll configs received through a trusted channel**.

## Example

See [`examples/minimal-phase1.yaml`](examples/minimal-phase1.yaml) for a complete, working starting point.
