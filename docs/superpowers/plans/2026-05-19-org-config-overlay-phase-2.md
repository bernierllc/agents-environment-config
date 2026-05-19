# Org Config Overlay — Phase 2 Implementation Plan (skeleton)

> **For agentic workers:** This is a Later-tier scope skeleton — NOT a build-ready
> plan. Open questions below must be resolved with the user before tasks are
> written. Use `superpowers:writing-plans` to expand once scope is locked.

**Status:** Scope draft. Phase 1 shipped via PR #47 + #48 (test coverage). Phase 2
covers the trust, signing, multi-org conflict, and propagation work that Phase 1
intentionally deferred.

**Parent design specs:**
- `docs/superpowers/specs/2026-05-04-org-config-overlay-design.md` (canonical scope)
- `docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md` (preferences + prompts allow-lists)

**Phase 1 reference plan (shipped, soon to be archived):**
- `docs/superpowers/plans/2026-05-04-org-config-overlay-phase-1.md`

---

## Phase 2 in scope

Phase 1 delivered: schema parse + validate, single-org enrollment, basic
policy overlay (`AEC defaults → org → user`), unsigned configs with loud
warnings, local-path enrollment, `aec org status/remove`, allow-list enforcement
for `install.preferences` and `install.prompts`.

Phase 2 adds the four capabilities Phase 1 explicitly deferred:

1. **Signing & trust verification**
   - `trust.mode: dns_anchor` — fetch `.well-known/aec-pubkey` over TLS, verify
     ed25519 detached signature. Gated behind `pip install aec[org-configs]`.
   - `trust.mode: pinned_key` — TOFU fingerprint with explicit acknowledgment,
     stored in `~/.aec/orgs/<id>.state.json`.
   - `aec org trust-rotate <org-id>` command for key rotation acknowledgment.
   - `aec doctor` surfaces unsigned/unverified configs in red.

2. **URL-fetch delivery + refresh**
   - `aec install --org-config <https-url>` and `aec update` re-fetches.
   - State file stores `source_of_record: url|mdm|local` and source URL.
   - Optional per-org `refresh.ttl_hours` for time-based auto-refetch.

3. **Multi-org enrollment + conflict resolution**
   - Concurrent enrollments at `~/.aec/orgs/*.yaml`.
   - Conflict scan after each org's policy loads (types: stance, version,
     source-replacement, preference, install-mode, project-rule, P6 violation).
   - `~/.aec/conflict-resolutions.json` with input-hash invalidation.
   - `aec org resolve <conflict-id>` interactive UX.
   - Halt only conflicting items; everything unambiguous still applies (P7).

4. **Hash-based change propagation**
   - Re-hash on every `aec` invocation; on hash change re-verify trust then
     present unified policy diff. Managed mode applies silently; guided mode
     prompts.
   - File lock + atomic rename for concurrent `aec` processes.

## Out of scope for Phase 2

Locked from the design spec; revisit in v1.1+:

- Per-user overrides inside a single org config.
- Time-bounded rules (`required_after`, `expires_at`).
- Conditional rules beyond directory/remote matching.
- Executable shell hooks in `enrollment_script`.
- Org-to-org inheritance/delegation.
- Telemetry back to the org.
- A central registry of well-known orgs.

## Open questions (must resolve before tasks are written)

1. **Crypto dependency footprint.** Confirm `pynacl` (libsodium) is the right
   library vs. `cryptography`. Spec leans pynacl for misuse-resistance + smaller
   install. Verify wheels exist for all platforms Matt distributes to (macOS
   arm64, macOS x86_64, Linux x86_64). Decision needed before Task 1.
2. **`aec[org-configs]` install messaging.** When a user has an unsigned config
   working today and Phase 2 introduces signed-only as the default for new orgs,
   how do we communicate the install upgrade? Add a doctor warning? Auto-detect
   missing extras and prompt?
3. **Conflict UX scope for v2.0.** Spec describes interactive resolve UI but
   doesn't pin down `aec org resolve` ergonomics (TUI? plain stdin? generate a
   `.json` file the user edits?). Need a UX sketch before Task 4.
4. **Managed-mode silent apply policy.** When a managed-mode config's hash
   changes mid-week, do we apply at next interactive `aec` call only, or also
   on `aec doctor` / hook-triggered invocations? Affects timing of trust
   re-verification.
5. **Pubkey rotation grace period.** Spec says rotation requires explicit
   `aec org trust-rotate`. Should there be a max age on a "pending rotation"
   state before AEC halts all org-config operations? Default suggestion: 30 days.
6. **Test-org fixture.** Phase 2 needs a test org config (with real signature)
   for integration tests. Stand up a `tests/fixtures/orgs/test-org/` with a
   throwaway keypair, or rely on mocks for the verifier? Affects how trusted the
   verification tests will be.

## Suggested phasing within Phase 2

Once open questions resolve, break the work as four sub-phases that each ship
independently and can move from Later → Next one at a time:

- **2a — Signing core.** ed25519 verify, pubkey cache, `trust: pinned_key` end-to-end.
  Pinned-key first because it doesn't require the DNS pubkey-discovery code path.
- **2b — DNS anchor + rotation.** `.well-known/aec-pubkey` fetch + `aec org trust-rotate`.
- **2c — URL fetch + refresh.** `--org-config <url>`, refresh TTL, MDM-vs-URL state tracking.
- **2d — Multi-org conflicts.** Conflict detection, persistence, `aec org resolve`,
  doctor surfacing. Largest sub-phase — likely 60% of Phase 2 effort.

## Success criteria (Phase 2 done when…)

- A signed org config (pinned_key or dns_anchor) can be enrolled via URL and via MDM
  drop, with identical behavior post-enrollment.
- Two simultaneously enrolled orgs with conflicting stances halt only the conflicting
  items; everything else applies; user can resolve via CLI and the resolution survives
  unchanged org config hashes but invalidates when either input hash changes.
- `aec doctor` reports trust state of every enrolled org and flags any unsigned,
  rotated, or unverified configs.
- `pip install aec` (without extras) still works for users with no org config; signed
  configs error with a clear "install aec[org-configs]" message.
- Cross-process safety verified via concurrent `aec` invocation test.

## References

- Spec sections to lean on: "Trust & Verification", "Local Storage and Refresh",
  "Conflict Resolution", "Crypto implementation".
- Phase 1 plan for shape/conventions of the implementation tasks.
