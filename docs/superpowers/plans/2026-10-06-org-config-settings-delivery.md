# Org-config settings & file delivery (git-sourced org configs)

Status: proposed — ROADMAP Tier 2, after org-config plugin governance
Priority: High (org-wide agent settings are hand-synced per machine today)
Discovered: 2026-10-06, syncing a Claude Code `autoMode` block between two machines by hand

## Problem

A user who runs Claude Code / Codex on more than one machine, or an org that
wants every member's agents configured alike, keeps the agent configuration
that matters in hand-maintained per-machine copies:

| Artifact | Location |
|---|---|
| Auto-mode classifier context + allow/deny rules | `~/.claude/settings.json` → `autoMode` |
| Other org-wide Claude settings | `~/.claude/settings.json` → `autoCompactWindow`, `model`, `hooks`, … |
| Global agent rules | `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md` |
| Rule references read on demand | `~/.claude/references/*.md` |

Observed in maintainer use: one `autoMode` change was authored on machine A,
pasted to machine B, rewritten by hand where it said "this Mac", and then a
follow-up rule needed a second round trip. Every round trip is a chance for the
machines to drift without anyone noticing.

## Incumbent and why it is insufficient

AEC already has the right shape: an **org config**, typically authored in a
private catalog repo (`my-org/aec-catalog` → `org/my-org.yaml`). It cannot do
this job yet, for three reasons:

1. **No slot for agent settings or files.** The body is `sources`, `items`
   (skills/rules/agents/mcps), and `install.preferences` / `install.prompts`,
   both closed allow-lists of *AEC* preferences
   (`aec/lib/org_config/allow_lists.py`). An org cannot say "these keys belong
   in the Claude user settings file" or "this file belongs at the Codex global
   AGENTS.md".
2. **Custom git sources are validated but never fetched.**
   `validator.py:97-109` parses `sources.custom[]` and accepts their IDs as
   item sources, but nothing clones them: `apply.py:_catalog` only discovers
   AEC's built-in catalog directories via `get_source_dirs()`. An item whose
   `source` is a custom ID is silently never installed.
3. **Private repos can't be delivered as a config URL.** Refresh
   (`commands/org.py:refresh_url_sourced_orgs`) only re-fetches `https://`
   configs, using an unauthenticated GET (`fetch.py`), so a private catalog
   404s. Locally enrolled configs (`source_of_record: local`) are never
   refreshed, so edits to the catalog never reach enrolled machines. Refresh
   also re-enrolls without re-applying.

Not chosen:

- **Claude Code managed settings** (`/Library/Application Support/ClaudeCode/managed-settings.json`)
  is root-owned and per machine. It moves the copy somewhere harder to edit; it
  doesn't remove the copy.
- **Symlinking `~/.claude/settings.json` into a repo.** Claude Code writes
  machine-local keys to that file (`/model`, `theme`, `enabledPlugins`,
  `statusLine`), so the repo would churn on every UI toggle.
- **`aec export` / `aec apply` manifests** describe installed *items*. They have
  no settings or files either.

## Design

### 1. Git-sourced org configs

`aec org enroll` accepts a git source in addition to a path or an `https://`
YAML URL:

```bash
aec org enroll git+https://github.com/my-org/aec-catalog.git#main:org/my-org.yaml
```

- AEC clones the repo with the user's own git credentials (plain `git clone`
  through `subprocess`, the same way `sources.py` already shells out to git; no
  new dependency) into `~/.aec/orgs/<org_id>/repo/`, checks out `ref`, and reads
  the config at the given path.
- `OrgState` gains `source_of_record: "git"` with `source_repo`, `source_ref`,
  `source_path`, and the `resolved_commit` that was applied.
- `aec update` fetches, fast-forwards to `ref`, and if the resolved commit
  changed, re-enrolls **and re-applies** (fixing the "refresh without apply"
  gap for every source kind). Unsigned-config consent is still required at
  first enroll and is remembered per `(org_id, source_repo)`.
- The same clone backs `sources.custom[]` entries with that URL, so declaring
  the catalog as a custom source and as the config's own home costs one clone,
  not two. Other custom sources clone to `~/.aec/orgs/<org_id>/sources/<id>/`.

### 2. Custom sources actually install

`_catalog` merges custom source directories into `source_dirs` /
`available_by_type` keyed by source ID, so `items.<type>.<name>.source:
"my-org-catalog"` resolves against the cloned repo's layout (the same
layout AEC's built-in catalog uses: `.cursor/rules/**`, `.claude/skills/**`,
…).

### 3. New org-config block: `agent_settings`

Settings fragments are deep-merged into an agent's **user** settings file.
Each key the fragment names is owned by the org. Every other key stays
machine-local and untouched.

```yaml
agent_settings:
  claude:
    target: "~/.claude/settings.json"
    fragment: "claude/settings.fragment.json"   # path inside the org repo
    owned_keys: ["autoMode", "autoCompactWindow", "model"]
```

Rules:

- `owned_keys` is explicit. A key in the fragment that isn't in `owned_keys`
  fails validation, and so does an `owned_keys` entry missing from the fragment.
  Ownership is declared, never inferred from what happens to be in the file.
- An owned key is **replaced wholesale** (not list-merged). `autoMode.allow` is
  an ordered list the classifier reads as a whole, so merging two lists would
  silently reorder or duplicate rules.
- `targets` is a closed allow-list per agent (start with `claude` →
  `~/.claude/settings.json`, `codex` → `~/.codex/config.toml` deferred until
  someone needs it). Arbitrary paths are refused.
