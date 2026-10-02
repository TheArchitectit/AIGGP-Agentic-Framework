> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

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
- [x] Reconcile at coherence-service archive: CLOSED 2026-10-01 (feat commit `a74455a`
      + this ledger edit). `devgate-spec-coherence-service` archived 2026-10-01: 11
      capability deltas published to `openspec/specs/<cap>/spec.md`, change dir moved to
      `openspec/changes/archive/2026-10-01-devgate-spec-coherence-service/`. Re-run
      complete per `reconciliation.md` §7 "Reconcile-at-archive checklist" — 4 of 4 items
      dispositioned: (1) published-comparison re-verify measured byte-identical at the
      four row-referenced IDs (`coh-pol-01`, `coh-pol-04`, `coh-eval-01`, `coh-int-03`);
      strictly-stronger verdicts unchanged. (2) The three novel items are **deferred**
      (`stated assumption SA-1`) — the standing rule "AIGGP program not started" still
      holds; the reconciliation scope limit forbids adopting a drafted requirement via
      mere archive. (3) No `## MODIFIED` deltas land this iteration (`SA-3`): even
      though MODIFIED is now name-resolvable against the published specs, flipping
      would formally mutate the shipped set — the thing the draft proposes, not
      effects. (4) The 3D-pipeline overlap resolves to the shipped `coh-3d-02/03` +
      `coh-int-03` set — the draft's `promote-halt-contract` text is strict-subsumed,
      no consumer-side gap documented. **Net: AIGGP-02 keeps its `## ADDED` shape with
      no `<!-- id: -->` markers; the shipped `coh-*` specs stand unchanged.** The
      aiggp-02`reconciliation.md` file is the durable record; the §7 checkbox list is
      now `CLOSED 2026-10-01`.
