# API and MCP verification skills, and the access manifest

**Status:** Proposed (2026-10-19). **Owner:** Needs-PM (tier/priority not yet assigned).

## Problem

AEC ships a UI verification chain: `verification-writer` (analyzes code, writes `docs/verification/` with `access:` front matter, flows, user types, findings), `browser-verification` (walks the docs in a browser), and `playwright-test-generator` / `playwright-test-runner` (turn the docs into regression tests). Nothing equivalent exists for REST APIs or MCP servers:

- `route-scanner.py` only finds Next.js `route.ts` files. It has no OpenAPI, FastAPI, Express or MCP awareness.
- API items in verification docs are a footnote (`*API-only*` + `API-VERIFICATION-FLAG`), not a first-class surface.
- No skill executes an API or MCP tool as a given role/scope and asserts the authorization boundary.
- Which endpoints and tools exist, and for whom, is enforced in code but not published as data.

Consequence for documentation: the customer-docs agent (`bernier-customer-documentation`) cannot know what is customer-facing, admin-only, tier-gated or unreleased. It would document from prompts, and its new SEO/AEO output (llms.txt, markdown twins, docs MCP) makes a wrong or leaked claim cheap to crawl.

## Incumbent check

- `verification-writer` already owns the `access:` front-matter contract (`public`, `auth_model`, `required_roles|permissions|scopes`), user-type sections, flow docs, `affected_paths`, version fingerprints and the findings report. **Extend it; do not fork the contract.**
- `playwright-test-runner` already manages isolated test envs, execution and fix loops. The API runner reuses its environment handling by reference.
- `mcp-builder` guides *building* servers, not verifying them. Different job.
- Playwright's `APIRequestContext` and the MCP SDK client / Inspector CLI already do the HTTP and MCP calls. Scripts here are thin glue (scan, merge, diff), well under the 50-line-per-tool threshold, not reimplementations.

## Proposal

Two new skills plus one shared artifact, mirroring the UI chain.

### 1. `api-verification-writer` (writer; REST and MCP surfaces)

Analyzes the codebase and emits `docs/verification/api/*.md` and `docs/verification/mcp/*.md`, one file per resource or tool group, same front-matter conventions as page docs:

- `surface: rest | mcp`, `path` or `tool`, `version`, `generated_by`, `affected_paths`.
- `access:` identical schema to pages, extended with `tier` (entitlement/plan gate) and `visibility: public | internal | admin | draft` (default `draft`). Visibility is authored by a person in the doc's frontmatter and reviewed in the PR like any doc change; the writers always emit `draft` for new docs and never infer or overwrite it, and the generated manifest is never hand-edited. Promotion to `public`, `internal` or `admin` is that one-line frontmatter edit.
- MCP extras: tool `annotations` (`readOnlyHint`, `destructiveHint`), input/output schema summary, required scope.
- Role sections ("As Admin", "As Member", "Unauthenticated") with items in the existing item format; authorization-boundary items (wrong role gets 403/denied) are first-class, not deep-only extras.
- Flow docs may span surfaces (UI step, then API call, then MCP tool) so user flows stay in one place.

Discovery order (most authoritative first): generated OpenAPI spec, live MCP `tools/list` / tool registry, then framework route scanning. Where two sources disagree, that is a finding (spec drift, undocumented route, tool missing from catalog), not something to paper over.

