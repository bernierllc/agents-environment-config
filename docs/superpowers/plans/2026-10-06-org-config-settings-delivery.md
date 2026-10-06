# Org-config settings & file delivery (git-sourced org configs)

Status: proposed — ROADMAP Tier 2, after org-config plugin governance
Revision: 2 (2026-10-06) — reworked after adversarial review: content-hash trust model, allow-lists over denylists, lifecycle and unattended semantics, phased delivery
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

- **Claude Code managed settings** (`/Library/Application Support/ClaudeCode/managed-settings.json`
  on macOS) is root-owned and per machine. It moves the copy somewhere harder
  to edit; it doesn't remove the copy.
- **A dotfiles repo with `~/.claude/settings.json` symlinked into it.** Claude
  Code writes machine-local keys to that file (`/model`, `theme`,
  `enabledPlugins`, permission-prompt answers), so the repo would churn on every
  UI toggle, and every machine would share keys that are supposed to differ.
  Claude Code's settings layering (managed / user / project / local) has no
  user-level layer that is "org-owned keys only". That gap is the reason for an
  owned-key merge: **the org owns a declared set of keys in one file that the
  machine also writes, and every other key stays the machine's.**
- **`aec export` / `aec apply` manifests** describe installed *items*. They have
  no settings or files either.

## Design principles

1. **Repo content is trusted only through the config.** The org YAML is the one
   object that gets signed and hashed today, so every fragment and file it
   delivers is pinned by sha256 *inside* the YAML. A signed config then
   authenticates its content transitively. An unsigned config is treated as
   what it is: whoever can push to the repo can change what lands on the machine.
2. **Allow-lists, never denylists**, for what can be delivered: top-level
   settings keys, destination paths, and source file types. This follows
   `PREFERENCES_ALLOW_LIST`.
3. **Exec-capable content is a separate, louder class.** Settings keys that make
   the agent run commands (`hooks`, `permissions`, `statusLine`, `mcpServers`,
   `apiKeyHelper`, …) and any delivered file are "exec-capable". They are never
   applied unattended from an unsigned source.
4. **Never silently overwrite, never silently skip.** Drift and refusals are
   persisted as pending state and surfaced on every later `aec` command until
   they are resolved.
5. **Ship in phases**, so the parts that can run code land only after the trust
   model is in place.

## Phase 1 — git-sourced org configs, refresh-then-apply

### Enrollment

```bash
aec org enroll git+https://github.com/my-org/aec-catalog.git#main:org/my-org.yaml
```

- New module `aec/lib/org_config/git_source.py`. `fetch.py` stays the
  https-GET-only module its docstring promises. It follows `sources.py`'s
  subprocess and debug-logging pattern (`_debug.log_subprocess_failure`).
- **Input validation (enroll time and every refresh):**
  - The URL scheme must be `https://` or scp-style `git@host:path`. Reject
    `file://`, `ext::`, and anything starting with `-`.
  - `ref` must match `^[A-Za-z0-9._/-]+$` and must not start with `-`.
  - The config path inside the repo is normalized and must stay inside the
    clone after `resolve()`.
- **Invocation:**
  - Use an argv list (no shell) with `--` before positional URL and ref.
  - Pass `-c protocol.allow=never -c protocol.https.allow=always -c protocol.ssh.allow=always`.
  - Set env `GIT_TERMINAL_PROMPT=0`, plus a timeout.
  - Clone with `clone --depth 1 --branch <ref>`.
  - Refresh does `fetch --depth 1 origin <ref>` then `checkout --detach FETCH_HEAD`. AEC owns the clone, so force-pushes and moved tags are followed, not failed on.
- **Credentials:** the user's own git setup (credential helper, ssh agent). AEC
  never stores credentials.
- **Clone location:** `~/.aec/orgs/<org_id>.d/repo/`. The `.d` suffix keeps it
  out of `discover_enrolled_orgs`' `*.yaml` glob. `org_id` gains charset
  validation (`^[a-z0-9][a-z0-9-]{0,62}$`) in `validator.py`. That also closes
  the existing traversal path in `OrgPaths.config_for`.
- **Signatures:** for `pinned_key` / `dns_anchor` orgs, the detached signature
  is a sibling file in the repo (`org/my-org.yaml.sig`), read from the same
  commit. `_signature_for_url` gets a git counterpart. Verification and key
  rotation are otherwise unchanged.

### State

- `OrgState` gains `source_of_record: "git"`, plus `source_repo`, `source_ref`,
  `source_path`, `resolved_commit`, and `pending: Optional[dict]` (see
  Lifecycle). All new fields have defaults.
