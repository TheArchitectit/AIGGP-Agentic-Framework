# Sprint plan — DG-05 fleet enrollment traceability

**Scope:** finish sealed, requirement-specific evidence for the existing enrollment behavior.
Tasks 1.1–1.2 and 2.1/2.3/2.4 are recorded; local reconciliation tests passed 18/18. Live enrollment remains NOT_RUN.

## Sequence

### S1 — intake/baseline

- Recheck the nine-ID traceability map, reviewed source revision, test receipt, and explicit limits in the local checkpoint.
- Task 2.2 is the sole unchecked task: no configured signer set or signed bundle bound to this commit/test result is supplied.

### S2 — implementation or evidence collection

- Luna prepares requirement-specific claims and links to the enforcing path, behavioral assertion, exact test/run identity, commit, and expected bundle digest.
- Validate the sealed bundle with the existing validator. Bind any attestation to the bundle digest and commit using only an approved configured signer set; never synthesize signer trust.
- If signing or a required result is unavailable, record NOT_RUN for that evidence and leave task 2.2 open.

### S3 — independent qualification

- A distinct audit session verifies each claim against `fleet-app-01`–`09`, validates the bundle/attestation and signer identity, and checks for credential leakage.
- Confirm that hermetic fixtures are labeled local and that workflow/live fleet runs remain NOT_RUN unless signed real-run evidence is reviewed.
- Stop on absent signer policy, mismatched digest/commit, secret material, or any claim broader than its observed test.

### S4 — integration/closeout

- Lead reconciles independent findings, reruns evidence validation and traceability, and signs off only the sealed scope.
- Do not change enrollment credentials or runtime behavior. A live fleet result remains outside this plan unless the responsible operator supplies an authorized, signed run.

## Bounded roles

- Lead: design of acceptance boundary, review, and sign-off. Luna: collect and seal local receipts. A separate audit session validates them from the artifact.
- Configured signer owner supplies approved trust material and attestation when available; no individual signer is invented.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Evidence](evidence.md)
- [Local enrollment checkpoint](local-enrollment-verification.md) · [Traceability map](traceability-map.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
