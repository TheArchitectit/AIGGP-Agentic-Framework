# Tasks: add-fleet-manager-boundary

Program package: `devgate-product-tiers-fleet-manager`, Sprint 1 box 1.1
(repository and contract gates). Box 1.2 (versioned contracts) and 1.3
(extraction rehearsal) are separate changes.

## 1. The boundary root

- [ ] 1.1 `fleet-manager/README.md`: license notice (BSD 3-Clause, root
      `LICENSE`, no separate grant per OD-001) + dependency rules in prose
- [ ] 1.2 `fleet-manager/manifest.json`: schema tag, boundary root, license
      block, declared path patterns, `forbidden_roots`, `exempt_paths`
- [ ] 1.3 The manifest's declared patterns cover every tracked file under the
      root, and the gate proves it (`--check` run in CI)

## 2. The gate

- [ ] 2.1 `scripts/check_boundary.py`: manifest validity (exit 2), coverage
      (exit 1), dependency direction (exit 1), `--changed-base` scattered-code
      check (exit 1); clean tree exits 0
- [ ] 2.2 `tests/test_check_boundary.py`: planted core→boundary import,
      allowed boundary→core import, undeclared file under the root, malformed
      manifest, forbidden changed path, prose mention in docs is not a
      violation, and the exempt list is pinned to the gate script and its test
- [ ] 2.3 CI: required step in the `specs` job

## 3. Evidence

- [ ] 3.1 `docs/qa/2026-10-24-fleet-manager-boundary.md`: what was created,
      the gate's own runs, the mutation proofs, the stated limits of the
      static detector
