# Tasks

- [x] 1. Add and validate an exact-review requirement before implementation.
- [x] 2. Add detached review loading with external path, SHA-256 verification, verified repo/run identity and strict committed `BASE..HEAD` validation.
- [x] 3. Preserve backward-compatible legacy callers; exact-review mode bypasses consumer range suppressions and inventories all substitution and mass-rewrite findings.
- [x] 4. Add positive, stale-clean, self-approval, altered-tree, changed-base, malformed digest/schema, symlink, and arbitrary-range negative controls.
- [x] 5. Run focused tests, the corruption scanner's controls, strict OpenSpec validation, traceability and regression checks.
