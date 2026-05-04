# Org Configuration Overlay — Design Spec

**Date:** 2026-05-04
**Status:** Draft (post-brainstorm, pre-implementation-plan)
**Owner:** Matt Bernier
**Related skills:** `superpowers:brainstorming` → next: `superpowers:writing-plans`

## Problem

Organizations adopting AEC want to standardize their development setup across employees and contractors: same rules, same skills, same agents, same per-project policies. Today AEC has no first-class way for an organization to publish a configuration that:

- Adds (or replaces) the default `bernierllc/*` item sources with the org's own.
- Pre-decides which items are required, recommended, blocked, or pinned to specific versions.
- Pre-configures install behavior so teammates don't re-answer the same prompts inconsistently.
- Applies different policies to different projects based on directory or git remote.
- Is delivered safely via URL fetch, MDM drop, or local file — without exposing users to silent supply-chain attacks.

Without this, every team that wants standardization either forks AEC and maintains a divergent copy, or hand-distributes setup instructions that drift over time.

## Goals

1. Let an organization publish a single versioned configuration file that AEC enrolls and applies on every employee/contractor machine.
2. Support both URL-fetched and MDM-dropped delivery, equivalent once the file is on disk.
3. Support multiple concurrent enrollments per machine (consultants, contractors).
4. Make trust explicit: prefer DNS-anchored signed configs, support pinned-key signed, allow unsigned with loud warnings.
5. Never silently resolve disagreements — between orgs, or between an org and the user's choices. Surface them for the user to decide.
6. Keep individual users (no org config) completely unaffected. Org-config support ships behind a `pip` extras install and adds zero default dependencies to core AEC.
7. Document the feature for three audiences: end users receiving an org config, IT/admin authors publishing one, and AEC contributors maintaining the overlay engine.

## Non-Goals (v1)

Explicitly deferred to keep v1 focused. All can be added in later schema versions without breaking changes:

- Per-user overrides inside a single org config.
- Time-bounded rules (`required_after`, `expires_at`).
- Conditional rules (project-property-based gating beyond directory/remote matching).
- Executable shell hooks inside `enrollment_script`.
- Org-to-org inheritance/delegation.
- Telemetry from the user's machine back to the org.
- A central registry of well-known orgs.

## Audience Framing

AEC operates at three scales. The README will be updated to call this out near the top:

- **Individuals** — clone the repo, `aec install`, get sensible defaults.
- **Teams** — share a fork or a common rules source.
- **Organizations** — publish a signed *org configuration* that AEC enrolls on every member's machine.

Org configurations are private artifacts. AEC never hosts them; each organization publishes their own.

## Concept and Data Flow

An **org config** is a YAML file with frontmatter that AEC interprets as a declarative overlay during normal install/setup/update flows. The org config never installs anything directly — it's data that drives existing AEC code paths.

Three equivalent delivery mechanisms (all converge on the same on-disk state):

1. **URL fetch** — `aec install --org-config https://aec.acme.com/config.yaml`
2. **MDM drop** — IT deploys the file directly to `~/.aec/orgs/<org-id>.yaml`; AEC discovers it on next invocation.
3. **Local path** — `aec install --org-config ./acme-config.yaml` (manual / air-gapped).

A user can enroll in multiple orgs simultaneously. Each org's config is stored at `~/.aec/orgs/<org-id>.yaml` with a sibling `<org-id>.state.json` holding the cached hash, signature status, last-fetched timestamp, and source-of-record.

On every `aec` invocation:

1. Discover all org configs in `~/.aec/orgs/`.
2. Verify each against its trust anchor.
3. Re-hash; if the hash changed since last apply, prompt the user with a diff before applying (or apply silently in `install.mode: managed`).
4. Layer policy: **AEC defaults → org configs → user preferences**.
5. Detect conflicts; halt only the conflicting items, apply everything unambiguous (see Conflict Resolution).

## Schema

YAML with frontmatter, schema-versioned, MDM-friendly, easy to diff and sign.

