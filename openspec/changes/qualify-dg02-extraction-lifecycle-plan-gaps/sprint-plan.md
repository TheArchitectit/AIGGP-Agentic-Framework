# Sprint plan — DG-02 extraction, lifecycle, and planning evidence gaps

**Status:** active qualification routing. Batch 013 covers DG02-U-145 through DG02-U-156; all 182 baseline requirements remain UNPROVEN. The next DG-02 review starts at DG02-U-157.

## Scope and entry points

Coordinate the evidence follow-up for these capabilities:

- Fleet manager extraction: `repo-005-01..03` (`DG02-U-145..147`). Start with [the extraction rehearsal](../../../fleet-manager/scripts/extraction_rehearsal.py) and [its recorded review](../dg-02-evidence-ledger-reconciliation/batches/batch-013/README.md).
- Fleet manager job lifecycle: `fleet-008-01..05` (`DG02-U-148..152`). The current tests exercise synthetic state and supplied cleanup values; they do not observe runner processes or host disposal.
- Fleet manager plan/apply: `fleet-002-01..04` (`DG02-U-153..156`). Current tests exercise deterministic plans, authorization, retry, and audit behavior using supplied state.

Use the native CLI and Python model tests for this change. A change to session startup also needs a carrier-specific run. [Adapter assignments](../../SPRINTS.md#session-adapter-matrix). The [DG-02 review](../dg-02-evidence-ledger-reconciliation/README.md) records the outstanding proof for each row.

## Observed controls to qualify

1. **Node-absent extraction rehearsal.** A controlled run with Node unavailable collected 2,195 core tests and passed Phase A, then printed `node absent — guardrails half skipped (stated, not silently passed)` and still ended `OK`. Preserve the visible skip in reporting, and require a nonzero exit when the required scan cannot run. With Node present the scan passed. Retain both receipts.
2. **Plan construction accepts an inconsistent summary.** The planner computed a change from two free slots to one. A caller replaced those values with 20 and 19 and the public plan document accepted them under the original ID. Replay both cases and test every supported constructor and apply path.
3. **Lifecycle evidence is synthetic.** Current lifecycle tests model transitions and caller-supplied disposal/timestamps. Qualification needs accountable evidence for host runner launch, cleanup, and observation before claiming real runner lifecycle behavior.
4. **Provenance remains open.** Batch 013 records current behavior but does not supply accepted historical row citations or expected-digest requirement bundles. Keep every affected row UNPROVEN until the ledger evidence contract and independent review accept the required proof.

## Sequence and roles

| Step | Role | Work product |
| --- | --- | --- |
| S1 — owner | Fleet Manager maintainer and CI owner | Map each requirement to its owner and expected receipt. Specify the nonzero exit for an incomplete rehearsal and rejection or recomputation of an inconsistent plan summary. |
| S2 — writer | Luna writer | Implement tasks 1–3 and exercise normal and refusal paths with synthetic fixtures. |
| S2 — evidence | Luna evidence collector | Record checkout, commands, inputs, expected and observed results. Bind each receipt to its row and record missing provenance. |
| S3 — independent audit | Separate session | Replay each control at a recorded revision; verify stdout, exit status, test identities, and artifact digests. Confirm that simulated reports are not described as host observations. |
| S4 — lead and accountable owner | Lead with maintainers | Reconcile results and provenance. Update the row-bound evidence and lifecycle state only when every proof conjunct is satisfied. Preserve UNPROVEN otherwise. |

## Acceptance record

For each affected requirement, record the exact checkout SHA, command, environment prerequisites (including Node availability), fixture/input digest, expected and observed output, exit status, test node IDs, host versus simulation boundary, and artifact digest. Treat a skipped scan as `SKIPPED` with its reason, never as a green scan. Treat unavailable host evidence as `NOT_RUN` with the owner or dependency stated. Do not modify the immutable baseline roster or infer historical provenance from the current passing tree.

## Cross-links

- [Extraction capability plan](../../sprints/capabilities/fleet-manager-extraction.md)
- [Job lifecycle capability plan](../../sprints/capabilities/fleet-manager-job-lifecycle.md)
- [Plan/apply capability plan](../../sprints/capabilities/fleet-manager-plan.md)
- [DG-02 batch index](../dg-02-evidence-ledger-reconciliation/README.md)
- [Global sprint dispatch](../../SPRINTS.md)
