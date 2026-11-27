# package-resolution sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Resolve a frozen package inventory, classify normative files and verify each expected digest. Compare an accepted closure with a declared but unavailable import. Start at [tests/test_hub_coherence_normative.py](../../../tests/test_hub_coherence_normative.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-pkg-01`](../../specs/package-resolution/spec.md#requirement-explicit-package-resolution) explicit package resolution | explicit immutable package / missing package / moving reference |
| [`coh-pkg-02`](../../specs/package-resolution/spec.md#requirement-package-structural-validity) package structural validity | contradictory duplicate ID / identical duplicate ID |
| [`coh-pkg-03`](../../specs/package-resolution/spec.md#requirement-normative-boundary) normative boundary | narrative note changes |
| [`coh-pkg-04`](../../specs/package-resolution/spec.md#requirement-frozen-import-closure) frozen import closure | import digest mismatch / import cycle |
| [`coh-pkg-05`](../../specs/package-resolution/spec.md#requirement-authenticated-normative-inventory) authenticated normative inventory | requirement hidden as informative |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-085, DG02-U-086, DG02-U-087, DG02-U-088, DG02-U-089. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-package-release-rule-gaps](../../changes/qualify-dg02-package-release-rule-gaps/sprint-plan.md).

[Published specification](../../specs/package-resolution/spec.md) and [sprint dispatch](../../SPRINTS.md).