Findings report (same format as verification-writer's): routes/tools analyzed, missing auth, missing descriptions/annotations/output schemas, spec-vs-code drift, REST/MCP parity gaps, and a **"Cross-agent feedback"** section (see below).

### 2. `api-verification` (runner; the browser-verification / playwright-runner equivalent)

Executes the API/MCP verification docs against a **local or test environment only**:

- REST via Playwright `APIRequestContext`; MCP via the MCP SDK client over stdio or HTTP.
- **Role/scope matrix:** for each item, call as every declared role/scope/permission/tier plus unauthenticated (principals.json lists roles, scopes, permissions and tier per principal; a permission-gated operation is probed with a principal holding it and an authenticated one lacking it), assert the allowed ones succeed and the others are denied. A mismatch between `access:` and actual behavior is the headline finding (doc wrong or code wrong; never silently update either).
- Logs, fixes-or-findings and the run summary follow browser-verification's structure.
- Safety: test credentials from `.env*` only, allowlist, not heuristic: the runner refuses any base URL that is not loopback, private-range, link-local-excluded, `.local`/`.localhost`/`.test`/`.internal`, or named in `API_VERIFICATION_ALLOWED_HOSTS` (a production URL with no recognizable marker is refused by default), no secrets or tokens written to docs or logs, destructive tools run only against seeded fixtures.
- A generator step (verification docs to persisted Playwright API tests) is **deferred**; the runner executes docs directly first. Add the generator only if regression-test persistence proves necessary.

### 3. Access manifest (shared, generated, never hand-edited)

`docs/verification/access-manifest.json`, produced by a small script in `verification-writer` (pages) and `api-verification-writer` (API/MCP) merged into one file:

```json
{ "generated_from": "<git sha>",
  "entries": [ { "surface": "page|rest|mcp", "id": "...", "visibility": "public|internal|admin|draft",
                 "auth_model": "...", "public": null, "roles": [], "scopes": [], "permissions": [], "tier": null, "gated_by": [],
                 "user_types": [], "affected_paths": [], "verified_at": "<sha>" } ] }
```

One manifest entry per independently gated operation: a grouped doc with a public GET and an admin-only POST is split into two entries (the writers emit one `access:` block per operation doc, never the most permissive of a group).

Combination semantics (as built in `api-verification/scripts/matrix.py`): every declared kind (roles, scopes, permissions, tier) must be satisfied, and within a kind the principal needs any one listed value. `public: true` means unauthenticated callers may reach the operation; `visibility` only says who may read the docs, so the two are separate fields. The `access:` frontmatter contract in `verification-writer` is extended in this plan to allow several `required_*` kinds at once (today it permits only the fields of the single `auth_model`); existing documents stay valid because every field is optional. An operation needing both Admin and `billing:write` is therefore `roles: [Admin]` plus `scopes: [billing:write]`; alternatives (Admin OR a scope) are two entries.

The manifest, not an agent's judgment, decides audience. Static discovery is not verification: `verified_at` is written only by the runner (`matrix.py evaluate` with zero mismatches, stamped with the git SHA it ran against). Consumers send an entry into crawlable outputs only when `visibility` is `public` AND `verified_at` matches the current SHA of its `affected_paths`; otherwise it is treated as unverified and kept `draft`. Consumers: the customer-docs agent, the internal-docs agent, `llms.txt` / sitemap / MCP-index build steps, CI.

## How the docs writer uses it

- Reads the manifest if present. The destination comes from `visibility` alone: `public` entries become customer docs, `internal` entries internal docs, `admin` entries admin guides. Roles, scopes and tiers only describe access and availability inside that page (a `visibility: public` operation gated to `member` is customer documentation that says so);  only `draft` (the default, never inferred) is withheld from everything, and only `public` enters crawlable outputs.
- No manifest: every claim is marked `unverified` and pages stay `draft`.
- User flows come from flow docs (`user_types`, ordered steps), not from the agent inferring them. Flow docs have no `access:` block (the incumbent contract gives them none), so the manifest has no `flow` entries and phase 1 drops `flows` from `SURFACE_DIRS` in `build-access-manifest.py` (with a test). Flow frontmatter instead lists the manifest ids it touches (`entries: ["/events/{id}", "POST /events"]`; page slugs and item ids are not manifest ids). Fail closed: an empty list, or any id with no manifest entry, withholds the flow as draft. Otherwise the flow's destination is the most restrictive visibility among its entries (all `public` → public; any `admin` → admin; else any `internal` → internal; any `draft` → draft), so a flow with one admin-only step stays out of customer docs rather than leaking it. A flow is published only when every listed entry has a current `verified_at` and the flow's own `affected_paths` are unchanged since the newest of them. Only the API runner stamps `verified_at` today; until a page stamper exists, flows with page steps stay draft.

## Feedback loop between agents and skills

Each producer writes a "Cross-agent feedback" section in its findings report; the other side reads it on its next run:

| From | Signal | Meaning |
|---|---|---|
| docs writer | feature documented, no verification doc | verification coverage gap |
| docs writer | wants to document an "API-only, permanent" item | durability flag likely wrong, or the thing is internal |
| verification-writer / api-verification-writer | `access:` changed (major bump) | dependent docs are stale |
| browser-verification / api-verification | affordance mismatch, or role matrix differs from `access:` | docs may describe a control or permission that does not exist; flow doc may be wrong |
| docs writer | reader-visible flow contradicts a flow doc's steps | flow doc written incorrectly; feed back to verification-writer |

## AEC product constraints

- Generic for every AEC user: no maintainer projects, hosts or workflows in committed files (`tests/test_no_maintainer_specifics.py` enforces). Placeholder names only. Project-specific wiring (for example a repo's tool-catalog generator) stays in that repo.
- Skills under `.claude/skills/`, each with `SKILL.md`, a `hooks.json` where staleness scanning applies (mirroring verification-writer), and scripts invoked through `aec run-script`.
- Every skill change bumps the version in the same commit, then `python3 scripts/generate-manifest.py`; `scripts/check-version-bumps.py` gates CI. Extending verification-writer (manifest emit, `visibility`/`tier` fields) is a minor bump and must keep existing docs valid.
- Declare the new skills' dependencies so `aec install` pulls them with their counterparts (see `tests/test_skill_dependencies.py`).
- Scripts get tests (`test_*.py`, as `route-scanner` does). The manifest merge is tested on behavior: given page, REST and MCP fixtures, the output contains each entry with the right visibility; a conflicting source produces a finding.

## Phases

1. **Contract:** manifest schema; extend `access:` with `tier` and `visibility` (default `draft`); verification-writer emits manifest entries for pages. Version bump, tests.
2. **Writer:** `api-verification-writer` for OpenAPI plus MCP registry discovery (framework route scanning second); findings with drift detection.
3. **Runner:** `api-verification` with the role/scope matrix and production-URL refusal.
4. **Docs agents:** `bernier-customer-documentation` and internal-documentation read the manifest; `draft`-by-default rule and unverified-claim rule; build-step integration guidance (llms.txt, twins, MCP index only for `public`).
5. **Feedback loop:** "Cross-agent feedback" sections in all findings reports and the readers on each side.

## Open questions

1. Visibility vocabulary: are `public | internal | admin | draft` enough, or is "beta/unreleased-flag" a fifth value distinct from `draft`?
2. Where does the manifest merge script live so both writers share it (in `verification-writer`, or a small shared skill)?
3. MCP discovery: source-registry parsing is stack-specific; is live `tools/list` against a test server the only generic path?
4. Does the docs agent live in this repo's skill ecosystem or only in `agency-agents` (it is a separate repo today)? The agent change (PR bernierllc/agency-agents#3) lands first and is manifest-optional.

## Not in scope

Persisted API test generator; production verification; a docs-site build (the agent only specifies the outputs).
