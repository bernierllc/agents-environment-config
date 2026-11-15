# Custom-source validation hardening

**Source:** Codex P2 r4580011167 and r4580011170 on PR #132 (deferred by decision, round 13).
Status: not started. Both come from the same gap: a custom source's content or an
item's `version` is trusted where it should be validated at the boundary and reported as
a structured failure.

## Root cause

1. **Malformed source file crashes instead of failing the source.** `_check_item_paths()`
   (`aec/lib/org_config/apply.py`) calls `discover_available()`, which reads each rule,
   agent or skill with `read_text(encoding="utf-8")`. A file that is not valid UTF-8
   raises `UnicodeDecodeError`, and the handler in the source-sync loop catches only
   `OrgConfigError`. The exception skips the `source_failed` outcome and the staged
   checkout cleanup, so `aec org apply` and `aec install --org-config` end in the generic
   crash path with no message naming the offending source.
2. **Non-string `version` passes exact-version validation.** The validator
   (`aec/lib/org_config/validator.py`) tests `_EXACT_VERSION.match(str(version))`, so YAML
   `version: 1.0` or `version: 2` (a float or int) passes, but `ItemPolicy` keeps the
   original number. `plan_apply()` then compares it with the catalog's string version and
   reports a matching required item as unsatisfiable.

## Correct fix

1. In the source-sync loop, treat a failure to read a source's files as a source failure:
   either wrap the read in `_check_item_paths` and raise `OrgConfigError` naming the file,
   or make `discover_available` raise one for undecodable content. Pick the one that
   leaves a single owner for "this source's content is unreadable"; do not catch
   `UnicodeDecodeError` in two places. The failure must hit the existing `source_failed`
   path so the staged checkout is discarded and the exit code is 13.
2. In the validator, require `version` to be a string before applying the regex (the
   error names the field and says to quote it, e.g. `version: "1.0"`). Do not normalize
   with `str()`: `1.10` would silently become `1.1`.
3. Tests: a source with a non-UTF-8 rule file gives `source_failed`, cleans staging and
   exits non-zero through both `aec org apply` and `aec install --org-config`; `version: 1.0`
   and `version: 2` are rejected with a field path; `version: "1.0"` still validates.

## Affected surfaces

`aec/lib/org_config/apply.py` (`_check_item_paths`, the source-sync loop),
`aec/lib/sources.py` (`discover_available`), `aec/lib/org_config/validator.py`,
`docs/orgs/authoring-org-configs.md` (note that `version` must be quoted),
`tests/commands/test_org_custom_sources.py`. The version-constraint evaluator plan
(`2026-11-14-custom-source-version-ranges.md`) touches the same validator line, so do
this first or fold the string check into it.

## Done when

A malformed source file and a numeric `version` each produce a clear, field- or
source-naming error and a non-zero exit, under test, with no staged checkout left behind.
