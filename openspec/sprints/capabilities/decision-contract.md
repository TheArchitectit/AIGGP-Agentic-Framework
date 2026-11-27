# decision-contract sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Use the decision precedence cases to compare canonical decision, envelope fields, exit code and stable finding order for the same subject. Start at [tests/test_hub_coherence_decision.py](../../../tests/test_hub_coherence_decision.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-dec-01`](../../specs/decision-contract/spec.md#requirement-single-decision-precedence-matrix) single decision precedence matrix | simultaneous crash and violation / exit code and result disagree |
| [`coh-dec-02`](../../specs/decision-contract/spec.md#requirement-structured-error-envelopes) structured error envelopes | invalid input before digests exist / unsupported protocol version |
| [`coh-dec-03`](../../specs/decision-contract/spec.md#requirement-canonical-versus-envelope-separation) canonical versus envelope separation | envelope differs, decision identical |
| [`coh-dec-04`](../../specs/decision-contract/spec.md#requirement-exit-code-contract) exit code contract | full exit-code sweep / ERROR in enforced mode |
| [`coh-dec-05`](../../specs/decision-contract/spec.md#requirement-finding-sort-order-and-stability) finding sort order and stability | unordered inputs |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-039, DG02-U-040, DG02-U-041, DG02-U-042, DG02-U-043. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/decision-contract/spec.md) and [sprint dispatch](../../SPRINTS.md).