### Reserved source identifiers

For declaring policy on AEC's bundled sources:

- `aec.default.skills`
- `aec.default.rules`
- `aec.default.agents`
- `aec.default.mcps`

Custom source IDs are declared in `sources.custom[].id`. Any source ID referenced by an item that does not match a reserved name or a declared custom ID is a parse error.

### Stance vocabulary (closed)

`required` · `recommended` · `blocked` · `pinned` · `silent` (default — never written explicitly).

Adding a new stance requires a `schema_version` bump.

### Annotated example

```yaml
---
# Identity & versioning
schema_version: "1.0"
org_id: "acme"
org_name: "Acme Corp"
config_version: "3.2.0"
description: "Standard AEC configuration for Acme engineering"

# Trust anchor — see Trust & Verification section
trust:
  mode: "dns_anchor"            # dns_anchor | pinned_key | unsigned
  dns_domain: "aec.acme.com"
  signature_url: "https://aec.acme.com/config.yaml.sig"
---

sources:
  default:                      # Stance toward AEC's bundled bernierllc/* sources
    skills:  keep               # keep | replace | deny
    rules:   keep
    agents:  replace
    mcps:    keep
  custom:
    - id: "acme-skills"
      url: "https://github.com/acme-corp/aec-skills.git"
      ref: "v1.4.0"             # tag, branch, or commit SHA
      contributes: ["skills"]
    - id: "acme-rules"
      url: "git@github.com:acme-corp/aec-rules.git"
      ref: "main"
      contributes: ["rules"]

items:
  skills:
    "secure-coding-v2":
      source: "aec.default.skills"   # required on every item
      stance: required
      version: ">=2.0.0"
    "experimental-foo":
      source: "aec.default.skills"
      stance: blocked
    "company-onboarding":
      source: "acme-skills"
      stance: required
  rules:
    "general/architecture":
      source: "aec.default.rules"
      stance: pinned
      version: "1.2.0"
  agents: {}
  mcps: {}

install:
  mode: "guided"                # guided | managed
  agents:
    enabled:  ["claude", "cursor"]
    disabled: ["qwen", "gemini", "codex"]
  preferences:
    projects_dir: "~/work/acme"
    completion_behavior: "verify-with-tests"
    hook_policy: "auto"
  prompts:
    quality_infra_port_registry: true
    quality_infra_scheduled_tests: true
    git_essentials_dependabot: true
  enrollment_script:
    - { action: "add_source",    source_id: "acme-skills" }
    - { action: "install_items", types: ["rules", "skills"] }
    - { action: "run_doctor" }

projects:                       # First match wins
  - match:
      git_remote: "github.com:acme-corp/backend-*"
    profile:
      items:
        rules:  { "languages/python/typing-standards": { source: "aec.default.rules", stance: required } }
        skills: { "security-review":                    { source: "aec.default.skills", stance: required } }
      preferences:
        hook_policy: "auto"

  - match:
      directory: "~/work/acme/mobile-*"
    profile:
      items:
        rules:
          "stacks/react-native/*": { source: "aec.default.rules", stance: recommended }

  - match:
      git_remote: "github.com:acme-corp/*"
    profile:
      items:
        rules: { "general/architecture": { source: "aec.default.rules", stance: required } }

branding:
  display_name: "Acme Engineering Standard"
  welcome_message: "AEC is configured per Acme's standards. Questions: #aec-help on Slack"
  doctor_footer: "Acme org config v3.2.0"
```

### Schema design notes

- **`source` is required on every item** to eliminate ambiguity entirely. Parser rejects items without it.
- **`sources.default.<type>` is per-item-type** so an org can replace just the skills source while keeping defaults for rules, etc.
- **`enrollment_script` is declarative actions, not arbitrary shell.** v1 actions: `add_source`, `install_items`, `set_hooks`, `run_doctor`, `set_pref`. No `run: <bash>` escape hatch — would massively expand attack surface and complicate signing.
- **Project matching uses two pattern types**: `git_remote` (preferred, glob over normalized remote URL) and `directory` (glob over absolute path). First match wins.
- **Profile overlays are partial deltas** — they only declare keys they care about; everything else inherits from the org-level config.

