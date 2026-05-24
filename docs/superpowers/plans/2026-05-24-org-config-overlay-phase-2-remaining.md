> Status: build-ready — expands the Phase 2 skeleton (`2026-05-19-org-config-overlay-phase-2.md`) into task-by-task work covering everything still missing after Phase 2a shipped. Supersedes the skeleton's "tasks not yet written" note.

# Org Config Overlay — Phase 2 Remaining (2b–2e) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: implement task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax. Test first → watch it fail → implement the minimum → watch it pass → run the full suite → commit. Do not batch tasks.

**Goal:** Finish the org-config overlay's trust, delivery, multi-org, and propagation work that Phase 2a deferred — so a signed org config can be delivered by URL or DNS anchor, multiple orgs can coexist with deterministic conflict handling, and config changes propagate safely on every `aec` run.

**What already shipped (do not rebuild):**
- Phase 1: schema, parser, validator, hashing, state IO, single-org discovery, unsigned trust, `aec org enroll/list/status/show/remove`, allow-lists, doctor "Org configurations" section.
- Phase 2a (`a5f7cbf`): `pinned_key` ed25519 verification (`aec/lib/org_config/crypto.py`, `trust.py`), inline-pubkey enrollment, `aec org trust-rotate` for pinned keys, doctor trust surfacing.

**Parent specs:**
- `docs/superpowers/specs/2026-05-04-org-config-overlay-design.md` (canonical scope: "Trust & Verification", "Local Storage and Refresh", "Conflict Resolution", "Crypto implementation")
- `docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md`
- Skeleton: `docs/superpowers/plans/2026-05-19-org-config-overlay-phase-2.md`

**Tech stack:** Python 3.9+, Typer, stdlib `hashlib`/`json`/`pathlib`/`urllib`/`fcntl`, PyYAML + `pynacl==1.5.0` (both gated behind `pip install aec[org-configs]`). No new runtime deps for users without org configs.

---

## Decisions resolved (locked 2026-05-24)

These were the skeleton's open questions. Resolved before task-writing:

| # | Question | Decision |
|---|----------|----------|
| 1 | Crypto library | **Resolved in 2a** — `pynacl==1.5.0`, pinned per supply-chain policy in `pyproject.toml`. |
| 2 | `aec[org-configs]` install messaging | Missing-extra path raises `OrgConfigCryptoUnavailable` with an actionable `pip install aec[org-configs]` message (exists for 2a); extend it to the DNS/URL fetch paths, and add a doctor warning when a signed config is enrolled but the extra is absent. |
| 3 | Conflict resolution UX | **Plain stdin prompts.** `aec org resolve <conflict-id>` walks each conflict via numbered stdin choices using the existing `aec.lib.prompts` seam. No TUI, no new deps. |
| 4 | Managed-mode silent-apply timing | **Apply on any `aec` invocation** (including `aec doctor` and git-hook-triggered runs). Re-verify trust before applying. Guided mode prompts; managed mode applies silently. |
| 5 | Pubkey rotation grace | **User-driven rotation, 30-day grace with countdown.** On a detected key change: warn immediately on every invocation, showing days remaining. After 30 days, **lock out** org-config operations until `aec org trust-rotate <org-id>`. (MDM/automated rotation is out of scope — this covers the case where the human operator must run the rotate command.) |
| 6 | Test-org fixture | **Real ephemeral keypairs**, generated per-test via a pytest fixture (follows the 2a `test_crypto.py` precedent). No committed private keys; no mocked verifier for the happy path. |

---

## Scope

**In scope (everything still missing in Phase 2):**
- **2b** — DNS-anchored trust (`trust.mode: dns_anchor`) + the key-rotation grace/countdown/lockout state machine.
- **2c** — URL-fetch delivery (`aec org enroll <https-url>`, `aec install --org-config <url>`) + `refresh.ttl_hours` re-fetch + `source_of_record` tracking.
- **2d** — Multi-org enrollment + conflict detection + `conflict-resolutions.json` persistence + `aec org resolve` + halt-only-conflicting (P7).
- **2e** — Hash-based change propagation (re-hash on every invocation → re-verify → unified diff → apply) + cross-process safety.

