# AIGGP OpenSpec review and gap register

**Reviewed revision** `fd2c11f08aa74f8b1f4917a7a5c2785860ef4cf1` on `main`

**Review date** 2026-11-25 UTC

The [open, closed, and coded inventory](2026-11-25-aiggp-open-closed-coded.md)
covers all 56 published specs, their 251 requirement headings, the two
active changes, and 43 archived packages. The
[integration gap review](2026-11-25-aiggp-integration-gaps.md) covers reusable
consumer workflows and the GitLab distribution and monitoring boundaries.

AIGGP's generated index reports one CLOSED, one DEFERRED, 42 UNPROVEN, and
12 UNKNOWN specs. The append-only ledger records two closure proofs for
`doc-truth`. Review state, code markers, and test evidence are tracked
separately. The 182 unproven ledger records stay unresolved until the existing
evidence gate accepts proof for each requirement.

## Validation at the reviewed revision

| Check | Observed result |
|---|---|
| OpenSpec 1.14.3 `validate --all --strict` | 58 passed, including all 56 published specs and both active changes |
| OpenSpec 1.14.3 `validate --archived --strict` | 33 passed, 10 failed on incomplete historical tasks |
| `scripts/spec_index.py --repo . --check` | Generated index matches |
| `scripts/spec_traceability.py --root . --ratchet` | 238 of 252 unique requirement markers covered. The enforced floor passed, with 14 advisory uncovered entries |
| `scripts/specs-validate-negative-control.sh` against the pinned toolchain | Passed. The strict CLI refused the malformed fixture and named its missing purpose |
| `scripts/check_exec_bits.py` | Failed for `tests/test_drift_scan_template.py`, tracked as DG-12 |
| `scripts/spec_state_gate.py --base 479b609 --head fd2c11f` | Failed on missing recognized IDs in three published specs, tracked as DG-01 |
| Scheduled open-item gate | The three GitLab deferral review dates expired. OI-001 through OI-003 track individual owner dispositions |

## Item register