## Trust & Verification

Three trust modes, declared by the org in their config. Pubkey/signature plumbing uses ed25519 throughout.

### Mode 1: `dns_anchor` (preferred)

Trust derives from org's domain ownership + valid TLS.

Org publishes:
- `https://aec.acme.com/config.yaml`
- `https://aec.acme.com/config.yaml.sig` (detached ed25519 signature over config bytes)
- `https://aec.acme.com/.well-known/aec-pubkey` (raw ed25519 public key, plain text)

AEC verification flow:
1. Fetch config (or read MDM-dropped local file).
2. Read `trust.dns_domain` from frontmatter.
3. Fetch pubkey from `https://<dns_domain>/.well-known/aec-pubkey` over TLS. TLS chain validation is the trust root.
4. Fetch signature from `trust.signature_url`.
5. Verify config bytes against signature using fetched pubkey.
6. Cache pubkey + source URL in state file for offline re-verification.
7. **Pubkey rotation:** if a fetch returns a different pubkey, AEC treats it as a trust event — `aec org status` flags it; user must run `aec org trust-rotate <org-id>` to acknowledge the rotated key before the new config applies.

### Mode 2: `pinned_key` (fallback)

For orgs that can't host on a public domain.

Org publishes config + signature + pubkey via internal channels (S3 with auth, internal git, MDM).

Org config declares one of:
```yaml
trust:
  mode: "pinned_key"
  pubkey: "<base64-ed25519-pubkey>"
  signature_url: "https://internal.acme/config.yaml.sig"
# or
trust:
  mode: "pinned_key"
  pubkey_url: "https://internal.acme/aec-pubkey"
  signature_url: "https://internal.acme/config.yaml.sig"
```

Enrollment flow:
- First-time install: AEC shows pubkey fingerprint and asks user "you should have received this fingerprint from your IT team — does it match? (y/N)". On `y`, fingerprint is pinned to `~/.aec/orgs/<org-id>.state.json`.
- All subsequent fetches/MDM-drops verified against pinned fingerprint.
- Rotation requires explicit `aec org trust-rotate <org-id>` with the new fingerprint.

This is TOFU with explicit user acknowledgment.

### Mode 3: `unsigned` (loud)

Some small orgs / experimental setups won't sign. Allowed but:

- `aec install --org-config <unsigned-config>` prints a multi-line warning before applying:

  ```
  ⚠  This org config is unsigned.
     Anyone who can write to ~/.aec/orgs/acme.yaml or modify the source URL
     can change your AEC setup, install custom rules/skills/MCPs, or change
     where AEC fetches updates from. Proceed only if you trust the source.
     Continue? (y/N)
  ```

- `aec doctor` permanently flags `trust: unsigned` in red.
- `aec org status` shows the warning every invocation.
- `--allow-unsigned` flag bypasses the prompt for scripted installs (warning still printed).

### Hash-based change detection (all modes)

Independent of signature: AEC stores `sha256(config-bytes)` in the state file. On every run:

1. Re-hash local config file.
2. Hash matches state → fast path, no work.
3. Hash differs → re-verify trust, present unified policy diff to user, require confirmation before applying. Managed-mode configs apply silently (user pre-authorized at enrollment) but still re-verify trust.

This means MDM can drop a new config and AEC notices, verifies, and applies on the user's next AEC invocation.

### Crypto implementation

`pynacl` (Python binding to libsodium): minimal, focused, misuse-resistant, ~2–3 MB install footprint, prebuilt wheels for all common platforms. Gated behind `pip install aec[org-configs]` extras so core AEC stays zero-dep.

Without the extras, signed org configs error cleanly with: *"Org config verification requires `pip install aec[org-configs]`. Install and re-run, or use --allow-unsigned to bypass."* Unsigned configs work without the extras.