**Out of scope (locked from the design spec; revisit v1.1+):** per-user overrides inside one org config; time-bounded rules (`required_after`/`expires_at`); conditional rules beyond directory/remote matching; executable `enrollment_script` hooks; org-to-org inheritance; telemetry; central org registry; MDM-driven automatic key rotation. The full **overlay *applier*** (pre-answering prompts / writing preferences during install) is tracked separately and only the seams it needs are touched here.

---

## File structure

### New files
```
aec/lib/org_config/
├── fetch.py            # https GET helpers (well-known pubkey, remote config) — injectable, TLS-verified
├── rotation.py         # key-rotation grace state machine: detect → warn/countdown → lockout
├── conflicts.py        # conflict detection across multiple EnrolledOrg policies (typed Conflict objects)
├── resolutions.py      # read/write conflict-resolutions.json + input-hash invalidation
└── propagation.py      # re-hash-on-invocation, change detection, unified policy diff, apply gate

tests/lib/org_config/
├── test_fetch.py
├── test_rotation.py
├── test_conflicts.py
├── test_resolutions.py
├── test_propagation.py
├── test_trust_dns_anchor.py
└── fixtures/
    └── orgs/                       # multi-org + signed fixtures (ephemeral keys via conftest)
        ├── conftest.py             # keypair + signed-config fixture factory
        ├── valid-multi-a.yaml
        ├── valid-multi-b-conflicting.yaml
        └── valid-dns-anchor.yaml

tests/commands/
├── test_org_resolve.py            # `aec org resolve` stdin UX
├── test_org_enroll_url.py         # url enroll + signed
└── test_org_trust_rotate_dns.py
```

### Modified files
- `aec/lib/org_config/trust.py` — implement `dns_anchor` branch (currently raises "arrives in phase 2b"); accept a fetched pubkey + signature; return fingerprint for TOFU pinning.
- `aec/lib/org_config/schema.py` — add `refresh_ttl_hours: Optional[int]` to `OrgConfig`; (trust pubkey/url/dns fields already present).
- `aec/lib/org_config/validator.py` — accept `dns_anchor` (require `trust.dns_domain`); accept `trust.pubkey_url`; accept `refresh.ttl_hours`; keep rejecting unknown trust modes.
- `aec/lib/org_config/discovery.py` — remove the single-org rejection; return all enrolled orgs sorted deterministically; surface per-org load errors without failing the whole set.
- `aec/lib/org_config/state.py` — extend `OrgState` consumers for rotation-pending payload shape and `source_of_record` values (`url`/`mdm`/`local`); no schema break (fields already exist).
- `aec/lib/org_config/__init__.py` — export new public surfaces (`detect_conflicts`, `Conflict`, `fetch_remote_config`, rotation/propagation entry points).
- `aec/commands/org.py` — `enroll` URL support (replace the `echo("url fetch added in phase 2")` stub at `org.py:118`); `dns_anchor` enroll (replace the "not yet implemented" branch at `org.py:165`); new `resolve` command; extend `trust-rotate` to dns_anchor.
- `aec/commands/install_cmd.py` — `--org-config <https-url>` flag → enroll + apply path.
- `aec/commands/update.py` — re-fetch URL/MDM-sourced orgs whose `refresh.ttl_hours` elapsed.
- `aec/commands/doctor.py` — surface: pending rotation + countdown, unsigned/unverified in red, missing-`org-configs`-extra warning, unresolved conflicts.
- `aec/cli.py` — ensure propagation gate runs early on every invocation (the 2e hook).
- `pyproject.toml` — no change expected (`org-configs` extra already pins pynacl + PyYAML).
- `docs/users/org-configs.md`, `docs/orgs/authoring-org-configs.md` — document dns_anchor, URL delivery, refresh TTL, multi-org + resolve, rotation lockout.

---

## Conventions (same as Phase 1)

- **Tests:** `pytest` from repo root. `tmp_path` for anything touching `~/.aec/`; inject `home_dir`/fetcher callables rather than reading `$HOME` or hitting the network.
- **No real network in tests.** All fetchers are injectable; tests pass a fake returning canned bytes. One opt-in, `-m network` integration test may exist but must be skipped by default.
- **Commits:** lowercase conventional commits (`feat(org-config): …`, `test(org-config): …`, `docs(org-config): …`). Required by commitlint.
- **Run before every commit that changes lib code:**
  ```bash
  pytest tests/lib/org_config/ tests/commands/ -v
  pytest -q   # full suite; coverage gate --cov-fail-under=65 must stay green
  ```
