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

[Current requirement audit](2026-11-25-aiggp-current-audit.md) traces the reviewed draft and subsequent archive evidence.

| ID | State | Owner role | Observed gap or evidence | Full OpenSpec |
|---|---|---|---|---|
| `DG-01` | Verified and archived | Spec maintainers | Eight stable IDs restored. The pinned CLI and shared parser now agree on the published inventory. | [Archived DG-01 evidence](../changes/archive/2026-11-25-dg-01-id-and-gate-alignment/evidence.md) |
| `DG-02` | Open | Spec evidence owners | The generated index lists 42 UNPROVEN specs. The ledger has 182 unproven records that need per-requirement evidence or continued explicit disposition. | [dg-02-evidence-ledger-reconciliation](../changes/dg-02-evidence-ledger-reconciliation/proposal.md) |
| `DG-03` | Open | Capability owners | Twelve published specs are UNKNOWN in the generated index. Record the code, tests, ownership, and resulting disposition for each. | [dg-03-unknown-status-disposition](../changes/dg-03-unknown-status-disposition/proposal.md) |
| `DG-04` | Open | Archive maintainers | Ten of 43 archives fail archived strict validation because tasks remain unchecked. Reconcile each original disposition while retaining its historical checkboxes. | [dg-04-archive-task-reconciliation](../changes/dg-04-archive-task-reconciliation/proposal.md) |
| `DG-05` | Open | Fleet enrollment maintainers | Nine fleet app enrollment requirement markers are uncovered by the traceability gate. Verify each existing requirement at the actual enrollment entry point. | [dg-05-fleet-app-enrollment-traceability](../changes/dg-05-fleet-app-enrollment-traceability/proposal.md) |
| `DG-06` | Open | Art workflow and consumer owners | The art evolution requirement is uncovered. Verify the applicable external consumer and record unavailable proof as NOT_RUN. | [dg-06-art-evolution-external-proof](../changes/dg-06-art-evolution-external-proof/proposal.md) |
| `DG-07` | Open | Spec State and repository owners | The enforcement-placement requirement is uncovered. Correlate actual workflow placement and branch protections with the documented guarantees. | [dg-07-spec-state-gate-enforcement](../changes/dg-07-spec-state-gate-enforcement/proposal.md) |
| `DG-08` | Open | GitHub template maintainers | Drift, specs, and text integrity use submodule checkout to supply ignored `.devgate/` tools. The expanded proposal covers all three reusable GitHub workflows. | [dg08-consumer-workflow-bootstrap](../changes/dg08-consumer-workflow-bootstrap/proposal.md) |
| `DG-09` | Conditional on adoption | GitLab option and monitor owners | Forge enrollment and template behavior have fixture evidence. Live GitLab runner monitoring remains conditional on operator adoption. | [dg09-gitlab-runner-live-monitoring](../changes/dg09-gitlab-runner-live-monitoring/proposal.md) |
| `DG-10` | Open | Runner distribution maintainers | GitLab templates pin an image digest. The repository review could not resolve its reviewed build source and artifact provenance. | [dg10-gitlab-runner-image-provenance](../changes/dg10-gitlab-runner-image-provenance/proposal.md) |
| `DG-11` | Verified and archived | GitLab template maintainers | Ten mirrors share a reviewed full-commit DevGate bootstrap with passing hermetic controls. Live GitLab runner acceptance applies upon adoption. | [Archived evidence](../changes/archive/2026-11-25-dg11-gitlab-mirror-bootstrap/evidence.md) |
| `DG-12` | Verified and archived | Framework CI maintainers | The drift-template test runs directly and is tracked at mode 100755. The executable gate passes. | [Archived DG-12 evidence](../changes/archive/2026-11-25-dg12-reconcile-drift-test-executable-mode/evidence.md) |
| `DG-13` | Verified and archived | Framework CI maintainers | The exact hosted checksum step passed for all 160 canonical entries. | [Archived evidence](../changes/archive/2026-11-25-dg-13-release-checksum-manifest/evidence.md) |
| `DG-14` | Verified and archived | Open-item gate maintainers | Exact-scope exclusions passed independent controls and the hosted detector at ac61e20. | [Archived evidence](../changes/archive/2026-11-25-dg-14-evidence-claim-scan-scope/evidence.md) |
| `DG-15` | Verified and archived | GitLab parity maintainers | The pinned five-case drill passed on Windows and Linux, including a quoted Linux fixture path. | [Archived evidence](../changes/archive/2026-11-25-dg-15-windows-parity-seed-path/evidence.md) |
| `DG-16` | Verified and archived | Framework CI maintainers | The verifier fails malformed SHA-256 and duplicate records, and checks the current 160-record inventory. | [Archived evidence](../changes/archive/2026-11-25-dg-16-checksum-manifest-record-validation/evidence.md) |
| `DG-17` | Verified and archived | Framework CI maintainers | Checksum inventory preserves Unicode names and rejects unsupported names and duplicate index stages. The exact hosted gate verified all 160 entries. | [OpenSpec change](../changes/archive/2026-11-25-dg17-checksum-unicode-path-inventory/proposal.md) |
| `DG-18` | Open | Spec traceability maintainers | The shared marker scanner omits the actual GitLab bootstrap source marker in YAML. | [OpenSpec change](../changes/dg18-yaml-workflow-source-markers/proposal.md) |
| `OI-001` | Disposition archived | GitLab option owner/operator | The owner specified feature support. Live instance enrollment requires explicit adoption. | [Archived evidence](../changes/archive/2026-11-25-review-gitlab-instance-deferral/evidence.md) |
| `OI-002` | Disposition archived | GitLab option owner/operator | Hermetic parity passed. Live parity requires explicit adoption. | [Archived evidence](../changes/archive/2026-11-25-review-gitlab-parity-deferral/evidence.md) |
| `OI-003` | Disposition archived | GitLab option owner/operator | The real GitLab backup and restore check requires explicit adoption and applies before gates depend on that instance. | [Archived evidence](../changes/archive/2026-11-25-review-gitlab-restore-deferral/evidence.md) |

## Existing active work

- `add-gitlab-forge-support` has nine checked boxes and four unchecked live
  conditions. The owner's existing decision accepts hermetic GitLab support
  as optional, with live proof deferred until adoption. The three
  archived dispositions record the confirmed adoption trigger. [Existing plan](../changes/add-gitlab-forge-support/tasks.md)
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

The pinned CLI validated 73 items in the initial review branch: 56 published specs,
two existing active changes, and 15 new item changes. The 15 review changes
began with complete planning artifacts and unchecked acceptance tasks. Peer review
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