`cryptography` may be added later if a use case requires it (e.g., X.509 verification against corporate CAs). Not in v1.

## Local Storage and Refresh

### Filesystem layout

```
~/.aec/
├── orgs/
│   ├── acme.yaml                  # one per enrolled org
│   ├── acme.state.json            # cached hash, trust state, last-applied
│   ├── globex.yaml
│   └── globex.state.json
├── conflict-resolutions.json      # user decisions on multi-org conflicts
├── conflict-resolutions.history.json   # bounded audit trail (last 100 entries)
├── trusted-orgs.json              # pinned pubkey fingerprints for pinned_key mode
└── prefs.json                     # existing user preferences (unchanged)

~/.agent-tools/
├── rules/
│   ├── agents-environment-config/ # AEC default source (existing)
│   └── acme-rules/                # org-contributed source clones
├── skills/
│   └── acme-skills/
├── agents/
└── commands/
```

Org-contributed sources clone to `~/.agent-tools/<source-id>/`, parallel to the AEC default source. Existing AEC discovery/install/symlink machinery handles them with no parallel codepath.

### State file shape

`~/.aec/orgs/<org-id>.state.json`:

```json
{
  "org_id": "acme",
  "config_version": "3.2.0",
  "config_hash": "sha256:abc...",
  "trust_mode": "dns_anchor",
  "pubkey_fingerprint": "SHA256:xyz...",
  "pubkey_source": "https://aec.acme.com/.well-known/aec-pubkey",
  "last_verified_at": "2026-05-04T12:00:00Z",
  "last_applied_at": "2026-05-04T12:00:01Z",
  "source_of_record": "mdm",
  "trust_acknowledgments": {
    "unsigned_warning_acknowledged_at": null,
    "key_rotation_pending": null
  }
}
```

### Discovery and refresh logic (every `aec` invocation)

```
For each file in ~/.aec/orgs/*.yaml:
    1. Parse frontmatter; extract org_id, schema_version, config_version
    2. Compute sha256(file_bytes)
    3. Read ~/.aec/orgs/<org_id>.state.json (if exists)

    4. If state missing → NEW ENROLLMENT:
         a. Verify trust per declared mode
         b. If trust fails → refuse, write error state, surface in `aec doctor`
         c. Run enrollment flow (managed: silent apply; guided: prompt)
         d. Write state file with hash, pubkey fingerprint, timestamps

    5. If state exists, hash matches → FAST PATH

    6. If state exists, hash differs → CONFIG CHANGED:
         a. Re-verify trust
            - DNS-anchored: re-fetch pubkey if cache age > 24h, compare fingerprint
            - Pinned-key: verify against pinned fingerprint
            - Unsigned: re-show acknowledgment if previously unacknowledged
         b. If trust fails OR pubkey rotated → halt, surface in `aec doctor`,
            require explicit `aec org trust-rotate <org-id>` to proceed
         c. Compute policy diff
         d. install.mode == managed → apply silently, log diff to state
         e. install.mode == guided → present diff, prompt y/N, apply on yes

  After all orgs processed:
    7. Recompute conflict set across all enrolled orgs
    8. Invalidate conflict-resolutions whose input hashes changed
    9. If unresolved conflicts → halt conflicting items, surface in `aec doctor`,
       prompt at next interactive `aec` command
```

### URL-fetch refresh (orgs not using MDM)

When an org config was originally added via `--org-config <url>`, AEC stores the URL in the state file. Refresh policy:

- `aec update` re-fetches the URL, writes to `~/.aec/orgs/<org-id>.yaml`, then runs the discovery flow.
- TTL: by default, `aec` invocations don't auto-refetch — only `aec update` does. Orgs can override with `refresh.ttl_hours: 24` in their config to opt into time-based refetch on any invocation. Off by default to stay out of the user's hot path.

### Concurrency

Multiple `aec` processes can run simultaneously. State-file writes use a lock file (`~/.aec/orgs/<org-id>.state.json.lock`) and atomic rename. Verification + state-write is sub-second. Aligns with existing AEC concurrency patterns (separate-files-per-concern).

