## ADDED Requirements

### Requirement: 3D subject manifest

<!-- id: coh-3d-01 -->

A 3D subject MUST be expressible as a composite subject manifest whose parts are individually digestible: world IR, generated asset files (e.g. GLB), engine scene, executable build, captures, and prior evaluation records. The composite subject digest MUST be computed over the part manifest under the canonical profile, so any part change changes the subject identity.

#### Scenario: any part changes

- **GIVEN** a world bundle whose scene file changes by one byte while all other parts are unchanged
- **WHEN** the subject manifest is recomputed
- **THEN** the composite subject digest changes and prior results no longer bind.

### Requirement: repair invalidates prior results

<!-- id: coh-3d-02 -->

A bounded repair that produces a new asset, scene, or build digest MUST create a new subject identity. Prior PASS results and attestations bind the pre-repair digest only and MUST NOT promote the repaired subject; the full required gate MUST run again against the new digest.

#### Scenario: repaired bundle presented with old attestation

- **GIVEN** an original bundle that failed, a repair producing digest D2, and a later PASS attestation for D2
- **WHEN** a promotion consumer is presented the pre-repair attestation for D1 against subject D2
- **THEN** promotion is refused on digest mismatch, and only the D2-bound PASS may promote.

### Requirement: pipeline consumes the common contract

<!-- id: coh-3d-03 -->

The 3D pipeline MUST consume the same decision contract (decision state, exit code, ledger, findings, attestation) as code subjects, without pipeline-specific pass logic or result-shape branching. Promote-or-halt behavior follows the same policy rules, including stage-aware ADVISORY acceptance.

#### Scenario: 3D asset candidate passes

- **GIVEN** a generated world bundle with immutable asset, scene, build, capture, and evaluation manifests
- **WHEN** all required OpenSpec assertions pass
- **THEN** the service emits PASS and a promotion system may advance the exact subject digest.

#### Scenario: no pipeline-specific branching

- **GIVEN** a promotion consumer handling both code and 3D subjects
- **WHEN** it parses results
- **THEN** one schema and one decision path handle both; subject-kind differences live in the subject manifest, not the result contract.

### Requirement: captures are declared inputs

<!-- id: coh-3d-04 -->

Render captures or sensor outputs used by assertions MUST be produced under a declared, pinned capture configuration and enter evaluation as digested subject parts or captured facts. An evaluator MUST NOT invoke rendering or simulation itself.

#### Scenario: capture regenerated differently

- **GIVEN** the same scene captured under two different pinned capture configurations
- **WHEN** assertions consume the captures
- **THEN** each capture carries its configuration digest, and results record which capture identity they evaluated.
