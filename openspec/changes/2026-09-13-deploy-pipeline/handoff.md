# Handoff: deploy-pipeline

## Traceability

| Audit finding | Spec requirement | Sprint |
|---|---|---|
| C7 gate audits submodule | rel-target-01 | 1 |
| C6 npm audit downgrade | rel-audit-01 | 2 |
| H7 double upload | rel-upload-01 | 3 |
| M5 advisory-as-gate | rel-upload-01 (D4) | 4 |
| M6 vacuous artifact verify | rel-artifact-01 | 4 |
| L8 short SHA unvalidated | rel-fixcommit-01 | 5 |

## Executor notes

- Sequencing: if 2026-09-13-gate-correctness has not landed, implement D1's
  env contract defensively (env wins, cwd fallback) so the branches merge in
  either order.
- Never run a real publish from a test. The dry-run harness (3.2) stubs
  twine/npm/cargo with PATH shims and asserts call counts.
- Keep deploy.sh under DevGate's own 500-line hard limit; extract the
  artifact-verify block into scripts/artifact_verify.sh if needed.