- `read_state` ignores unknown keys instead of `OrgState(**data)` raising on
  them, so an older AEC can read a newer state file.
- `remove_cmd` also deletes `<org_id>.d/`.

### Refresh then apply (all source kinds)

`aec update` → `_refresh_org_configs` changes for every source kind:

| Situation | Behavior |
|---|---|
| Content unchanged (commit and hash) | Nothing is written. |
| Changed, **signed** org, `install.mode: managed` | Re-verify, re-enroll, apply non-interactively. |
| Changed, **unsigned** org, or `guided` mode | Re-enroll, **do not apply**. Record `pending: {kind: "review", commit, summary}`. Print the plan diff and the command (`aec org apply`). |

This replaces today's `perform_enroll(..., allow_unsigned=True, yes=True)` in
`refresh_url_sourced_orgs`, which silently re-consents to changed unsigned
content. The `last_applied_at` that enrollment currently stamps at enroll time
(`org.py:304`) moves to the moment apply actually succeeds.

### Pending state is loud

- Any org with `pending` set makes `aec update` exit **non-zero** (2).
- `aec doctor` and `aec org status` show the pending item and its fix.
- Every interactive `aec` command prints a one-line banner naming it.
- `pending` clears only when an apply succeeds or the user declines that commit
  (`aec org apply --decline <commit>`).
- AEC has no scheduled update runner; `scheduled_runner_entrypoint.py` runs tests
  only. Unattended delivery means a user's own cron or launchd job running
  `aec update`, and a non-zero exit is how that job learns something needs a human.

### Migration

`aec org enroll --replace <git source>` swaps an enrolled org's source of
record and keeps its conflict resolutions and key-trust records. It replaces
the manual remove-then-enroll-then-apply sequence, which would lose them.

## Phase 2 — custom sources install

The review found this needs more than `_catalog`:

- `DesiredItem` (`apply_core.py:27-34`) gains `source_id`.
  `compile_desired_items` stops dropping `ItemPolicy.source`.
- `plan_apply` / `execute_apply` take source dirs keyed by
  `(source_id, item_type)` rather than by type alone.
- Each custom source clones through `git_source.py` (same validation) to
  `<org_id>.d/sources/<id>/`. A custom source whose URL equals the config's
  own repo reuses that clone.
- **Content is pinned:** a custom source must declare `commit:` (a full sha), not
  just `ref`. Signing the YAML then authenticates the source content too. A
  `ref`-only custom source is accepted only for unsigned orgs, and every change
  to it goes through the "pending review" path above.
- **Provenance:** `manifest_v2` records `source_id` per installed item, so
  `aec upgrade` / `aec outdated` / `aec update`'s outdated report
  (`update.py:_report_scope_outdated`) resolve the item against its own source
  instead of `get_source_dirs()`.
- Drop the "declared but unimplemented" caveat from the org-config docs.

## Phase 3 — `agent_settings` and `files`

### `agent_settings`

```yaml
agent_settings:
  claude:                         # agent key, not a path
    fragment: "claude/settings.fragment.json"
    sha256: "<hex>"               # pinned; mismatch refuses to apply
    owned_keys: ["autoMode", "autoCompactWindow"]
```

- **Target is an agent key**, mapped by AEC (`claude` → the Claude user settings
  file). There is no user-supplied path. `codex` (TOML) is deferred.
- **Closed allow-list of deliverable top-level keys**
  (`AGENT_SETTINGS_KEYS_ALLOW_LIST` in `allow_lists.py`, documented in the
  allow-lists spec addendum):
  - *config-only:* `autoMode`, `autoCompactWindow`, `cleanupPeriodDays`,
    `includeCoAuthoredBy`, `outputStyle`, `alwaysThinkingEnabled`;
  - *exec-capable:* `hooks`, `permissions`, `statusLine`.

  Anything else is rejected at enrollment. Keys such as `env`, `apiKeyHelper`,
  `mcpServers` and `model` are absent on purpose. `model` is something users
  change with `/model`, so owning it would trip drift constantly.
- **`owned_keys` must equal the fragment's top-level keys.** Each owned key is
  replaced wholesale (ordered lists like `autoMode.allow` must not be merged).
- **Value scan, as defense in depth:** reject a fragment whose string values
  match common secret shapes (`sk-`, `ghp_`, `xox[bp]-`, `AKIA`, PEM headers,
  long high-entropy tokens).
