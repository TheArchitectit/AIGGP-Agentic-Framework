# Tasks

- [x] 1. Add and validate an exact-review requirement before implementation.
- [x] 2. Add detached review loading with external path, SHA-256 verification, verified repo/run identity and strict committed `BASE..HEAD` validation.
- [x] 3. Preserve backward-compatible legacy callers; exact-review mode bypasses consumer range suppressions and inventories all substitution and mass-rewrite findings.
- [x] 4. Add positive, stale-clean, self-approval, altered-tree, changed-base, malformed digest/schema, symlink, and arbitrary-range negative controls.
- [x] 5. Run focused tests, the corruption scanner's controls, strict OpenSpec validation, traceability and regression checks.
- [x] 6. Keep release checksums synchronized with the changed shipped scanner and new review CLI; verify all 161 tracked script entries. The first native DevGate run identified the stale manifest (https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46065074313/job/140728310043); regenerated manifest verification passes.
- [x] 7. Specify and validate the shipped-script checksum coverage requirement in the upstream integrity spec.
- [x] 8. Regenerate `tests/expected-counts.json` after adding the new collected review suite (147 suites / 2,152 tests; `test_corruption_review` floor 11) and verify the declared/wired test-suite-floor join. Native DevGate run identified the missing floor at https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46067972621/job/140737785072.
- [x] 9. Specify CI's positive per-suite floor and inventory-join requirement for newly collected suites.
- [x] 10. Reconcile checksum and test-floor manifests against current main `cb2205c7460b2f88d1d74583d9b4ae788ccaad66`: regenerate `CHECKSUMS.sha256` for all 162 tracked scripts (including latest `scripts/lib/spec_catalog.py` and `scripts/spec_index.py` changes) and `tests/expected-counts.json` for 148 suites / 2,166 tests (`test_corruption_review` floor 11; `test_spec_catalog` floor 4); verify both gates on the current-base merge tree.
