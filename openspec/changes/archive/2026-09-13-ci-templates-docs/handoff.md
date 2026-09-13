# Handoff: ci-templates-docs

## Traceability

| Audit finding | Spec requirement | Sprint |
|---|---|---|
| H2 drift template red-by-default | ci-run-01 | 3 |
| M4 compliance template matching | ci-match-01 | 4 |
| M9 no framework CI | ci-self-01 | 2 |
| M7 version drift | doc-version-01 | 5 |
| M10 AGENTS.md contradictions | doc-overlay-01 | 5 |
| L3/L4/L5 small drift | ci-match-01, ci-self-01 | 1 |

## Executor notes

- Sprint 1 must merge before Sprint 2 or the new CI is born red.
- The drift template's SKIPPED state needs the gate-correctness change's
  documented skip output; if that lands later, key on exit code + the
  existing skip strings.
- Reconstructed CHANGELOG sections come from `git log v1.0.0..v1.2.0
  --pretty=%s`; mark them reconstructed.