| ID | State | Owner role | Observed gap or evidence | Full OpenSpec |
|---|---|---|---|---|
| `DG-01` | Verified and archived | Spec maintainers | Eight stable IDs restored. The pinned CLI and shared parser now agree on the published inventory. | [Archived DG-01 evidence](../changes/archive/2026-11-25-dg-01-id-and-gate-alignment/evidence.md) |
| `DG-02` | Open | Spec evidence owners | The generated index lists 42 UNPROVEN specs. The ledger has 182 unproven records that need per-requirement evidence or continued explicit disposition. | [dg-02-evidence-ledger-reconciliation](../changes/dg-02-evidence-ledger-reconciliation/proposal.md) |
| `DG-03` | Open | Capability owners | Twelve published specs are UNKNOWN in the generated index. Record the code, tests, ownership, and resulting disposition for each. | [dg-03-unknown-status-disposition](../changes/dg-03-unknown-status-disposition/proposal.md) |
| `DG-04` | Open | Archive maintainers | Ten of 43 archives fail archived strict validation because tasks remain unchecked. Reconcile each original disposition while retaining its historical checkboxes. | [dg-04-archive-task-reconciliation](../changes/dg-04-archive-task-reconciliation/proposal.md) |
| `DG-05` | Open | Fleet enrollment maintainers | Nine fleet app enrollment requirement markers are uncovered by the traceability gate. Verify each existing requirement at the actual enrollment entry point. | [dg-05-fleet-app-enrollment-traceability](../changes/dg-05-fleet-app-enrollment-traceability/proposal.md) |
| `DG-06` | Open | Art workflow and consumer owners | The art evolution requirement is uncovered. Verify the applicable external consumer and record unavailable proof as NOT_RUN. | [dg-06-art-evolution-external-proof](../changes/dg-06-art-evolution-external-proof/proposal.md) |
| `DG-07` | Open | Spec State and repository owners | The enforcement-placement requirement is uncovered. Correlate actual workflow placement and branch protections with the documented guarantees. | [dg-07-spec-state-gate-enforcement](../changes/dg-07-spec-state-gate-enforcement/proposal.md) |
| `DG-08` | Open | GitHub template maintainers | The reusable drift workflow assumes a submodule-provided .devgate checkout while the consumer contract calls for local untracked tooling. | [dg08-consumer-workflow-bootstrap](../changes/dg08-consumer-workflow-bootstrap/proposal.md) |
| `DG-09` | Conditional on adoption | GitLab option and monitor owners | Forge enrollment and template behavior have fixture evidence. Live GitLab runner monitoring remains conditional on operator adoption. | [dg09-gitlab-runner-live-monitoring](../changes/dg09-gitlab-runner-live-monitoring/proposal.md) |
| `DG-10` | Open | Runner distribution maintainers | GitLab templates pin an image digest. The repository review could not resolve its reviewed build source and artifact provenance. | [dg10-gitlab-runner-image-provenance](../changes/dg10-gitlab-runner-image-provenance/proposal.md) |
| `DG-11` | Open | GitLab template maintainers | The GitLab drift mirror assumes recursive submodule checkout and .devgate scripts. Its clean consumer bootstrap requires a verified framework pin. | [dg11-gitlab-mirror-bootstrap](../changes/dg11-gitlab-mirror-bootstrap/proposal.md) |
| `DG-12` | Verified and archived | Framework CI maintainers | The drift-template test runs directly and is tracked at mode 100755. The executable gate passes. | [Archived DG-12 evidence](../changes/archive/2026-11-25-dg12-reconcile-drift-test-executable-mode/evidence.md) |
| `OI-001` | Open owner review | GitLab option owner/operator | The instance selection deferral review date expired. Record a fresh decision and its next authorized trigger. | [review-gitlab-instance-deferral](../changes/review-gitlab-instance-deferral/proposal.md) |
| `OI-002` | Open owner review | GitLab option owner/operator | The live parity deferral review date expired. Reassess the condition against the instance selection decision and separate fixture evidence from live proof. | [review-gitlab-parity-deferral](../changes/review-gitlab-parity-deferral/proposal.md) |
| `OI-003` | Open owner review | GitLab option owner/operator | The restore drill deferral review date expired. Reassess the proof requirement against the approved instance disposition. | [review-gitlab-restore-deferral](../changes/review-gitlab-restore-deferral/proposal.md) |

## Existing active work

- `add-gitlab-forge-support` has eight checked boxes and four unchecked live
  conditions. The owner's existing decision accepts hermetic GitLab support
  as optional, with live proof deferred until adoption. The three new
  disposition packages preserve that decision pending review. [Existing plan](../changes/add-gitlab-forge-support/tasks.md)
- `harden-template-runner-portability` has seven checked boxes and one
  outstanding consumer-runner acceptance item. The change remains active.
  [Existing plan](../changes/harden-template-runner-portability/tasks.md)
- The game-type phase matrix remains the existing DEFERRED item. Its owner
  placed implementation in the consuming repository. [Published spec](../specs/game-type-phase-matrix/spec.md)

## Review procedure

Each new item uses the official spec-driven OpenSpec workflow and the same
1.14.3 version used by AIGGP CI. The proposals include design, normative
scenario deltas with stable IDs, and implementation and evidence tasks.
The item plans stay open at review. Status and strict validation check the
planning artifacts. Delivery verification uses the task-specific entry point,
expected errors, and external evidence where applicable. Archive only after
the task evidence and ledger disposition support closure.
[Official workflow](https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md)

## Review-branch checks

The pinned CLI validates 73 items in the review branch: 56 published specs,
two existing active changes, and 15 new item changes. The 15 new changes
have complete planning artifacts and unchecked acceptance tasks. Peer review
checked their evidence and refined the proposed scenarios, especially the
GitLab heartbeat, signed runner image provenance, and marker-ID contracts.

The traceability ratchet passes with 239 of 268 IDs covered and 29 advisory
entries. The extra covered ID is `spec-fmt-04`, whose negative-control script
and CI invocation were already present. The proposed requirement markers
provide identifiers for later verification. The 10 historic archive failures
remain isolated to DG-04.

The pattern scan passed with 49 non-blocking warnings. The semantic and
silent-success scans passed. Schema health reported SKIPPED because the
checkout has no database configuration.