- **Write mechanics:**
  - Resolve the real path, so a dotfiles symlink is edited in place, not
    replaced.
  - Refuse if the file isn't strict JSON. Never rewrite a file AEC couldn't
    parse.
  - Back up to `<file>.aec-bak/<UTC>.json` and keep the last 5.
  - Write a temp file in the same directory.
  - Re-read the target and compare its mtime and hash immediately before
    `os.replace`. If it changed (Claude Code wrote it meanwhile), redo the
    merge once, and refuse on a second race.
  - Preserve the file's mode.
- **Guarantee, stated precisely:** keys outside `owned_keys` are *semantically*
  unchanged (parsed-equal). The file is re-serialized with 2-space indent, and
  byte-identity is not promised.

### `files`

```yaml
files:
  - src: "codex/AGENTS.md"
    sha256: "<hex>"
    dst: "codex:AGENTS.md"         # agent-relative, from an allow-list
  - src: "claude/references/"
    manifest_sha256: "<hex>"       # hash of the sorted (path, sha256) list
    dst: "claude:references/"
```

- **dst is an allow-listed agent-relative slot** (`FILES_DST_ALLOW_LIST`):
  `claude:CLAUDE.md`, `claude:references/`, `codex:AGENTS.md`, `gemini:GEMINI.md`.
  Settings files, `skills/`, `agents/`, `commands/`, `hooks/` and every
  AEC-managed subtree are unreachable by construction.
- **src rules:**
  - Normalized, and must resolve inside the clone.
  - Regular files only: a symlink tracked in the repo is refused.
  - Allowed extensions: `.md`, `.txt`, `.json`, `.yaml`, `.toml`; binaries are
    refused.
  - Comparisons are case-insensitive on case-insensitive filesystems.
- **dst rules at apply time** (not just validate time):
  - Refuse if dst, or any parent between the agent root and dst, is a symlink.
  - Write with temp file plus `os.replace`.
  - A directory slot mirrors only files the repo tracks, and never deletes files
    AEC didn't deliver.
- All delivered files count as exec-capable, since agents read them as
  instructions.

### Trust gating (Phase 3)

| Org trust | config-only keys | exec-capable keys and `files` |
|---|---|---|
| signed, hashes match | apply (managed) / confirm (guided) | apply (managed) / confirm (guided) |
| unsigned | confirm on every change | confirm on every change, with the full diff of each exec-capable key and file shown; never applied by `aec update` |

Any hash mismatch refuses that block outright.

### Drift and lifecycle

- **Applied hashes** are recorded per owned key (canonical JSON: sorted keys, no
  whitespace) and per delivered file.
- **Drift** means the on-disk value no longer matches its recorded hash. Apply
  refuses that key or file, sets `pending: {kind: "drift", …}` (loud, as in
  Phase 1), and shows the diff plus both fixes: move the edit into the catalog,
  or `aec org apply --overwrite-drift`.
- **First apply (no recorded hash):** if the on-disk value already equals the
  incoming value, adopt it silently. Otherwise treat it as drift. This is the
  migration path for machines that were hand-synced.
- **Key dropped from `owned_keys`, or a file from the repo:** AEC stops
  managing it, leaves it in place, and reports it as released.
- **`aec org remove`:** leaves delivered keys and files in place, lists them as
  released, and deletes the clone and state.
- **Interaction with items:** a pending drift or review blocks only the
  affected settings key or file. Items and preferences still apply.

### Multi-org conflicts

- New conflict subjects: `settings:<agent>/<key>` and `file:<agent>:<slot>`.
  Slots come from the allow-list, so normalization is by construction.
- Resolutions are `honor:<org_id>` or `skip`. They are held in
  `EffectivePolicy.held` and reopened when any contributing config hash changes,
  like the existing subjects.

### Authoring guidance: machine-neutral content

One copy only works everywhere if the content never says "this machine".
Content that varies by machine names every machine instead. For example, an
`autoMode` environment entry reads "the user's developer machines: a laptop
(`my-laptop`) and a desktop (`my-desktop`), joined over a private network",
not "this Mac and the other one". Likewise, per-machine "ssh to the other
machine" allow rules become one rule that names both hosts. The authoring doc
recommends a catalog-side content test that fails on `this Mac` / `this
machine` in a fragment.

## Affected surfaces

