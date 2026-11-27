# Sprint plan — approved main release

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), [rehearsal evidence](evidence.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: design the evidence record, reconcile review findings, and sign off; only the authorized release owner publishes.
- Luna: prepare metadata after approval and collect the exact source, tag, release, and gate receipts.
- Independent auditor: a separate session reviews source and receipts first-hand; it does not rely on Luna's narrative.
- Accountable owner: release owner selects version and notes, approves the candidate, and authorizes publication.

## S1 — intake and baseline

- Reuse completed tasks 1.1–1.2: the captured coverage failure and isolated positive/negative fixture replay in `evidence.md`.
- For task 2.1, obtain the release owner's recorded version, notes, and candidate commit approval before editing release metadata.
- Record current `VERSION`, changelog, workflow expectations, tag target, and relevant CI head; preserve existing tag identities.
- Exit when approval is attributable to an owner and the candidate SHA and version are fixed; otherwise keep 2.1–3.2 blocked.

## S2 — metadata and evidence

- For task 2.2, prepare only the approved version and changelog edits; run the applicable prepublication gates on that candidate.
- Keep metadata review separate from publication; capture command output, inputs, head SHA, and gate conclusions.
- For task 3.1, after explicit release-owner publication, read back the annotated tag target and GitHub Release and compare both with the approved commit.
- Exit with matching metadata, source, annotated tag, and release receipts, or a named discrepancy with no closure claim.

## S3 — independent qualification

- Independent auditor checks approval authority, candidate binding, changelog/version diff, prepublication results, tag annotation/target, and release readback.
- Auditor records PASS/FAIL/NOT_RUN per conjunct and verifies the evidence references resolve at the reviewed revision.
- Lead reconciles findings; any missing authorization or mismatched target blocks acceptance.

## S4 — integration and closeout

- Task 3.2: lead updates the relevant OpenSpec and audit records only from accepted evidence; run strict validation and traceability.
- Recheck the release coverage workflow at the final reviewed head and archive only when task evidence supports it.
- Handoff: approval record, reviewed metadata diff, exact source SHA, gate receipts, tag and release URLs, auditor verdict, and final validation output.
- Boundary: no version choice, release, publication, or deployment is inferred from the earlier rehearsal; the release owner controls publication.
