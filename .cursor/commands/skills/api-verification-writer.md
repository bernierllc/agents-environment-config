---
name: "api-verification-writer"
description: "Writes verification docs for REST endpoints and MCP tools, one operation per doc, under docs/verification/api/ and docs/verification/mcp/. Inventories surfaces from OpenAPI, an MCP tools/list dump and framework route scans, flags spec/code drift, missing auth declarations and thin MCP tool metadata, and records who may call each operation in access frontmatter. Use when an API route, OpenAPI spec or MCP server changes, when documenting API/MCP behavior for customers or agents, or when the access manifest needs API/MCP entries. Companion to verification-writer (UI) and api-verification (runs the access matrix)."
tags: ["skill"]
---


# API Verification Writer

UI verification docs describe pages. This skill describes **operations**: REST endpoints and MCP tools. Same layout, same `access:` contract, same manifest, so the docs agents and CI read one source of truth for what is public, internal, admin-only or still a draft.

**Companions:** `verification-writer` (pages, owns the manifest builder) · `api-verification` (executes the access matrix from these docs) · docs agents (consume `docs/verification/access-manifest.json`).

## Workflow

0. **Name the incumbent first.** Look for an existing drift gate (a `check-*spec*`/`openapi` script, a prebuild step, a CI job). If the repo already fails the build on spec/route drift, reuse it and skip the scanner's drift findings; the scanner still adds `no-security-declared` and the MCP checks.
1. **Inventory.** `aec run-script skill:api-verification-writer scan-api-surfaces.py --root . --prefix /api/v1`
   - `--prefix` (repeatable) scopes to the public surface. Without it internal UI, auth-callback and webhook routes show up as "undocumented".
   - Runtime-built spec (TS module, framework route)? Dump it (`curl http://localhost:PORT/api/v1/openapi.json > /tmp/spec.json`) and pass `--openapi /tmp/spec.json`; a local URL also works. A directory path is an error. If the spec is built by a TS module, evaluate it directly (e.g. `tsx -e` calling the builder, with whatever env vars its config module requires set to dummy values); no server needed. If no code route matches any spec operation you get one `spec-code-mismatch` finding: wrong spec or wrong scope, not hundreds of real drifts. Code routes with no spec operations at all give one `spec-missing` finding.
   - `--prefix` matches full paths, so for routers mounted under a prefix in code (`router.get('/users')` at `/api/v1`) omit it or the code routes are filtered out. Receivers other than `app|router|server|fastify` (e.g. `api.get`, an HTTP client) are not treated as routes.
   - `--exclude /api/v1/mcp` (repeatable; give the path as the spec writes it; code routes that omit the mount prefix are also dropped when they suffix-match an excluded operation with the same method and have at least one literal segment) marks routes intentionally absent from the spec (a JSON-RPC MCP transport, internal paths); cover those with the MCP checks instead. OPTIONS routes are ignored. Nested checkouts (a directory with its own `.git`, such as a worktree) are skipped and listed in `skipped_nested_repos`; routes are deduped on (method, path).
   - MCP: add `--mcp-tools tools.json`, a `tools/list` result from a running test server. Cleanest dump: the MCP Inspector CLI (`npx @modelcontextprotocol/inspector --cli <server-url> --method tools/list`; check `--help` for your transport), or `client.listTools()` from the MCP SDK saved as JSON. Without a dump the scan reports 0 tools. For a repo with a code registry, call the registry through the same mapping the server's own `tools/list` handler uses (otherwise the dump can show annotations the live server never sends). Importing server modules may need dummy env vars (a site name, a DB URL that is never connected to; run once, collect every `X is required` error, and set them all rather than fixing one per run); that works only where import has no side effects, so check before suggesting it. A registry dump is unfiltered by scope: a superset of what any one key sees. MCP findings are grouped one per kind with the tool list; `mutating_tools` (delete_*, send_*, create_*, ...) are where a missing annotation matters most.
   - Spec beats code scan; disagreement is a finding, not something to reconcile silently. Session-authed UI routes vs API-key routes are not distinguished; use `--prefix`.
2. **Triage findings** (see `references/findings-format.md`). `no-security-declared` means someone must say whether the operation is public; do not guess.
3. **Write one doc per operation** following `references/doc-format.md`. Front matter carries `surface`, `method`+`path` or `tool`, `generated_by: api-verification-writer@<version>`, and `access:` including `visibility`.
4. **Regenerate the manifest:** `aec run-script skill:verification-writer build-access-manifest.py --root .`; commit it with the docs.
5. **Report** using the findings format, including the Cross-agent feedback section.

## Rules

- `visibility` is declared by a human or an upstream source, never inferred. Absent means `draft`. An operation behind a feature flag that is off in production (`gated_by`) is not customer-facing: declare it `internal` even when the spec lists it with ordinary scopes. The manifest builder flags `public` + `gated_by` as `public-gated-by-flag`.
- Docs may be generated by a script from the spec and tool registry, or written by hand, as long as every behavior claim is sourced from spec, code or a run and anything else is marked unverified.
- Behavior claims (status codes, error shapes, side effects) must be observed in code, spec or a run. Mark anything else `unverified` so docs agents do not publish it.
- Never put tokens, keys or real customer data in a doc. Principals are named, secrets live in env vars.
- Mutating operations (POST/PUT/PATCH/DELETE, destructive MCP tools) are documented with their side effects; running them is `api-verification`'s decision, not this skill's.
- Parity: a capability exposed by both REST and MCP should say so in both docs (`related:`); a gap is a finding.

## Stamp compatibility

`verification-writer`'s version scan accepts `api-verification-writer@x.y.z` stamps and does not report them as malformed.