- **Denied keys:** `env`, `apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`,
  and any key whose name matches `(?i)token|secret|password|key$`. Secrets
  never travel in an org repo (global rule: secrets only in `.env*`).
  `permissions` and `hooks` are allowed but flagged in the guided-mode plan as
  "changes what agents may run without asking".
- Write is atomic (temp file + `os.replace`), preceded by a timestamped backup
  `settings.json.aec-bak-<UTC>` (last 5 kept).
- **Drift detection:** state records a hash of each owned key's applied value.
  On apply or update, if the on-disk value no longer matches the recorded hash
  (someone hand-edited it on this machine), AEC refuses to overwrite and prints
  the diff plus the fix: move the change into the org repo or
  `aec org apply --overwrite-drift`. `aec doctor` reports the drift too. This is
  the guard that stops "edited it on one machine, forgot the other" from coming back.

### 4. New org-config block: `files`

```yaml
files:
  - src: "codex/AGENTS.md"
    dst: "~/.codex/AGENTS.md"
  - src: "claude/references/"
    dst: "~/.claude/references/"
```

- `dst` must be under `~/.claude/`, `~/.codex/`, `~/.gemini/`, or `~/.cursor/`.
  Refused: anything else, plus any `src` that matches `.env*`, `*.pem`, `*.key`,
  or `secrets*`.
- Delivered as **copies**, not symlinks, so a moved or recloned catalog can't
  leave dangling links (see "Managed symlink ownership by record" on the
  roadmap). Directory `src` mirrors only files the repo tracks; files in `dst`
  that the repo never delivered are left alone.
- Same drift guard as settings: a per-file applied hash, refuse-and-explain on
  local edits.

### 5. Machine-neutral content (authoring guidance)

One copy only works everywhere if the content never says "this machine".
Content that varies by machine names every machine instead. For example, an
`autoMode` environment entry reads "the user's developer machines: a laptop
(`my-laptop`) and a desktop (`my-desktop`), joined over a private network",
not "this Mac and the other one". Likewise, per-machine "ssh to the other
machine" allow rules become one rule that names both hosts.
`docs/orgs/authoring-org-configs.md` documents this, and catalog repos are
encouraged to add a content test that fails on `this Mac` / `this machine`
inside a settings fragment.

## Affected surfaces

| Surface | Change |
|---|---|
| `aec/lib/org_config/schema.py` | `AgentSettingsPolicy`, `FilePolicy` dataclasses; `OrgConfig.agent_settings`, `OrgConfig.files` |
| `aec/lib/org_config/validator.py` | Validate new blocks (owned-key parity, target and dst allow-lists, denied keys/paths); git source syntax |
| `aec/lib/org_config/allow_lists.py` | `AGENT_SETTINGS_TARGETS`, `AGENT_SETTINGS_DENIED_KEYS`, `FILES_DST_ROOTS`, `FILES_SRC_DENY` |
| `aec/lib/org_config/fetch.py` | Git clone/fetch helper (subprocess `git`, honors user credentials, timeout, non-interactive `GIT_TERMINAL_PROMPT=0`) |
| `aec/lib/org_config/state.py` | `source_of_record: "git"`, repo/ref/path/commit; per-key and per-file applied hashes |
| `aec/lib/org_config/apply.py` | `apply_agent_settings`, `apply_files` after items; `_catalog` includes custom sources; plan output lists settings/file changes |
| `aec/lib/org_config/effective.py`, `conflicts.py` | Two orgs owning the same settings key or `dst` is a conflict resolved via `aec org resolve` (never silent last-writer-wins) |
| `aec/commands/org.py` | `enroll` accepts `git+https://…#ref:path`; `refresh_*` covers git and re-applies on change; `apply --overwrite-drift` |
| `aec/commands/update.py` | `_refresh_org_configs` re-applies when the commit or hash changes |
| `aec/commands/doctor.py` | Report settings/file drift and stale git sources |
| `docs/orgs/authoring-org-configs.md`, `docs/users/org-configs.md` | New blocks, git enroll, machine-neutral authoring rule |
| `docs/qa-verification.md` | Enroll-from-git, apply, drift-refuse, update-propagates flows |

## Tests (real filesystem, real git; no mocks of code we own)

- Enroll from a local bare git repo (`git init --bare` in a tmp dir) → state
  records the commit; apply writes owned keys and leaves every other
  `settings.json` key byte-identical.
- Hand-edit an owned key → apply refuses, exits non-zero, names the key and the
  fix; `--overwrite-drift` applies.
- Push a new commit to the bare repo → `aec update` re-applies; unchanged commit
  → no write (mtime unchanged).
- Validator rejects: an owned key missing from the fragment, a fragment key not
  in `owned_keys`, `env`, `*token*`, a `dst` outside the allowed roots, a `.env`
  src.
- Two enrolled orgs owning `autoMode` → conflict surfaced, nothing written for
  that key until resolved.
- Custom source item (`rules` from a custom git source) installs end to end.
- Atomic write: kill between temp write and replace leaves the original intact
  (simulate with a failing `os.replace` patched at the OS boundary only).

## Rollout

1. Land in AEC (this plan) and release.
2. Documented migration for an existing locally enrolled org:
   `aec org remove <org>` → `aec org enroll git+…#ref:path` → `aec org apply`.
   `aec doctor` confirms there's no drift.
3. After that, a settings change means: edit the catalog, merge, then
   `aec update` on each machine (or the scheduled runner does it).

## Open questions

None blocking. Codex `config.toml` (TOML merge) is deferred until there's a
concrete owned key to deliver.
