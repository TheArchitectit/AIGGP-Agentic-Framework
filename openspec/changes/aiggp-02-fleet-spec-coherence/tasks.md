- Phase 0 (contract freeze): re-anchor the September 17 contracts to AIGGP-00 envelope and algebra; freeze digests.
- Phase 1 (deterministic core): evaluator, assertion planner, determinism fixtures.
- Phase 2 (container boundary): pinned image, ephemeral isolation, default-deny network, bounded execution.
- Phase 3 (evidence): envelope emission, ledger writes, attestation chain.
- Phase 4 (ladder): stage machinery, ratchet, bounded advisory, exception model.
- Phase 5 (fleet adapters): CI integration per repo, fleet schedule, Mission Control read views.
- Phase 6 (3D vertical slice): promote/halt wired to the AI 3D pipeline on one real candidate flow.
- Phase 7 (hardening and release): adversarial fixtures, image publication, docs.

## Reconciliation ledger

- [x] Reconcile AIGGP-02 requirements against the shipped coherence-service
      ladder (2026-09-20 drift audit, MEDIUM). See `reconciliation.md`: the
      adoption-ladder, coherence-evaluation, and promote/halt requirements are
      duplicates of shipped `coh-pol-01/03/04`, `coh-eval-01/02/04`, and
      `coh-int-03/04`, with the shipped text the stronger of the two; the
      shipped set is the superset (`coh-pol-02/05/06/07` have no draft
      counterpart); envelope-bound evidence, the 3D-pipeline consumer contract,
      and per-project coherence history are novel and **not built — the AIGGP
      program has not started**.
- [ ] Reconcile at coherence-service archive: re-run the comparison against the
      published `coh-*` requirements once `devgate-spec-coherence-service`
      archives into `openspec/specs/`, at which point a `MODIFIED` delta can
      name-match them. Deltas stay `ADDED` until then (see `reconciliation.md`
      §7).
