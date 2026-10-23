---
name: "api-verification"
description: "Verifies who can call each REST endpoint and MCP tool by running a principal x operation access matrix against a local or test server and comparing responses to what the verification docs declare. Flags over-permissive and over-restrictive operations, and refuses non-local hosts by default. Use after API or MCP auth changes, before releases, or to check that docs and behavior agree on public vs gated surfaces. Companion to api-verification-writer; the API counterpart of browser-verification."
tags: ["skill"]
---


# API Verification

Runs the access matrix. Docs say who should get in (`access:` frontmatter, merged into `docs/verification/access-manifest.json`); this skill checks the running server agrees.

## Prerequisites (halt with a clear message if missing)

1. `docs/verification/access-manifest.json` exists and is current: `build-access-manifest.py --check`.
2. `docs/verification/principals.json` maps each principal to roles/scopes and a `token_env` var **name**. Never tokens. Give a principal `"auth_model"` (the same vocabulary as the docs: `api-key`, `oauth-scope`, `session`, ...) when its credential only works on one kind of entry: it is expected to be denied every entry of another auth_model (an API key sent to an MCP-key endpoint is 403 by design). The comparison is exact, so label a principal with the value its entries use; do not mix `session` and `rbac` for the same cookie credential. Set `"mfa": true` on a principal that completes MFA; entries with `mfa_required` are expected to reject every other principal. An `anonymous` principal with no token is expected.
3. A **local or test** base URL. `matrix.py guard <url>` refuses anything else; extra safe hosts go in `API_VERIFICATION_ALLOWED_HOSTS` (comma-separated). Never point this at production.

## Workflow

1. `matrix.py plan` shows the expected allow/deny matrix. Read it; a surprising expectation is a docs bug (wrong `visibility` or roles), fix the docs first.
2. `matrix.py run --base-url http://localhost:PORT > results.json` probes REST entries as each principal. Mutating methods are skipped unless `--allow-mutating`, and only use that against a disposable database.
3. **MCP:** use `tools/list` as the access signal: a tool the principal can see is allowed (200), a tool missing from the list is denied (403), and a rejected connection keeps its HTTP status. Call a tool only when its `readOnlyHint` is true (never a mutating tool against a shared database). An MCP entry with an `endpoint` is probed there with that endpoint's credential; `run` ignores `endpoint`, so keep it on MCP entries. Write `{"results": [{"id": "<tool>", "principal": "<name>", "status": <401|403|200>}]}` in the same shape.
4. `matrix.py evaluate --results results.json` (add `--denied-status 401,403,302` for cookie apps that redirect to a login page; redirects are never followed, so the token cannot leak to another host). Exit 2 lists mismatches:
   - `over-permissive`: allowed but docs say denied. **Security bug**, fix the code, not the docs.
   - `over-restrictive`: denied but docs say allowed. Fix the code or correct the docs.
   - `server-error`: the probe got a 5xx. The placeholder id reached code that crashed, so the gate was not proven; treat as a bug in the route (a malformed id should be 400/404).
   - `flag-off-reachable`: only with `--flags-off NAME,...` on `plan`/`evaluate`. Entries `gated_by` a flag that is off in this environment must answer 404 or a denied status; anything else means the flag does not gate the route (add 302 to `--denied-status` for apps that redirect to a login page).
5. Write the report to `docs/verification/findings/api-verification-<date>.md` (the scanners skip `findings/`) with a **Cross-agent feedback** section (what docs agents and test runs told you, what changed). Fixes to wrong docs go through `api-verification-writer`, then regenerate the manifest.

Run via `aec run-script skill:api-verification matrix.py <subcommand> ...`.

## Rules

- A mismatch is never resolved by editing the expectation to match the server without checking intent. Over-permissive is code until proven otherwise.
- A principal with no `token_env` is anonymous: no token is sent, whatever roles it lists.
- An unreachable route is a `no-response` mismatch, not a pass. A planned row missing from the results file (and not listed in `skipped_mutating`) is a `missing-result` mismatch, for any surface that has at least one result.
- Status 404/400 caused by the placeholder path id counts as allowed: the auth gate passed the request.
- Do not log or print tokens; reports name principals only.
