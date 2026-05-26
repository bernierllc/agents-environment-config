# Org Configurations

If your organization has standardized on AEC, your IT/admin team may give you an **org config** — a single YAML file describing which agents, skills, rules, and MCP servers your org expects you to use, and which preferences should apply when you run `aec install` or `aec configure`.

This page explains how to enroll, inspect, resolve conflicts between, and remove org configs. It covers Phase 1 enrollment plus the Phase 2 trust, delivery, and multi-org features; project-scoped overlays arrive later.

## Phase 1 status

Org configs ship as a preview feature behind an extras flag:

```bash
pip install "aec[org-configs-preview]"
```

Without the extra installed, the `aec org` command group is unavailable.

## What is an org config?

An org config is a YAML file (with a small JSON-like frontmatter) authored by your org. It declares:

- **Items** — which skills, rules, agents, and MCPs the org wants in your environment, and what stance to take on each (`required`, `recommended`, `blocked`, `pinned`, or `silent`).
- **Sources** — where those items come from. AEC's built-in catalog is one source; your org can add their own Git repositories as additional sources.
- **Preferences** — defaults for AEC-wide settings (e.g., `projects_dir`, `hook_mode`).

AEC never hosts org configurations. Each organization publishes their own — typically as a file in an internal repo or wiki, or distributed by IT.

## Enrolling

Enroll a local file or an `https://` URL:

```bash
aec org enroll /path/to/your-org-config.yaml --allow-unsigned --yes
aec org enroll https://acme.example/aec.yaml          # signed configs need no --allow-unsigned
```

Only `https://` URLs are accepted. AEC remembers the URL and re-fetches + re-verifies it on `aec update`; configs that set `refresh.ttl_hours` are also re-fetched automatically once the local copy ages out.

After enrollment, AEC stores two files under `~/.aec/orgs/`:

- `<org_id>.yaml` — the validated config (a verbatim copy of the source).
- `<org_id>.state.json` — local state: hash, trust mode, timestamps.

## Why "unsigned" matters

Phase 1 supports only the `unsigned` trust mode. **Unsigned configs have no cryptographic guarantee** that the file you enrolled came from your org and wasn't modified in transit. AEC will:

- Refuse to enroll an unsigned config without explicit consent (`--allow-unsigned` or interactive confirmation via `--yes` / typed `y`).
- Show the trust mode prominently in `aec org status` and `aec doctor` output.

Prefer a signed config (`pinned_key` or `dns_anchor`) whenever your org offers one — it removes the need to trust the delivery channel.

## Signed configs (`pinned_key`, `dns_anchor`)

Signed enrollment is available with the crypto extra:

```bash
pip install "aec[org-configs]"
```

- **`pinned_key`** — the config carries an inline ed25519 public key (or a `pubkey_url`) and ships with a detached signature.
- **`dns_anchor`** — the public key is published at `https://<dns_domain>/.well-known/aec-pubkey`; AEC fetches and verifies against it.

AEC finds the signature via `--signature <file>`, the config's `signature_url`, or a `<config>.sig` sibling:

```bash
aec org enroll acme.yaml --signature acme.yaml.sig
aec org enroll https://acme.example/aec.yaml          # dns_anchor: key fetched from the domain
```

On first enrollment AEC shows the public-key **fingerprint** and asks you to
confirm it matches what your IT/security team gave you (trust on first use).
Pass `--trust-fingerprint` to accept it non-interactively. The fingerprint is
pinned in the org's state file.

### Key rotation

If the signing key later changes, AEC warns you immediately on every command
with a countdown, and after a 30-day grace it **locks** org-config operations
until you acknowledge the new key:

```bash
aec org trust-rotate acme   # re-verify and pin the rotated key
```

## Multiple orgs & conflicts

You can enroll more than one org at once. AEC never silently picks a winner when
they disagree (on an item stance, version, default-source handling, a
preference, or install mode). Conflicts show up in `aec doctor` and
`aec org status`; resolve them interactively:

```bash
aec org resolve --list      # show open conflicts
aec org resolve             # walk through each, choosing which org to honor
```

Everything the orgs agree on still applies — only the conflicting items wait for
your decision. Your choices are remembered, and re-asked automatically if a
contributing config changes.

## Applying policy

Enrolling records an org's policy; **applying** it makes the changes — writing
preferences, pre-answering install prompts, installing `required`/`pinned`
items, and removing `blocked` ones:

```bash
aec org apply                 # apply enrolled policy
aec org apply --dry-run       # preview the plan, change nothing
aec org apply --enroll https://acme.example/aec.yaml   # enroll then apply in one step
```

- **Managed** orgs (`install.mode: managed`) apply silently; **guided** orgs
  show the plan and ask before changing anything (use `--yes` to auto-confirm,
  `--managed` to force silent).
- Items still waiting on a conflict decision are **held** — everything else
  applies, and `aec org apply` tells you how many remain for `aec org resolve`.
- If an org's signing key is in rotation lockout, apply refuses until you run
  `aec org trust-rotate`.

## Inspecting

```bash
aec org list                # all enrolled orgs
aec org status              # summary incl. trust mode, fingerprint, rotation status
aec org show <org_id>       # full validated config as YAML
aec org resolve --list      # any unresolved cross-org conflicts
aec doctor                  # "Org configurations" + "Org conflicts" sections
```

## Leaving

```bash
aec org remove <org_id> --yes
```

Removes both the YAML and the state file. Your `~/.agents-environment-config/` workspace is **not** modified — `aec org remove` only un-enrolls; it does not undo any item installs.

## Phase 4 features (what an enrolled config can now do)

Once enrolled, AEC honors these additional behaviors:

- **Per-project overlays.** Inside a repo whose remote/path matches your org's `projects[]`, `aec org apply` installs the profile's items into that repo's `.claude/...` (a separate `repos[]` entry in the manifest) — base policy still lives globally. No per-repo opt-in is needed; the overlay activates from cwd.
- **Time-bounded rules.** Items can declare an active window (`required_after` / `expires_at`). Outside that window the stance is silently dropped, so an expired blocking rule stops removing the item.
- **`enrollment_script`.** A closed action set (`add_source`, `install_items`, `set_hooks`, `run_doctor`, `set_pref`) runs on enroll. No shell, no arbitrary URLs. If a custom source can't be cloned (e.g. you lack repo access), the failure is logged but enroll succeeds and items from the working sources still install.
- **Branding.** Your org may surface a welcome line on enroll and a display name + footer in `aec doctor`.

## Still deferred to later phases

| Feature | Phase |
|---|---|
| Org-to-org inheritance / delegation | 5+ |
| Per-user overrides inside one config | 5+ |
| MDM auto key-rotation | 5+ |
| Central org registry | 5+ |

If your org config uses one of these, AEC will reject it at enrollment with a clear error.

## See also

- [Authoring org configs](../orgs/authoring-org-configs.md) — for the IT/admin writing the config.
- [Minimal example](../orgs/examples/minimal-phase1.yaml) — copy-and-adapt starting point.