### Uninstall / unenroll

- `aec org remove <org-id>` — removes config + state + state lock; removes contributed sources from `~/.agent-tools/<source-id>/` if no other org references them; invalidates affected conflict resolutions; runs cleanup pass on per-project applied policies.

## Conflict Resolution

### Principles (from brainstorm, locked)

- **P1 — Silence is the default.** Most items are silent across most orgs. Most "conflicts" don't exist.
- **P2 — AEC never resolves disagreements on the user's behalf.** Whenever two orgs disagree, or AEC notices something a reasonable person might call a safety concern (unsigned config, downgraded version pin, source URL change, broad disallow-list), AEC surfaces it for the user to decide.
- **P3 — Decisions are explicit, persisted, and invalidated when inputs change.** Resolutions are keyed against the exact org configs that produced the conflict. Any input change re-prompts.
- **P4 — Enrollment order is presentation order only, not authority.** No implicit precedence.
- **P5 — Conflicts and unresolved decisions are loud.** `aec doctor` and `aec org status` always surface them.
- **P6 — Orgs cannot reach into other orgs' items.** Only declare policy on items in sources the org owns or in AEC defaults. Cross-org policy is a parse error, not a conflict.
- **P7 — Unresolved conflicts halt only the conflicting items.** Everything unambiguous applies; conflicting items are pending user decision.

### Conflict types detected

| Type | Example |
|---|---|
| Stance | A: required, B: blocked (same item) |
| Version | Both required/pinned but incompatible version constraints |
| Source replacement | A: keep defaults, B: replace defaults |
| Preference | A: projects_dir=~/work/acme; B: projects_dir=~/code |
| Install-mode | A: managed; B: guided |
| Project-rule | Two orgs match same git_remote pattern with incompatible profiles |
| **P6 violation** (not a conflict) | Org A declares policy on Org B's source — entire org A config halts loading |

### Detection timing

Conflict scan runs after each org's policy loads but before applying. Triggers:

- New org enrolled
- Existing org's config hash changes
- Org removed (some prior conflicts may now be moot)
- `aec org status` invoked (read-only re-scan)

### Resolution data structure

`~/.aec/conflict-resolutions.json`:

```json
{
  "schema_version": "1.0",
  "resolutions": [
    {
      "id": "res-7f3a2b",
      "kind": "stance",
      "subject": {
        "type": "skill",
        "name": "secure-coding-v2",
        "source": "aec.default.skills"
      },
      "inputs": [
        { "org_id": "acme",   "config_hash": "sha256:abc...", "stance": "required" },
        { "org_id": "globex", "config_hash": "sha256:def...", "stance": "blocked" }
      ],
      "decision": "honor:acme",
      "decided_at": "2026-05-04T12:34:56Z",
      "decided_by": "matt@bernierllc.com",
      "notes": null
    }
  ]
}
```

The `inputs` array is the invalidation key. On every conflict re-scan:

1. Compute current set of conflicts.
2. For each, check if a resolution exists whose `inputs` exactly match the current state.
3. Match → honor the resolution.
4. No match → unresolved conflict. AEC removes any stale resolution whose inputs no longer match (auto-prune).

### Decision vocabulary

- `honor:<org-id>` — apply that org's stance, ignore others
- `skip` — apply nobody's stance; treat as silent (conservative)
- `custom:<value>` — for non-stance conflicts (e.g., picking a specific `projects_dir`)
- `defer` — same as no resolution; AEC will re-prompt every interactive run

### Prompt UX

Conflicts surface at the next interactive `aec` command (not on `aec doctor`, which is read-only). If unresolved conflicts exist when the user runs `aec install`/`aec setup`/`aec update`, AEC pauses before any apply work and walks through them one at a time:

