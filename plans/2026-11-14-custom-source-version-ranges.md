# Version constraints for org-config items

**Source:** Codex P1 r4577168044 on PR #132. Status: in review (PR into `staging`, Tracker AEC-VERSION-RANGES-1).

## Root cause

AEC has no version-constraint evaluator. `version_is_newer` / `parse_version`
(`aec/lib/skills_manifest.py`) compare dotted integers only, and `packaging` is
not a dependency. `plan_apply` (`aec/lib/apply_core.py`) therefore compares an
item's `version_spec` to the source's version as a literal string, so a
constraint such as `>=2.0.0` against version `2.1.0` reports "unsatisfiable".
The default-catalog path ignores `version_spec` altogether, so the docs example
`version: ">=2.0.0"` on an `aec.default.skills` item is accepted but not enforced.

## Interim guard (shipped with PR #132)

Policy validation rejects any `version` on a custom-source item that is not an
exact dotted-integer version (`^\d+(\.\d+)*$`), with a clear error naming the
field. `pinned` already means an exact version.

## Correct fix

1. Add one evaluator in `aec/lib/` supporting `==`, `>=`, `>`, `<=`, `<`, `~=`
   and comma-joined clauses over the existing dotted-integer `parse_version`.
2. Make `plan_apply` use it for every source, default catalog included, so a
   constraint is enforced the same way everywhere.
3. Loosen the validator to accept constraints, rejecting only what the
   evaluator cannot parse.
4. Update `docs/orgs/authoring-org-configs.md` (Items section) to describe the
   supported operators.

## Affected surfaces

`aec/lib/apply_core.py`, `aec/lib/org_config/validator.py`,
`aec/lib/skills_manifest.py` (or a new sibling), `docs/orgs/authoring-org-configs.md`,
tests for the evaluator and for validator and apply behaviour with ranges.

## Done when

`>=2.0.0` against `2.1.0` plans as install or noop on both a custom source and
the default catalog, and `<2.0.0` against `2.1.0` is reported unsatisfiable,
all covered by tests.

## Implementation (2026-11-21)

- Incumbent reused: `parse_version` in `aec/lib/skills_manifest.py` (dotted integers
  only). It parsed but did not evaluate constraints, so `parse_version_spec` and
  `version_satisfies` sit beside it in the same module; no new module.
- `plan_apply` evaluates every item's `version_spec` through `version_satisfies`,
  default catalog and custom sources alike. Mismatch and malformed pins both plan as
  `unsatisfiable` with a reason naming the item, pin and available version (or the
  supported syntax). An installed copy outside the pin is replaced.
- The validator calls `parse_version_spec` for every non-plugin item version (any
  source), requires a quoted string, requires a version for `pinned`, and limits
  `pinned` to one exact version. The custom-source-only exact-version guard is gone.
- Docs: a constraint gates, it does not select; rollback means an immutable custom
  source pinned by `commit`. AEC has no mechanism to pin the built-in catalog to an
  older AEC release (follow-up, not built here).
- Side effect: `aec apply <portable manifest>` now enforces the exact versions that
  `aec export` writes; a catalog at another version fails that item unless `--latest`.
