# Handoff: rule-enforcement-gaps

## Traceability

| Audit finding | Spec requirement | Sprint |
|---|---|---|
| H1 dead semantic rules | rule-truth-01 | 1 |
| M1 extracted-rules dead | rule-behavior-01 | 2 |
| H6 Python markers | rule-marker-01 | 3 |
| M2 submodule-only config | rule-config-01 | 4-5 |
| M3 enabled-by-default families | rule-fresh-01 | 4 |

## Executor notes

- D1 is the honest-coverage decision; do not leave rules "temporarily
  enabled" — enabled means implemented, per rule-truth-01.
- Coordinate with 2026-09-13-baseline-hygiene before shrinking the bundled
  allowlist (it owns the file); this change owns the merge *mechanism*.
- SEMANTIC-005 fixtures: plain missing-dep, stable-ref suppression, custom
  hook, and a guardrails-allow escape.