```
$ aec update

3 unresolved org conflicts. Let's resolve them before applying anything.

[1/3] Conflict on skill 'secure-coding-v2' (source: aec.default.skills):
  - acme   (config v3.2.0, hash abc...) → required (>=2.0.0)
  - globex (config v1.4.0, hash def...) → blocked

  How would you like to handle this?
    1. Honor acme (install secure-coding-v2 >=2.0.0)
    2. Honor globex (do not install)
    3. Skip — install nothing for this item
    4. Defer — ask me again next time
    5. Show me the skill (opens source URL or local path)

  Choice [1-5]: _
```

Non-interactive contexts (CI, `--yes`, scripts) → AEC refuses to apply policy on conflicting items, applies everything else (P7), exits 0 with a clear "N items pending decision" message. Never silently picks a winner.

### Audit trail

Resolutions are append-mostly: when a resolution is invalidated and replaced, the old one moves to `~/.aec/conflict-resolutions.history.json` with `invalidated_at` timestamp and the reason. Bounded retention (last 100 entries, oldest pruned).

## CLI Surface

### New subcommand group: `aec org`

```
aec org enroll <url-or-path>      # add a new org config
aec org list                      # list enrolled orgs (id, name, version, trust, last applied)
aec org status [<org-id>]         # detailed status
aec org show <org-id>             # print resolved/effective config (--raw for as-is)
aec org diff <org-id>             # show what would change if applied (read-only)
aec org sync [<org-id>]           # re-fetch URL-sourced configs, then apply
aec org remove <org-id>           # unenroll
aec org trust-rotate <org-id>     # acknowledge pubkey rotation (interactive)
aec org reorder                   # interactive reorder (display order only)
aec org resolve                   # interactive walkthrough of unresolved conflicts
aec org resolve --redo <res-id>   # re-prompt a previously decided resolution
aec org resolutions               # list current resolutions
aec org resolutions --clear       # wipe all resolutions
aec org pubkey verify <org-id>    # show pinned pubkey fingerprint and source
```

### New flags on existing commands

```
aec install --org-config <url-or-path>
aec install --org-config <url-or-path> --allow-unsigned
aec install --no-org-discovery               # ignore pre-staged ~/.aec/orgs/*.yaml
aec setup [path] --org-context <org-id>      # force project to match a specific org
aec update --skip-org-refresh                # update items without re-fetching org configs
aec doctor                                   # adds Org configurations section
```

### Environment variables (CI / managed-machine support)

```
AEC_ORG_CONFIG=<url-or-path>      # equivalent to --org-config
AEC_ALLOW_UNSIGNED=1              # equivalent to --allow-unsigned
AEC_NO_ORG_DISCOVERY=1            # disable passive ~/.aec/orgs/ discovery
AEC_NON_INTERACTIVE=1             # existing; with org configs, refuses to apply unresolved
                                  # conflicts (rather than prompting)
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (or success-with-warnings; warnings on stderr) |
| 1 | Generic error (existing AEC behavior) |
| 10 | Trust verification failure |
| 11 | Unresolved conflict in non-interactive mode |
| 12 | P6 violation (cross-org policy) — refused to load |
| 13 | Schema validation failure on org config |

## Documentation Plan

```
docs/
├── users/
│   └── org-configs.md              (NEW) end-user guide
├── orgs/                           (NEW directory)
│   ├── authoring-org-configs.md    full schema reference
│   ├── hosting-and-distribution.md DNS-anchor setup, MDM patterns, hosting
│   ├── signing-keys.md             ed25519 generation, rotation, well-known endpoint
│   └── examples/
│       ├── minimal.yaml
│       ├── full-managed.yaml
│       └── multi-source.yaml
└── contributors/
    └── adding-org-config-support.md  internal: overlay engine architecture
