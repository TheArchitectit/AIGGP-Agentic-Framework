# Tasks

- [ ] 1. Add and validate an exact-review requirement before implementation.
- [ ] 2. Add detached review loading with external path, SHA-256 verification, canonical repo identity and strict committed `BASE..HEAD` validation.
- [ ] 3. Preserve backward-compatible legacy callers; exact-review mode bypasses consumer range suppressions and inventories all substitution and mass-rewrite findings.
- [ ] 4. Add positive, stale-clean, self-approval, altered-tree, changed-base, malformed digest/schema, symlink, and arbitrary-range negative controls.
- [ ] 5. Run focused tests, the corruption scanner's controls, strict OpenSpec validation, traceability and regression checks.