- All datetimes are ISO-8601 UTC strings on disk.

---

# Sub-phase 2b — DNS anchor + key rotation

## Task 2b.1: `fetch.py` — TLS-verified HTTPS GET (injectable)

**Files:** create `aec/lib/org_config/fetch.py`, `tests/lib/org_config/test_fetch.py`.

- [ ] **Step 1 — failing tests.** Cover: (a) `fetch_bytes` rejects non-`https://` URLs with `OrgConfigFetchError`; (b) a `max_bytes` cap raises on oversized bodies; (c) the function is a thin wrapper that delegates to an injected opener so tests never touch the network.
  ```python
  import pytest
  from aec.lib.org_config.fetch import fetch_bytes, OrgConfigFetchError

  def test_rejects_non_https():
      with pytest.raises(OrgConfigFetchError, match="https"):
          fetch_bytes("http://example.com/x", opener=lambda url, timeout: b"x")

  def test_passes_through_https_body():
      got = fetch_bytes("https://example.com/x", opener=lambda url, timeout: b"hello")
      assert got == b"hello"

  def test_enforces_max_bytes():
      big = b"x" * 1000
      with pytest.raises(OrgConfigFetchError, match="too large"):
          fetch_bytes("https://e/x", opener=lambda url, timeout: big, max_bytes=10)
  ```
- [ ] **Step 2 — implement.** `fetch_bytes(url, *, opener=None, timeout=10, max_bytes=1_000_000)`. Default `opener` uses `urllib.request.urlopen` with a `ssl.create_default_context()` (TLS verification ON; never disable). Reject non-https schemes before opening. Add `OrgConfigFetchError(OrgConfigError)` to `errors.py`.
- [ ] **Step 3 — run + commit.** `feat(org-config): add TLS-verified injectable https fetcher`.

## Task 2b.2: wire `dns_anchor` into `verify_trust`

**Files:** modify `trust.py`; create `tests/lib/org_config/test_trust_dns_anchor.py`; fixtures via `tests/lib/org_config/fixtures/orgs/conftest.py` (Task 2d.0 may land this first — if absent, create the keypair fixture here).

- [ ] **Step 1 — failing tests.** Using an ephemeral ed25519 keypair: (a) a config signed by the key, with the matching pubkey returned from a fake `.well-known/aec-pubkey` fetch, verifies and returns the fingerprint; (b) a tampered config fails with `OrgConfigTrustError("signature verification failed")`; (c) a pubkey whose fingerprint differs from the pinned one raises the "run `aec org trust-rotate`" error; (d) when `pynacl` is unavailable, raises `OrgConfigCryptoUnavailable` with the install hint.
- [ ] **Step 2 — implement.** Replace the `dns_anchor` branch (`trust.py:58-61`). Add params `pubkey_fetcher: Optional[Callable]` and `dns_domain`/`signature` plumbing. Behavior: fetch pubkey from `https://<dns_domain>/.well-known/aec-pubkey` via the injected fetcher, then reuse the existing detached-signature verification + fingerprint logic (factor the shared body out of `_verify_pinned_key`). TOFU-pin the fingerprint exactly like pinned_key. Keep `verify_trust` keyword-only and backward compatible (new params optional).
- [ ] **Step 3 — run + commit.** `feat(org-config): verify dns_anchor trust via well-known pubkey`.

## Task 2b.3: `rotation.py` — grace state machine (warn → countdown → lockout)

**Files:** create `aec/lib/org_config/rotation.py`, `tests/lib/org_config/test_rotation.py`.

Implements decision #5. The `key_rotation_pending` payload on `OrgState` records `{ "detected_at": iso, "new_fingerprint": fp, "old_fingerprint": fp }`. Grace window = 30 days (module constant `ROTATION_GRACE_DAYS = 30`).

