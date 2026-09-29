# Proposal: 3D vertical slice

## Why

The coherence contract already specifies 3D subjects (`coh-3d-01..04`,
`coh-assert-05` in `devgate-spec-coherence-service/specs/subjects-3d/` and
`assertions-and-evaluators/`). Sprint S7 of that package held the
implementation checklist. Carved out 2026-09-28 (owner, architect) so
`devgate-spec-coherence-service` can be accepted on its shipped surface —
stdlib coherence core, pinned container, fleet adapter, attestation chain —
without a Godot/3D capture pipeline sitting in its tasks list as unfinished.

This package is the implementation of those already-frozen requirements. It
redefines nothing: no new `coh-*` IDs, no design.md contract change, no
decision-matrix change. The coherencing service must consume 3D through the
same promote-or-halt contract as code (coh-3d-03); this package builds the
composite subject, the capture pipeline, and the one Godot build + bounded
repair demonstration.

## What Changes

- 3D composite subject manifest implementation (world IR, GLB, engine scene,
  executable build, captures, evaluation records; part-digest composition).
- First room's normative requirements mapped to stable assertion IDs under
  the existing operational assertion schema.
- Capture pipeline under pinned configuration; captures are declared inputs;
  evaluators never render (coh-3d-04).
- One Godot build and one bounded repair through the same contract; no
  pipeline-specific branching (coh-3d-03, coh-3d-02 / acceptance Fixture G).
- Vision observations advisory-only until reproducibility criteria are met
  (coh-assert-05). Vision determinism itself is Redeye's domain — this
  package only keeps the observations non-canonical.

## Non-Goals

- No change to the coherence decision contract, exit matrix, or attestation
  chain. Those are frozen and accepted.
- No arm64 work (no arm hardware in the fleet).
- No vision-determinism resolution (outside this package).
- No AIGGP ID wiring.

## Impact

- Specs: none new. Implements `coh-3d-01..04` and `coh-assert-05` as already
  specified under `devgate-spec-coherence-service`.
- Tests: new fixtures + capture-pipeline tests; dual-runnable pytest /
  `__main__` in the coherence suite's style.
- Folders: Godot project / capture tooling TBD at first sprint; the repo is
  stdlib-only on the request path, so capture tooling stays outside
  `hub/`.