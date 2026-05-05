# Org Configurations

If your organization has standardized on AEC, your IT/admin team may give you an **org config** — a single YAML file describing which agents, skills, rules, and MCP servers your org expects you to use, and which preferences should apply when you run `aec install` or `aec configure`.

This page explains how to enroll, inspect, and remove an org config. It covers **Phase 1** functionality only; later phases will add signed configs, hosted refresh, and project-scoped overlays.

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

Enroll a local file:

```bash
aec org enroll /path/to/your-org-config.yaml --allow-unsigned --yes
```

Phase 1 supports **local-path enrollment only**. URL fetching arrives in Phase 2.

After enrollment, AEC stores two files under `~/.aec/orgs/`:

- `<org_id>.yaml` — the validated config (a verbatim copy of the source).
- `<org_id>.state.json` — local state: hash, trust mode, timestamps.

## Why "unsigned" matters

Phase 1 supports only the `unsigned` trust mode. **Unsigned configs have no cryptographic guarantee** that the file you enrolled came from your org and wasn't modified in transit. AEC will:

- Refuse to enroll an unsigned config without explicit consent (`--allow-unsigned` or interactive confirmation via `--yes` / typed `y`).
- Show the trust mode prominently in `aec org status` and `aec doctor` output.

Phase 2 will add signed trust modes (`pinned_key`, `dns_anchor`). Until then, only enroll configs you received through a trusted channel.

## Inspecting

```bash
aec org list                # all enrolled orgs (Phase 1: 0 or 1)
aec org status              # summary including trust mode and last-verified timestamp
aec org show <org_id>       # full validated config as YAML
aec doctor                  # includes an "Org configurations" section
```

## Leaving

```bash
aec org remove <org_id> --yes
```

Removes both the YAML and the state file. Your `~/.agents-environment-config/` workspace is **not** modified — `aec org remove` only un-enrolls; it does not undo any item installs.

## Phase 1 limits

These are explicitly deferred to later phases:

| Feature | Phase |
|---|---|
| Signed configs (`pinned_key`, `dns_anchor`) | 2 |
| `aec org sync` (refresh from URL) | 2 |
| Multiple enrolled orgs at once | 3 |
| Per-project overlays (`projects[]`) | 4 |
| `enrollment_script` execution | 4 |
| Refresh TTL, branding, daemon checks | 5 |

If your org config uses a Phase 2+ feature, AEC will reject it at enrollment with a clear error.

## See also

- [Authoring org configs](../orgs/authoring-org-configs.md) — for the IT/admin writing the config.
- [Minimal example](../orgs/examples/minimal-phase1.yaml) — copy-and-adapt starting point.
