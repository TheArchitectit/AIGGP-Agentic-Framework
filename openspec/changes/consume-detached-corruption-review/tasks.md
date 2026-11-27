# Tasks

- [x] 1. Add and validate an exact-review requirement before implementation.
- [x] 2. Add detached review loading with external path, SHA-256 verification, verified repo/run identity and strict committed `BASE..HEAD` validation.
- [x] 3. Preserve backward-compatible legacy callers; exact-review mode bypasses consumer range suppressions and inventories all substitution and mass-rewrite findings.
- [x] 4. Add positive, stale-clean, self-approval, altered-tree, changed-base, malformed digest/schema, symlink, and arbitrary-range negative controls.
- [x] 5. Run focused tests, the corruption scanner's controls, strict OpenSpec validation, traceability and regression checks.
- [x] 6. Keep release checksums synchronized with the changed shipped scanner and new review CLI; verify all 161 tracked script entries. The first native DevGate run identified the stale manifest (https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46065074313/job/140728310043); regenerated manifest verification passes.
- [x] 7. Specify and validate the shipped-script checksum coverage requirement in the upstream integrity spec.