```

### README updates

New "AEC for Individuals, Teams, and Organizations" section near the top of the README, with links out to the user-facing and org-author-facing guides. Note: AEC never hosts org configurations; each organization publishes their own privately.

A second short subsection in the existing setup flow links: *"If your organization gave you an AEC config, run `aec install --org-config <url-or-path>` instead."*

## Migration & Backward Compatibility

- **Users without org configs:** zero impact. Behavior unchanged when `~/.aec/orgs/` is empty and no `--org-config` is passed.
- **Existing `.aec.json` per-project files:** untouched. Per-project `.aec.json` always wins over org overlays for any field they both touch (project local truth is more specific).
- **Existing `~/.aec/prefs.json`:** untouched. Org `install.preferences` apply only on first enrollment if a key is unset, or in `install.mode: managed` (where org has authority by user opt-in).
- **Schema versioning:** `schema_version: "1.0"` required from day one. AEC refuses to load configs declaring an unknown future schema version with an "upgrade aec" message.
- **Old `aec` versions encountering org configs:** without org-config support, `aec` simply ignores `~/.aec/orgs/`. `aec install --org-config <url>` errors cleanly with "this version of aec doesn't support org configs; upgrade with `pip install -U aec[org-configs]`."

## Rollout Plan (Phased)

Each phase ships a useful slice. No phase blocks individual users.

**Phase 1 — Schema + parser + unsigned mode**
- Schema definition, validator, loader for `~/.aec/orgs/`
- `items` + `sources` + `preferences` blocks (core 60% of value)
- Single-org only (multi-org parsing rejected with clear error)
- Trust mode: `unsigned` only, with loud warning
- Commands: `aec org enroll`, `list`, `status`, `show`, `remove`
- Docs: `docs/users/org-configs.md`, `docs/orgs/authoring-org-configs.md`
- Ships behind `pip install aec[org-configs-preview]`

**Phase 2 — Signing & trust modes**
- `pinned_key` and `dns_anchor` modes via `pynacl`
- Pubkey rotation flow + `aec org trust-rotate`
- Well-known endpoint discovery
- Docs: `docs/orgs/signing-keys.md`, `docs/orgs/hosting-and-distribution.md`
- Promote to `pip install aec[org-configs]`

**Phase 3 — Multi-org + conflicts**
- Multiple concurrent enrollments
- Conflict detection + resolution data structure + persistence
- `aec org resolve` walkthrough, P6 enforcement
- Stale-resolution invalidation + audit trail

**Phase 4 — Project matching + install-flow control**
- `projects[]` matching with `git_remote` and `directory` patterns
- `install.mode`, `install.agents`, `install.preferences`, `install.prompts`, `enrollment_script`
- `aec setup --org-context` flag

**Phase 5 — MDM polish**
- Refresh TTL handling
- `branding` block (welcome message, doctor footer)
- Exit-code standardization for CI/MDM
- Optional `aec daemon-check` for managed-machine periodic refresh
- Org-config support promoted out of preview-extras (still gated behind `[org-configs]` for crypto)

## Open Questions

None blocking. Items the implementation plan should call out:

1. Exact subset of AEC preference keys allowed in `install.preferences` (audit existing keys; some may not be safe to org-set).
2. Exact subset of named prompts allowed in `install.prompts` (need stable IDs per prompt).
3. Whether `aec org sync` should be on a default cron via `aec daemon-check` or always opt-in (defer to Phase 5 user feedback).
4. Specific glob semantics for `git_remote` patterns: do we normalize SSH vs HTTPS forms? (Likely yes — match against canonical `host:owner/repo` form.)

## Appendix: Schema Validation Errors (selected)

For author UX, the loader produces precise error messages:

- `org-config has stance on item 'X' but no source field` → schema error
- `item 'X' references source 'Y' which is not declared in sources.custom and not a reserved aec.default.* ID` → schema error
- `org 'A' declares policy on item from source 'acme-skills' which is owned by org 'B'` → P6 violation, halt
- `schema_version '2.0' is unknown to this version of aec; upgrade with pip install -U aec[org-configs]` → version mismatch
- `multiple items at items.skills have name 'foo' with source 'aec.default.skills'` → duplicate
- `enrollment_script[3].action 'run' is not a recognized action; allowed: add_source, install_items, set_hooks, run_doctor, set_pref` → escape-hatch attempt blocked
