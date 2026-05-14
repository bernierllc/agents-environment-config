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
