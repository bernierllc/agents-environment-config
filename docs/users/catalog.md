# Installing catalog items

Install a single skill, rule, or agent from the AEC catalog into the **current tracked repo** (default) or **globally** with `-g`:

```bash
aec install skill my-skill          # local: repo/.claude/skills/ or .agent-rules/
aec install skill my-skill -g       # global: ~/.claude/skills/ etc.
aec install skill my-skill --yes    # non-interactive (no prompts)
```

The central manifest (`~/.agents-environment-config/installed-manifest.json`) records every install per repo path and under `global`.

## Multi-repo global migration prompt

If you keep installing the **same** catalog item locally in many repos, AEC can offer to consolidate to one **global** install:

1. AEC counts how many **other** tracked repos already have that item in the manifest (not counting the repo you are in now, and not counting if the item is already global).
2. When that count reaches your threshold (default **3**, meaning the **next** install would be the **4th** distinct repo), before copying files you see a prompt such as: you are about to install this in your **4th** tracked repo; convert to a global install?
3. If you answer **yes**, AEC removes that item from each per-repo install (files and manifest entries), installs it once globally, updates the manifest, and refreshes the dual-write installed files.
4. If you answer **no**, you can optionally choose to **stop offering** for that specific item (`skill:name`, `rule:name`, or `agent:name`). That choice is stored in `preferences.json` and the offer is skipped until you clear it.

**Non-interactive installs** (`--yes` / `-y`) skip this prompt and perform a normal local install.

**Configuration:** See [Catalog install preferences](preferences.md#catalog-install-preferences) for `global_install_multi_repo_threshold` and `skip_global_install_prompt_for`.

## Skill dependencies

Skills can declare that they require other skills to be present. AEC resolves and installs these automatically at install time with your approval.

### Declaring dependencies in `SKILL.md`

```yaml
---
name: my-skill
version: 1.0.0
description: Does something useful
author: Your Name
dependencies:
  skills:
    - name: verification-writer
      min_version: "3.3.0"
      reason: "Reads verification-page docs to understand output format"
---
```

Each entry requires `name`, `min_version` (semver `x.y.z`), and `reason`. AEC only enforces a minimum version — there are no upper-bound constraints.

### Install approval flow

When you install a skill that has unmet dependencies, AEC lists them and asks for approval before writing any files:

```
Installing playwright-test-generator@3.5.0 will also install:

  verification-writer@3.3.0
    Reason: Reads verification-page docs to understand output format

Approve all? [y/n/each]:
```

- `y` — install all deps and the target skill
- `n` — abort; nothing is installed
- `each` — approve or reject each dep individually; rejecting any dep aborts the entire install

Pass `--yes` / `-y` to skip the prompt and install all deps silently.

### Upgrade conflict flow

When you upgrade a skill whose new version raises a `min_version` constraint on an already-installed dep, AEC prompts once per conflicting dep before applying the upgrade:

```
Updating playwright-test-generator to 3.5.0 requires verification-writer >=3.4.0
(currently 3.3.0). Update verification-writer too? [y/n/cancel]:
```

- `y` — upgrade the dep, then upgrade the target skill
- `n` / `cancel` — skip the target skill upgrade (the dep is left unchanged)

### Migration for existing installs

Skills installed before dependency support was added are treated as explicit installs. The manifest records `installedAs: "explicit"` or `installedAs: "dependency"` for each skill. This field is backfilled automatically on first load — no manual action required.

### Debugging

To inspect what would be installed without writing any files, use `--dry-run`:

```bash
aec upgrade --dry-run   # shows dep conflicts and new deps alongside version bumps
```
