# Tasks: 3D vertical slice

Carved out of `devgate-spec-coherence-service` Sprint S7 on 2026-09-28 (owner).
Spec requirements stay where they were written (`coh-3d-01..04`,
`coh-assert-05`); this list is the implementation backlog.

## Sprint 3D-1 — composite subject and first room

- [ ] 3D composite subject manifest: world IR, GLB assets, engine scene, executable build, captures, evaluation records; part-digest composition (coh-3d-01).
- [ ] Map first room's normative requirements to stable assertion IDs under the operational assertion schema.

## Sprint 3D-2 — capture and the one gated build

- [ ] Capture pipeline under pinned configuration; captures as declared inputs, evaluators never render (coh-3d-04).
- [ ] Gate one Godot build and one bounded repair through the same contract; no pipeline-specific branching (coh-3d-03).
- [ ] Prove repaired digest invalidates earlier attestation; new PASS binds repaired digest (coh-3d-02, acceptance Fixture G).

## Sprint 3D-3 — vision posture

- [ ] Vision observations advisory-only until reproducibility criteria met (coh-assert-05).

**Gate:** evidence-backed promotion + deterministic halt demonstrated. **Blocks:** 3D enforcement.

## Notes

- Vision determinism (the reproducibility criteria themselves) is Redeye's
  domain. This package only holds observations non-canonical until those
  criteria exist.
- No arm64 in scope. No arm hardware in the fleet; the execution-profile
  machinery already accepts a second platform when one is provisioned.
- "Deterministic halt" at the gate means the shared promote-or-halt contract
  refuses on digest change (coh-3d-02) — not that a Godot build is
  bit-reproducible across toolchains.