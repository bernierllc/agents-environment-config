# Render shared directory paths deterministically

Status: deferred P2 from PR #131; scheduling pending.

## Root cause and affected surfaces

`aec/lib/hooks/setup.py:configured_hooks` iterates directory declarations and
rewrites already-modified predicates and match expressions. Nested defaults
such as `docs` and `docs/reports` therefore depend on declaration order. A
selected destination that overlaps another default can also be rewritten a
second time. Sorting by prefix length alone does not prevent that cascade.

This renderer is shared by install, upgrade and drift verification/repair.
Predicates `repo_has`, `repo_has_any`, and `repo_lacks`, plus hook match
expressions, must agree with the configured resource readers. Command directory
placeholders are explicit keys and must not be treated as ambiguous prefixes.

## S1 — Single-pass rendering from original declarations

1. Keep original hook values immutable while rendering. For each original
   predicate path, choose the longest matching declared default at a path
   component boundary, replace once, and preserve the unmatched suffix.
2. Define equal-default ambiguity explicitly: reject conflicting destinations
   for aliases or require a single unambiguous result. Validate normalized
   defaults rather than depending on dictionary order or trailing slash spelling.
3. Handle the existing match-expression syntax deliberately: identify original
   path-prefix occurrences and replace nonoverlapping spans once, without
   interpreting selected destinations as new input. Preserve glob/regex syntax
   outside those spans. If a supported expression cannot be mapped safely,
   fail validation with a specific diagnostic instead of silently guessing.
4. Reuse configured_hooks for install and drift; do not duplicate the mapping
   in either caller or runtime reader. Keep command placeholders keyed and
   shell-quoted, rendered from the original command without cascading replaces.

## Acceptance tests

Permutation tests must produce identical output for parent/child defaults in
both orders. Cover exact-root and descendant predicates for all three fields,
nonmatching sibling prefixes, selected paths overlapping other defaults,
unchanged/default destinations, ambiguous aliases, and paths with spaces.
Cover multiple prefixes in match expressions and preserve expression syntax.
Assert original HooksFile input remains unchanged. Install real hooks using
nested custom roots and verify execution plus Drift.OK after repair.

Until this ships, nested/overlapping directory defaults are a known limitation;
items with one shared directory key are unaffected by this ordering defect.

Finding: https://github.com/bernierllc/agents-environment-config/pull/131#discussion_r4530578584
