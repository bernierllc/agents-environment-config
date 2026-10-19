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

Enroll a local file, an `https://` URL, or a file in a git repo:

```bash
aec org enroll /path/to/your-org-config.yaml --allow-unsigned --yes
aec org enroll https://my-org.example/aec.yaml        # signed configs need no --allow-unsigned
aec org enroll 'git+https://git.example.com/my-org/aec-catalog.git#main:org/my-org.yaml'
```

Only `https://` URLs are accepted. A git source is `git+<url>#<ref>:<path>`, where `<url>` is `https://…` or `git@host:path`, `<ref>` is a branch or tag, and `<path>` is the config's path inside the repo. AEC clones with your own git credentials (a credential helper or ssh key) and never stores them, so a url with `user:token@` in it is refused and keeps the clone in `~/.aec/orgs/<org_id>.d/repo/`. A signed git config's signature is `<path>.sig` in the same commit.

AEC remembers the source and re-fetches + re-verifies it on `aec update`; configs that set `refresh.ttl_hours` are also re-fetched automatically once the local copy ages out.

To move an enrolled org to a new source (say, from a URL to a git repo) while keeping your conflict resolutions:

```bash
aec org enroll --replace my-org 'git+https://git.example.com/my-org/aec-catalog.git#main:org/my-org.yaml'
```

`--replace` refuses an org that is not enrolled, and a source whose `org_id` is different.

### What `aec update` does with an upstream change

`aec update` never prompts. For each url- or git-sourced org:

| Upstream | What happens |
|---|---|
| Same content as what you enrolled | Nothing. Any stale pending review is cleared. |
| Trust anchor changed (trust mode, pinned key, key URL, or DNS domain) | Recorded as a pending **trust change**. Nothing is applied. |
| Can't fetch, parse, or verify (bad signature, wrong `org_id`) | Recorded as **verify failed**. Your current config is untouched. |
| Signed, verified, and `install.mode: managed` | Applied. |
| Anything else (unsigned, or signed but guided/unset) | Staged for **review**: AEC prints what changed and applies nothing. |

If anything is pending, `aec update` finishes its other steps and then exits with code **14**, and `aec doctor` fails until it's cleared:

- **Review:** `aec org apply` applies the staged change (if you decline at the prompt or use `--dry-run`, it stays staged). `aec org apply --decline <commit>` discards it (at least 7 characters of the commit; for a URL source, the config hash shown).
- **Trust change:** only `aec org enroll --replace <org_id> <source>` at an interactive prompt clears it. `--yes` is refused, and so are `--decline` and `aec org trust-rotate`.
- **Verify failed:** fix the source, then run `aec update` again.

After enrollment, AEC stores two files under `~/.aec/orgs/`:

- `<org_id>.yaml` — the validated config (a verbatim copy of the source).
- `<org_id>.state.json` — local state: hash, trust mode, source, timestamps, and any pending item.
- `<org_id>.d/` — the git clone (git sources) and a change staged for review.

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
aec org status              # trust mode, fingerprint, source, last applied (or "never applied"), pending
aec org show <org_id>       # full validated config as YAML
aec org resolve --list      # any unresolved cross-org conflicts
aec doctor                  # "Org configurations" + "Org conflicts" sections
```

## Leaving

```bash
aec org remove <org_id> --yes
```

Removes the YAML, the state file, and the `<org_id>.d/` directory. Your `~/.agents-environment-config/` workspace is **not** modified — `aec org remove` only un-enrolls; it does not undo any item installs.

## Still deferred to later phases

| Feature | Phase |
|---|---|
| Per-project overlays (`projects[]`) | 4 |
| `enrollment_script` execution | 4 |
| `branding`, `aec daemon-check` periodic refresh | 5 |

If your org config uses one of these, AEC will reject it at enrollment with a clear error.

## See also

- [Authoring org configs](../orgs/authoring-org-configs.md) — for the IT/admin writing the config.
- [Minimal example](../orgs/examples/minimal-phase1.yaml) — copy-and-adapt starting point.