| Surface | Phase | Change |
|---|---|---|
| `aec/lib/org_config/git_source.py` (new) | 1 | Validated clone/fetch/checkout; argv-only; protocol allow-list |
| `aec/lib/org_config/validator.py` | 1–3 | `org_id` charset; git source syntax; custom `commit:`; new blocks, allow-lists, sha256 fields, value scan |
| `aec/lib/org_config/paths.py` | 1 | `<org_id>.d/` clone and sources dirs |
| `aec/lib/org_config/state.py` | 1, 3 | git fields, `pending`, applied hashes; tolerant `read_state` |
| `aec/lib/org_config/trust.py`, `aec/commands/org.py` | 1 | Signature sibling-file for git; `enroll --replace`; `apply --decline`, `--overwrite-drift`; remove deletes clone |
| `aec/commands/update.py` | 1 | Refresh-then-apply table; non-zero exit on pending |
| `aec/commands/doctor.py`, CLI banner | 1 | Surface `pending` |
| `aec/lib/org_config/apply.py`, `aec/lib/apply_core.py` | 2, 3 | `source_id` on `DesiredItem`; per-source dirs; `apply_agent_settings`, `apply_files` |
| `manifest_v2`, upgrade/outdated paths | 2 | Per-item `source_id` provenance |
| `aec/lib/org_config/allow_lists.py` + allow-lists spec addendum | 3 | `AGENT_SETTINGS_KEYS_ALLOW_LIST` (with exec-capable class), `FILES_DST_ALLOW_LIST`, `FILES_SRC_EXTENSIONS` |
| `aec/lib/org_config/effective.py`, `conflicts.py` | 3 | New conflict subjects |
| `docs/orgs/authoring-org-configs.md`, `docs/users/org-configs.md`, `docs/qa-verification.md` | 1–3 | git enroll, trust table, pending, drift, migration, machine-neutral authoring |

**Platform:** POSIX only, as org-config already is (`state.py` uses `fcntl`).
Paths go through `expanduser().resolve()` plus `os.path.normcase`.

## Tests (real filesystem, real git; no mocks of code AEC owns)

Phase 1:
- Enroll from a local bare repo served over a `file://`-free transport. Use a
  test-only `protocol.file.allow` override scoped to the test git config, and
  say so in the test.
- Rejected: `ref` = `--upload-pack=x`; URLs `ext::sh -c x`, `file:///tmp/x`, and
  `-oProxyCommand=x`; `org_id` = `../x`; a config path escaping the clone.
- Force-pushed ref → refresh follows it.
- Unsigned changed commit → `aec update` exits 2, `pending` recorded, nothing
  applied. `--decline` clears it.
- Signed + managed changed commit → applied. Signed with a bad sig → refused.
- Backward compatibility: existing local and url state files load; the existing
  `tests/commands/test_org_refresh.py` passes; an unknown state key is ignored.
- `enroll --replace` keeps resolutions; `remove` deletes `<org_id>.d/`.

Phase 2:
- An item from a custom source installs, and `aec upgrade` / `outdated` resolve
  it against that source.
- Custom source without `commit:` in a signed org → rejected.

Phase 3:
- Apply writes owned keys, and non-owned keys are parsed-equal before and after.
- Symlinked settings file → edited through the link, and the link survives.
- Invalid or commented JSON → refused, file untouched.
- Concurrent write between read and replace → merge redone once; a second race
  → refused. The race is simulated by writing the file from the test between
  the hooks; `os.replace` is patched only to inject the write, which is an
  OS-boundary patch.
- Rejected:
  - a key outside the allow-list (`env`, `model`, `mcpServers`);
  - `owned_keys` not equal to the fragment's keys;
  - a secret-shaped value;
  - a sha256 mismatch;
  - a `files` src that is a tracked symlink, escapes with `..`, or is a binary;
  - a dst slot not on the allow-list;
  - a dst whose parent is a symlink.
- Drift: a hand-edit is refused, `pending` is set, and `--overwrite-drift`
  applies.
- First apply: an equal value is adopted, and a differing value counts as drift.
- Key dropped / file dropped / `org remove` → content left in place and
  reported as released.
- Unsigned org with an exec-capable key → never applied by `aec update`.
- Two orgs owning `autoMode` → conflict held and nothing written for that key.

## Rollout

1. Ship Phase 1 and release. Existing local enrollments keep working; migrate
   with `aec org enroll --replace git+…`.
2. Phase 2, then release.
3. Phase 3, then release. Catalog authors add fragments and files with their
   sha256 pins. A `aec org pin` helper writes the hashes into the YAML so
   nobody computes them by hand.

## Open questions

None blocking. Deferred: Codex `config.toml` (TOML merge) until there is a
concrete owned key to deliver.