- [ ] **Step 1 — failing tests.**
  ```python
  from aec.lib.org_config.rotation import rotation_status, RotationStatus, ROTATION_GRACE_DAYS

  def test_no_pending_returns_clear():
      assert rotation_status(pending=None, now="2026-05-24T00:00:00Z").state == "clear"

  def test_pending_within_grace_warns_with_countdown():
      s = rotation_status(
          pending={"detected_at": "2026-05-01T00:00:00Z", "new_fingerprint": "b", "old_fingerprint": "a"},
          now="2026-05-24T00:00:00Z",
      )
      assert s.state == "warn"
      assert s.days_remaining == 7          # 30 - 23

  def test_pending_past_grace_locks_out():
      s = rotation_status(
          pending={"detected_at": "2026-04-01T00:00:00Z", "new_fingerprint": "b", "old_fingerprint": "a"},
          now="2026-05-24T00:00:00Z",
      )
      assert s.state == "locked"
      assert s.days_remaining == 0
  ```
- [ ] **Step 2 — implement.** `RotationStatus(state: Literal["clear","warn","locked"], days_remaining: int, message: str)`. `message` for `warn` reads e.g. *"Org 'acme' signing key changed on 2026-05-01. Run `aec org trust-rotate acme` within 7 days or org-config operations will be locked out."*; for `locked` it states the lockout is active. Pure function over `(pending, now)` so it's trivially testable.
- [ ] **Step 3 — run + commit.** `feat(org-config): add key-rotation grace/countdown/lockout state machine`.

## Task 2b.4: enforce rotation status + extend `trust-rotate`/doctor for dns_anchor

**Files:** modify `aec/commands/org.py`, `aec/commands/doctor.py`; tests `tests/commands/test_org_trust_rotate_dns.py`, extend `tests/commands/test_doctor_cmd.py`.

- [ ] **Step 1 — failing tests.** (a) When a dns_anchor org's fetched key changes, the next `aec org status`/any org op writes `key_rotation_pending` and prints the countdown warning; (b) after the simulated grace expiry, org ops exit non-zero with the lockout message until `trust-rotate`; (c) `aec org trust-rotate <id>` for a dns_anchor org re-fetches the pubkey, verifies, clears `key_rotation_pending`, and re-pins; (d) `aec doctor` shows `pending rotation — N days remaining` in yellow and `LOCKED` in red.
- [ ] **Step 2 — implement.** Generalize `trust_rotate_cmd` (`org.py:347`) so it handles both `pinned_key` (inline) and `dns_anchor` (fetched) modes. Insert a `rotation_status(...)` gate at the top of org-config-affecting commands; on `locked`, raise `typer.Exit(EXIT_TRUST)`. Add the rotation/countdown line to doctor's `_check_org_configurations`.
- [ ] **Step 3 — run full suite + commit.** `feat(org-config): enforce rotation lockout and rotate dns_anchor keys`.

---

# Sub-phase 2c — URL fetch + refresh

## Task 2c.1: schema/validator support for `pubkey_url` and `refresh.ttl_hours`

**Files:** modify `schema.py`, `validator.py`; extend `tests/lib/org_config/test_validator.py`, `test_schema.py`.

- [ ] **Step 1 — failing tests.** (a) `OrgConfig` carries `refresh_ttl_hours: Optional[int]` (default None); (b) validator accepts `refresh: { ttl_hours: 24 }` and rejects `ttl_hours <= 0` with a `field_path="refresh.ttl_hours"` error; (c) validator accepts `trust.pubkey_url` (https) for pinned_key and rejects a non-https `pubkey_url`.
- [ ] **Step 2 — implement.** Add the field + parsing; reuse the https check from `fetch.py` for url-shaped fields. Contract change to `OrgConfig` — sweep constructors in tests/discovery.
- [ ] **Step 3 — run + commit.** `feat(org-config): validate pubkey_url and refresh.ttl_hours`.

## Task 2c.2: remote config fetch + `aec org enroll <https-url>` + `aec install --org-config <url>`

**Files:** modify `aec/commands/org.py` (replace stub at `org.py:118`), `aec/commands/install_cmd.py`; create `tests/commands/test_org_enroll_url.py`; reuse `fetch.py`.

