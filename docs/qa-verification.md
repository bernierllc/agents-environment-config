# QA Verification

Manual verification steps for AEC features. Run these checks after changes to the
relevant subsystems before merging.

## Agent Blurb (`aec configure-agent`)

### Install-time prompt
1. In a fresh repo with a `CLAUDE.md`, run `aec install skill foo` (any installable).
2. Verify prompt offers to add agent blurb. Accept.
3. Verify `<repo>/.aec/agent-blurb.json` is created.
4. Verify `CLAUDE.md` contains an `<!-- aec-blurb:start ... -->` block with valid hashes.

### Drift detection (each of the 5 states)
1. **clean** — immediately after install, run `aec configure-agent --check`; exit 0.
2. **not_installed** — delete `.aec/agent-blurb.json` and run `--check`; exit non-zero.
3. **upstream_update** — manually edit the stored `template_hash` in `.aec/agent-blurb.json` to a bogus value; `--check` reports upstream update.
4. **manual_edit** — hand-edit text inside the block in `CLAUDE.md`; `--check` reports manual edit.
5. **conflict** — combine 3 and 4; `--check` reports conflict.

### Refresh idempotency
1. Run `aec configure-agent --refresh` twice.
2. Verify the second run produces no diff in `CLAUDE.md`.

### Remove
1. Run `aec configure-agent --remove --yes`.
2. Verify block is gone from `CLAUDE.md`, surrounding user content preserved.
3. Verify `.aec/agent-blurb.json` is deleted.

### Both-scope install
1. Run `aec configure-agent --scope both --profile balanced --agent-files all --yes`.
2. Verify both `<repo>/.aec/agent-blurb.json` and `~/.aec/agent-blurb.json` exist.

### Decline persistence
1. On first prompt, decline.
2. Run another `aec install` — verify no prompt.
3. Bump AEC major version (e.g., locally edit `aec/__init__.py` `__version__`).
4. Run another `aec install` — verify prompt returns.

## Hook drift reconciliation (`aec hooks verify`)

### Drift detection + repair
1. In a fresh repo, install a hook-bearing skill: `aec install skill <hooked-skill>`.
2. Confirm the hook lands in `<repo>/.claude/settings.json` and a state file exists at `<repo>/.aec/installed-hooks/skill.<key>.json`.
3. Run `aec hooks verify`; exit 0, reports the hook OK.
4. Hand-edit `.claude/settings.json` to remove the hook entry (simulating an out-of-band clobber).
5. Run `aec hooks verify`; non-zero, reports the hook MISSING.
6. Run `aec hooks verify --repair`; the hook is re-wired into `settings.json` from source.
7. Run `aec hooks verify` again; exit 0.

### Doctor drift summary
1. Repeat the clobber from the section above in a tracked repo.
2. Run `aec doctor`; verify it counts the drifted hook and points at `aec hooks verify --repair`.

## Dormant-hook guard (global install of a hook-bearing skill)

1. Run `aec install skill <hooked-skill> --global` interactively.
2. Verify a bold/colored warning states the hooks stay dormant (global installs wire no hooks) and offers to bail.
3. Decline — verify nothing is installed.
4. Re-run with `--global --yes` (non-interactive) — verify it refuses without `--allow-dormant-hooks`.
5. Re-run with `--global --yes --allow-dormant-hooks` — verify it installs.
6. Install a **hookless** skill `--global` — verify no dormant warning appears.

## Scope-aware global uninstall

### Repo installs spared by default
1. Install a skill globally, then install the same skill into two repos (`aec install skill foo` inside each).
2. Run `aec uninstall skill foo --global` interactively.
3. Verify the aggregated prompt lists both repos with options: all / each / show where / only globally (default).
4. Choose **only globally** — verify the global copy is gone but both repo copies (dir + hooks + manifest entry) remain.

### Non-interactive selection
1. With the same setup, run `aec uninstall skill foo --global --yes` — verify default `--repos none`: repo copies spared.
2. Run `aec uninstall skill foo --global --yes --repos all` — verify all repo copies removed.
3. Verify `--repos <path1>,<path2>` removes only the named repos (unknown paths ignored).
