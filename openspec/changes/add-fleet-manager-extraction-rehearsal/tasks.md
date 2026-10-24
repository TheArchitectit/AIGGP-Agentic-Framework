# Tasks: add-fleet-manager-extraction-rehearsal

Program package: `devgate-product-tiers-fleet-manager`, Sprint 1 box 1.3
(extraction rehearsal in CI). Predecessors: `add-fleet-manager-boundary` (1.1),
`add-fleet-manager-contracts-v1` (1.2).

## 1. The rehearsal

- [x] 1.1 `fleet-manager/scripts/extraction_rehearsal.py` — phase A (boundary
      alone + declared build inputs, extra files refused, its suite must pass)
- [x] 1.2 Phase B — repository without the boundary: core suite collects, the
      pattern scan runs, and a zero-collection result is a failure, not a pass
- [x] 1.3 `--keep` for local inspection; exit 0/1/2 with the phases named

## 2. The gate refinement it forced

- [x] 2.1 `fleet-manager/manifest.json`: `invocation_paths` +
      `fleet-manager/scripts/**` declared
- [x] 2.2 `scripts/check_boundary.py`: the allowance, validated (repo-relative,
      not inside the boundary)
- [x] 2.3 `tests/test_check_boundary.py`: the pin, an invocation site that may
      name the boundary, a non-invocation file that still reds, and an
      invocation site inside the boundary as a manifest error
- [x] 2.4 `check_boundary.py`'s own marker made comma-separated — it was
      silently covering one requirement out of four

## 3. Wiring and evidence

- [x] 3.1 CI: the rehearsal runs in the `tests` job next to the contract suite
- [x] 3.2 `docs/qa/2026-10-24-fleet-manager-extraction-rehearsal.md`: the runs,
      the planted cases, and what phase B does and does not prove
