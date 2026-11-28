# Tasks

## 1. Extraction rehearsal — rows 145–147

- [ ] 1.1 Exercise Phase A in isolated extracted workspaces: declared build inputs only, no undeclared open-core files, and an undeclared-import negative control (`repo-005-01`).
- [ ] 1.2 Exercise Phase B with boundary absent and nonempty core test collection. Make required scanner absence/nonzero execution fail the rehearsal; explicitly test missing Node where the scanner currently reports `SKIPPED` and ensure the rehearsal exits nonzero (`repo-005-02`).
- [ ] 1.3 Verify invocation-path allowlist and dependency direction, including an undeclared reference and a path incorrectly placed under the boundary (`repo-005-03`). Retain exact workspace manifests and exit/output receipts.

## 2. Job lifecycle model — rows 148–152

- [ ] 2.1 Qualify one-job-only behavior, closed transitions, terminal destruction and no return to warm with accepted and refused behavioral cases (`fleet-008-01`).
- [ ] 2.2 Qualify complete cleanup proof shape, optional unknown job identity, failed-disposal refusal, replacement admission ordering and both proof/quarantine dispositions (`fleet-008-02`).
- [ ] 2.3 Qualify inspectable quarantine identity/reason/time and exclusion from warm capacity (`fleet-008-03`).
- [ ] 2.4 Qualify required, positive, bounded resource limits and command rendering of the validated values (`fleet-008-04`).
- [ ] 2.5 Qualify the closed typed-error taxonomy and unexpected-error classification with value-level negative controls (`fleet-008-05`). State clearly that model tests do not prove host cleanup collection or command execution; add separate runtime evidence only if claiming that integration.

## 3. Plan/apply — rows 153–156

- [ ] 3.1 Qualify deterministic identity, ordered change simulation, impossible-change diagnostics and capacity impact (`fleet-002-01`). Directly instantiate or otherwise exercise every public construction path with synthetic caller-supplied capacity summaries that are false, incomplete, reordered or inconsistent; require rejection or recomputation from the base state and changes.
- [ ] 3.2 Qualify apply revision binding, principal scopes, destructive authorization and revalidation against current state/time (`fleet-002-02`). Include stale revision and changed-capacity negative controls and assert no partial state mutation.
- [ ] 3.3 Qualify idempotent same-key/same-plan replay and same-key/different-plan refusal (`fleet-002-03`).
- [ ] 3.4 Qualify append-only audit sequence/timestamp rules, refusal receipts and credential-shaped reason non-disclosure (`fleet-002-04`).

## 4. Provenance and evidence

- [ ] 4.1 For each row 145–156, establish an ordered, reachable historical source/test range with relevant enforcement and tests in range; do not infer historical behavior from current source markers or QA prose alone.
- [ ] 4.2 Create a requirement-specific bundle per claim containing exact source/test paths, named test IDs and receipts, synthetic-control inputs/results, reviewed revision, expected digest and validator result. Preserve NOT_RUN/UNPROVEN when historical provenance or required evidence is unavailable.
- [ ] 4.3 Have an independent reviewer replay the controls and verify range overlap, bundle digests and validator acceptance. Submit only conjunctively supported candidates to the canonical state gate; keep all other rows UNPROVEN.
