# Authoring an Org Config

This guide is for the IT/admin authoring an org config for distribution to your team. It covers the Phase 1 schema plus the Phase 2 trust, delivery, and multi-org capabilities. Fields that are still deferred to later phases are listed at the end so you don't ship a config that depends on un-shipped functionality.

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
| `trust.mode` | yes | One of `unsigned`, `pinned_key`, `dns_anchor` (see [Trust modes](#trust-modes)). |

## Trust modes

| Mode | Guarantee | Required fields |
|---|---|---|
| `unsigned` | None — anyone who can edit the file can change your environment. Enrolling requires `--allow-unsigned` or an interactive acknowledgment. | — |
| `pinned_key` | ed25519 signature verified against an inline public key, with TOFU fingerprint pinning. | `trust.pubkey` (base64) **or** `trust.pubkey_url` (https) + a detached signature |
| `dns_anchor` | ed25519 signature verified against a key published at `https://<dns_domain>/.well-known/aec-pubkey`. | `trust.dns_domain` + a detached signature |

```yaml
trust:
  mode: "pinned_key"
  pubkey: "BASE64_ED25519_PUBLIC_KEY"          # or: pubkey_url: "https://acme.example/aec.pub"
  signature_url: "https://acme.example/aec.yaml.sig"   # optional; see signatures below
```

```yaml
trust:
  mode: "dns_anchor"
  dns_domain: "acme.example"                    # key served at /.well-known/aec-pubkey
```

**Signatures.** Signed configs need a detached ed25519 signature over the exact config bytes. AEC looks for it in this order: an explicit `--signature <file>`, then `trust.signature_url` (https), then a `<config>.sig` sibling (for local files: a `<config>.yaml.sig` sidecar; for URLs: `<url>.sig`). On first enrollment AEC shows the key fingerprint for you to confirm out-of-band; it then pins it. If the key later changes, AEC halts and the operator must run `aec org trust-rotate <org-id>` to acknowledge the new key (see [Key rotation](#key-rotation)).

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

## install.mode

```yaml
install:
  mode: "managed"   # or "guided"
```

`managed` applies your policy without prompting; `guided` presents changes for the user to confirm. When two enrolled orgs disagree on the mode, it's surfaced as a conflict (see below).

Users apply your policy with `aec org apply` (or `aec org apply --enroll <url>` to enroll and apply in one step). Applying writes the allow-listed preferences, pre-answers the mapped install prompts, installs `required`/`pinned` items, and removes `blocked` ones. Items waiting on a conflict decision are held until the user runs `aec org resolve`, and apply is refused while a signing key is in rotation lockout.

## Delivery & refresh

Configs can be enrolled from a local file **or** an `https://` URL:

```bash
aec org enroll https://acme.example/aec.yaml
```

AEC records the URL and re-fetches + re-verifies it on `aec update`. To also auto-refetch on ordinary invocations once the local copy ages out, set a TTL:

```yaml
refresh:
  ttl_hours: 24    # positive integer; omit to refresh only on `aec update`
```

For `dns_anchor` orgs, AEC re-checks the published key when its cache is older than 24h and flags a rotation if the fingerprint changed.

## Multi-org & conflicts

Users may enroll more than one org at once. AEC never silently picks a winner: when orgs disagree on the same item stance, version, default-source stance, preference, or install mode, the conflict is surfaced in `aec doctor` / `aec org status` and resolved with `aec org resolve`. Unaffected items still apply (only the conflicting subjects wait for a decision). Resolutions are remembered and automatically re-opened if any contributing config changes.

## Key rotation

For signed orgs, a changed signing key is detected (inline pubkey for `pinned_key`; the well-known key for `dns_anchor`). AEC warns immediately with a day countdown and, after a 30-day grace, locks org-config operations until the operator runs `aec org trust-rotate <org-id>`.

## What's deferred to later phases

Do **not** ship configs that depend on the following — they will be rejected (or silently ignored) by today's validator:

- `projects[]` per-project overlays → **Phase 4**
- `enrollment_script` execution → **Phase 4**
- `branding` block (`display_name`, `welcome_message`, `doctor_footer`) → **Phase 5**
- `aec daemon-check` periodic refresh → **Phase 5**

If you author with these fields today, the file may parse but the behaviors won't fire. Bump `config_version` when later phases let you add more.

## Phase 4 expressiveness

The Phase 4 schema is backward-compatible (`schema_version` stays `"1.0"`); every new block is optional. Authors using these features must require users on a Phase-4-capable `aec`.

### Per-project overlays — `projects[]`

Scope a policy delta to specific repos. Matching is first-overlay-wins; an overlay matches when *either* its `match.git_remote` glob (over the normalized remote) *or* its `match.directory` glob (over the absolute working path) matches. Profiles carry `items` and `prompts`. Project-scoped preferences are intentionally unsupported in v1 because `prefs.json` is a global store.

```yaml
projects:
  - match:
      git_remote: "github.com:acme-corp/*"
    profile:
      items:
        skills:
          "internal-repo-skill":
            source: "acme-skills"
            stance: required
      prompts:
        setup.track_current_repo: true
```

Inside a matched repo, `aec org apply` installs the profile's items at repo scope (the repo's `.claude/...` and a `repos[]` entry in the manifest). Cross-org conflicts introduced by profiles are still *held* by the conflict pipeline.

### Time-bounded rules — `required_after` / `expires_at`

Gate an item's stance by an ISO-8601 window. The stance takes effect at `required_after` and stops at `expires_at`. Outside the window the item is silently dropped — including from blocked-removal, so an expired blocking stance no longer holds a subject.

```yaml
items:
  skills:
    "secure-coding-v2":
      source: "aec.default.skills"
      stance: required
      required_after: "2026-06-01"
      expires_at:     "2027-01-01"
```

### Declarative `enrollment_script`

A closed set of five actions runs on enroll, in declared order. There is no shell escape hatch — `{ action: "run", cmd: "..." }` is rejected at validation.

| Action | Params | Notes |
|---|---|---|
| `add_source` | `source_id` (required) | Clones a `sources.custom[]` entry under `~/.aec/org-sources/<id>`. Sync failures (permission denied, network) are logged and do **not** halt enroll; subsequent `install_items` skips items whose source failed. |
| `install_items` | `types` (optional), `sources` (optional) | Applies this org's install-intent items, filtered by types/sources, skipping items from any failed sources. |
| `set_hooks` | `policy` (optional: `auto`/`per-repo`/`never`) | Writes `hook_mode`. Defaults to the value of `install.preferences.hook_mode`. |
| `run_doctor` | — | Runs `aec doctor`. Doctor errors halt the script. |
| `set_pref` | `key`, `value`, `if_unset` (optional bool) | `key` must be on the install.preferences allow-list. `if_unset` defaults to `true` in guided mode, `false` in managed. |

### Branding

Optional org-supplied identity strings.

```yaml
branding:
  display_name:    "Acme Engineering"
  welcome_message: "Welcome to Acme. Questions? Slack #aec-help"
  doctor_footer:   "Acme org config v4.0.0"
```

`welcome_message` prints after the enroll line; `display_name` and `doctor_footer` bracket the org's section in `aec doctor`.

## Distribution

AEC never hosts org configs. Distribute the YAML through a channel your team trusts: an internal Git repo, an https URL, or your IT package channel. For integrity, sign your config (`pinned_key` or `dns_anchor`) so users can verify it cryptographically rather than relying on transport trust alone.

## Example

See the [`examples/`](examples/) directory for complete, working starting points:

- [`minimal-phase1.yaml`](examples/minimal-phase1.yaml) — smallest unsigned config.
- [`dns-anchor.yaml`](examples/dns-anchor.yaml) — `dns_anchor` trust + `refresh.ttl_hours` + managed mode, with `required`/`pinned`/`blocked` stances.
- [`multi-org-a-acme.yaml`](examples/multi-org-a-acme.yaml) + [`multi-org-b-globex.yaml`](examples/multi-org-b-globex.yaml) — two orgs whose stances clash on the same skill, to demonstrate conflict handling.
- [`phase4-features.yaml`](examples/phase4-features.yaml) — per-project overlays, time-bounded rules, `enrollment_script`, and branding in one config.

## End-to-end walkthrough

**As an author** — publish the YAML through a channel your team trusts (internal Git, an https URL, or your IT package channel). To let users verify integrity, sign it and use `pinned_key` or `dns_anchor` trust (see [Trust modes](#trust-modes)).

**As a user** — enroll and apply:

```bash
# Enroll from a local path or an https URL (signed configs verify on enroll):
aec org enroll https://acme.example.com/aec.yaml
# ...or enroll and apply in one step:
aec install --org-config https://acme.example.com/aec.yaml

# Apply (or re-apply) enrolled policy. --dry-run previews the plan first:
aec org apply --dry-run
aec org apply
```

Managed-mode configs apply silently on every `aec` invocation; guided-mode configs show the plan and prompt first.

**Multiple orgs** — if two enrolled orgs disagree on the same subject (e.g. Acme `required` vs Globex `blocked` for `secure-coding-v2`), that item is *held* while every non-conflicting item still applies (P7). Resolve it once:

```bash
aec org resolve            # list open conflicts
aec org resolve <id>       # pick the winning org (honor:<org-id>) or skip
```

The decision is keyed to both configs' hashes, so it survives unchanged configs but re-opens if either side changes. `aec doctor` surfaces unresolved conflicts and any pending key rotation.