- [ ] **Step 1 — failing tests.** (a) `aec org enroll https://…/acme.yaml` (fetcher injected) downloads, parses, validates, verifies trust, writes `~/.aec/orgs/acme.yaml` + state with `source_of_record="url"` and the source URL recorded; (b) a signed remote config with a `.sig`/`signature_url` verifies; (c) an unsigned remote config without `--allow-unsigned` refuses; (d) `aec install --org-config <url>` performs enroll-then-apply; (e) a non-https URL is rejected.
- [ ] **Step 2 — implement.** Replace the `_looks_like_url` stub branch with a real path that pipes `fetch_bytes` → existing parse/validate/verify/persist flow. Persist source URL in state (extend the state payload; field already present as `source_of_record`, store the URL alongside under `pubkey_source`/a `source_url` key — confirm shape in `state.py`). Make the fetcher injectable through the command for tests (module-level default, override via a hidden param or env in tests).
- [ ] **Step 3 — run full suite + commit.** `feat(org-config): enroll org configs from https urls`.

## Task 2c.3: TTL-based refresh on `aec update`

**Files:** modify `aec/commands/update.py`; create helper in `propagation.py` or `fetch.py`; tests extend `tests/test_update_cmd.py`.

- [ ] **Step 1 — failing tests.** (a) A url-sourced org whose `last_verified_at` is older than `refresh_ttl_hours` is re-fetched on `aec update`; (b) one within TTL is not re-fetched; (c) a re-fetch that returns a changed config triggers the 2e propagation path (re-verify + diff); (d) local-sourced orgs are never auto-refetched.
- [ ] **Step 2 — implement.** Add `due_for_refresh(state, ttl_hours, now) -> bool`. Wire into `update.py` for orgs with `source_of_record in {"url","mdm"}`.
- [ ] **Step 3 — run + commit.** `feat(org-config): refresh url-sourced org configs on ttl expiry`.

---

# Sub-phase 2d — Multi-org enrollment + conflict resolution

## Task 2d.0: signed/multi-org test fixtures (ephemeral keys)

**Files:** create `tests/lib/org_config/fixtures/orgs/conftest.py` + yaml fixtures.

- [ ] **Step 1 — implement fixture factory.** A pytest fixture that generates an ed25519 keypair, signs a given config body, and writes `<config>.yaml` + `<config>.sig` into `tmp_path`. Provide two non-conflicting orgs and one pair that conflicts (same item, opposing stances `required` vs `blocked`; a `pinned` version mismatch; a source `replace` vs `keep` clash). Commit no private keys.
- [ ] **Step 2 — commit.** `test(org-config): add ephemeral-key signed + multi-org fixtures`.

## Task 2d.1: enable multi-org discovery

**Files:** modify `discovery.py`; extend `tests/lib/org_config/test_discovery.py`.

- [ ] **Step 1 — failing tests.** (a) Two valid configs load into two `EnrolledOrg`s sorted by `org_id`; (b) one invalid config does not sink the whole set — it's returned as a load error the caller can surface (introduce `discover_enrolled_orgs(paths, *, strict=False)` returning `(orgs, errors)` or keep raising in `strict=True`); (c) zero configs still returns `[]`.
- [ ] **Step 2 — implement.** Remove the `len>1` rejection (`discovery.py:37-42`). Deterministic ordering. Decide the error-tolerance API and keep doctor/status callers working (they currently expect a list — preserve a list-returning convenience).
- [ ] **Step 3 — run full suite + commit** (this changes a Phase-1 contract — sweep `org.py` + `doctor.py` callers). `feat(org-config): support multiple concurrently enrolled orgs`.

## Task 2d.2: `conflicts.py` — typed conflict detection

**Files:** create `aec/lib/org_config/conflicts.py`, `tests/lib/org_config/test_conflicts.py`.

Conflict types (from spec): `stance`, `version`, `source_replacement`, `preference`, `install_mode`, `project_rule`, `p6_violation`.

- [ ] **Step 1 — failing tests.** Build two `OrgConfig`s and assert `detect_conflicts([a, b])` returns `Conflict` objects with: stable `conflict_id` (hash of sorted org_ids + type + subject), `type`, `subject` (e.g. `skills/foo`), and the competing `(org_id, value)` pairs. Cover each type with at least one case; assert non-conflicting overlaps produce zero conflicts (P7: only genuine clashes).
- [ ] **Step 2 — implement.** Pure function over the loaded configs; no IO. `Conflict` is a frozen dataclass. `conflict_id` must be deterministic and stable across runs so resolutions can key off it.
- [ ] **Step 3 — run + commit.** `feat(org-config): detect cross-org policy conflicts`.

## Task 2d.3: `resolutions.py` — persistence + input-hash invalidation

**Files:** create `aec/lib/org_config/resolutions.py`, `tests/lib/org_config/test_resolutions.py`. Uses `paths.conflict_resolutions` + `paths.conflict_resolutions_history`.

- [ ] **Step 1 — failing tests.** (a) A saved resolution round-trips; (b) a resolution stores the `input_hash` (hash of the two contributing config hashes); (c) when either contributing org config changes (hash differs), the stored resolution is treated as **stale/invalid** and not auto-applied; (d) superseded resolutions append to the history file; (e) writes are atomic + flock-guarded (reuse the `state.py` pattern).
- [ ] **Step 2 — implement.** `load_resolutions(paths)`, `save_resolution(paths, conflict_id, choice, input_hash)`, `is_valid(resolution, current_input_hash)`.
- [ ] **Step 3 — run + commit.** `feat(org-config): persist conflict resolutions with input-hash invalidation`.

## Task 2d.4: `aec org resolve` — stdin UX + halt-only-conflicting (P7)

**Files:** modify `aec/commands/org.py` (new `resolve` command); create `tests/commands/test_org_resolve.py`. Uses the `aec.lib.prompts` seam.

- [ ] **Step 1 — failing tests** (drive stdin via `CliRunner(input=...)`). (a) `aec org resolve` lists open conflicts with numeric ids; (b) `aec org resolve <id>` prompts to pick the winning org/value and persists it; (c) `--list` prints conflicts non-interactively and exits 0; (d) after resolving, the conflict no longer appears; (e) re-running with a changed contributing config re-opens the (now stale) conflict.
- [ ] **Step 2 — implement.** Numbered stdin prompts only (decision #3). On resolve, write via `resolutions.py`. Enforce **P7**: unaffected items always apply; only the specific conflicting subjects are held pending resolution — surface this as a one-line summary ("3 items applied, 1 held pending `aec org resolve`").
- [ ] **Step 3 — run full suite + commit.** `feat(org-config): add aec org resolve for multi-org conflicts`.

## Task 2d.5: doctor surfacing of unresolved conflicts

**Files:** modify `aec/commands/doctor.py`; extend `tests/test_doctor_cmd.py`.

- [ ] **Step 1 — failing test.** With two conflicting orgs enrolled and no resolution, `aec doctor` prints an "Org conflicts" subsection in red listing each open conflict + the `aec org resolve` hint; with resolutions present, it prints clear.
- [ ] **Step 2 — implement + run full suite + commit.** `feat(org-config): surface unresolved org conflicts in doctor`.

---

# Sub-phase 2e — Hash-based change propagation + concurrency

## Task 2e.1: change detection on every invocation

**Files:** create `aec/lib/org_config/propagation.py`, `tests/lib/org_config/test_propagation.py`.

- [ ] **Step 1 — failing tests.** (a) `detect_changes(paths, now)` returns the set of orgs whose on-disk `content_hash` differs from `state.config_hash`; (b) unchanged orgs report nothing; (c) a missing state (newly dropped MDM file) is reported as "new".
- [ ] **Step 2 — implement.** Re-hash each enrolled config, compare to persisted state. Pure-ish (inject `now`).
- [ ] **Step 3 — run + commit.** `feat(org-config): detect org-config hash changes on invocation`.

## Task 2e.2: unified policy diff

**Files:** extend `propagation.py` + tests.

- [ ] **Step 1 — failing tests.** Given an old vs new `OrgConfig`, `policy_diff(old, new)` returns added/removed/changed items, source changes, preference changes, and trust-mode changes in a render-ready structure.
- [ ] **Step 2 — implement + commit.** `feat(org-config): compute unified org-config policy diff`.

## Task 2e.3: apply gate — re-verify trust, managed vs guided, cross-process safe

**Files:** extend `propagation.py`; wire into `aec/cli.py` so it runs early on every command; tests `test_propagation.py` + a concurrency test.

Implements decision #4 (apply on any invocation, including doctor/hooks).

- [ ] **Step 1 — failing tests.** (a) On a changed config, the gate **re-verifies trust** before applying; a trust failure blocks apply and surfaces the error (does not silently apply); (b) **managed mode** applies silently and updates state (`config_hash`, `last_applied_at`); (c) **guided mode** presents the diff and prompts (drive via injected prompt) — declining leaves state unchanged; (d) rotation `locked` status (Task 2b.3) blocks apply; (e) **concurrency:** two processes invoking the gate simultaneously do not corrupt state — second waits on the flock and sees a consistent result (reuse `state.py` flock + atomic rename; add a test that spawns two threads/processes hitting `write_state` for the same org).
- [ ] **Step 2 — implement.** A single `run_propagation_gate(paths, *, mode, now, prompt=…, fetcher=…)` called from `cli.py` before command dispatch. Order: detect changes → for each, re-verify trust (+ rotation gate) → diff → managed:apply / guided:prompt → persist state under flock. Must be a no-op (fast, zero IO beyond a stat/hash) when nothing changed and no orgs are enrolled, so it never slows the common case.
- [ ] **Step 3 — run full suite + commit.** `feat(org-config): propagate verified org-config changes on every invocation`.

---

# Cross-cutting tasks

## Task X1: missing-extra messaging
- [ ] Ensure DNS/URL/verify paths raise `OrgConfigCryptoUnavailable` with `pip install aec[org-configs]` when pynacl/PyYAML absent; add a doctor warning when a signed/url org is enrolled but the extra is missing. Tests simulate the missing import. Commit: `feat(org-config): guide users to aec[org-configs] when crypto extra is missing`.

## Task X2: public surface + docs
- [ ] Export new entry points from `aec/lib/org_config/__init__.py`; smoke-test imports.
- [ ] Update `docs/users/org-configs.md` + `docs/orgs/authoring-org-configs.md`: dns_anchor authoring (`.well-known/aec-pubkey`), URL delivery, `refresh.ttl_hours`, multi-org + `aec org resolve`, rotation lockout/countdown. Add a `docs/orgs/examples/` dns-anchor + multi-org example.
- [ ] Commit: `docs(org-config): document phase-2 trust, delivery, multi-org, and refresh`.

## Task X3: archive the skeleton
- [ ] Update `2026-05-19-org-config-overlay-phase-2.md` status header to "expanded → 2026-05-24-org-config-overlay-phase-2-remaining.md"; once 2b–2e ship, move both Phase-2 docs to `docs/superpowers/plans/archive/`. Commit: `docs(plans): point phase-2 skeleton at the build-ready plan`.

---

## Definition of done (Phase 2 complete when…)

- A signed org config (`pinned_key` **or** `dns_anchor`) enrolls identically via local path, `https` URL, and MDM file drop; tampered configs are rejected.
- Two simultaneously enrolled orgs with conflicting stances **halt only the conflicting items** (P7); everything unambiguous still applies; `aec org resolve` persists a choice that survives unchanged config hashes but invalidates when either input hash changes.
- A user-driven key rotation warns immediately with a day countdown and **locks out** org-config operations after 30 days until `aec org trust-rotate`.
- `aec doctor` reports every org's trust state, pending rotation + countdown, missing-extra warnings, and unresolved conflicts.
- Config changes re-verify trust and propagate on **any** `aec` invocation (managed: silent; guided: prompted); concurrent invocations are safe (flock + atomic rename), proven by a concurrency test.
- `pip install aec` (no extras) still works for users with no org config; signed/url configs error with a clear `aec[org-configs]` install message.
- Full suite green with coverage ≥ 65%.

## Suggested execution order

`2b.1 → 2b.2 → 2b.3 → 2b.4` (trust foundation) → `2c.1 → 2c.2 → 2c.3` (delivery) → `2d.0 → 2d.1 → 2d.2 → 2d.3 → 2d.4 → 2d.5` (multi-org) → `2e.1 → 2e.2 → 2e.3` (propagation) → `X1 → X2 → X3`. Each task ships independently and keeps the suite green.
