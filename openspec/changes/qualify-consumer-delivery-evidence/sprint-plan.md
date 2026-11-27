# Sprint plan — consumer delivery evidence

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), [hosted pilot](hosted-pilot.md), [lab handoff](lab-handoff.md), and [receipts](receipts/).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: own the acceptance design, reconcile the pilot and sign off; do not publish consumer-owned checks.
- Luna: build/collect only approved synthetic fixtures and prepare machine-readable receipts.
- Independent auditor: separate session checks raw run, App, approval, and destination evidence.
- Accountable owners: reference app owner; consumer CI owner; AI02 Lab CI operator; repository administrator; consumer release, deployment, and destination owners.

## S1 — intake and baseline

- Accept tasks 1.1–1.2, 2.1, 2.3, and 3.1 as recorded, using their existing owner map and receipts.
- Keep the pilot pinned to approved AIGGP commit `bdbd450e0275a05b319ce29d83f761e8ed552e69`; do not substitute the handoff's older `80d18b0f0f4e080c9e47d4e534cc2c56c29308ca` tool SHA.
- Treat the five hosted consumer cases as separate from the UCS03 framework baseline; UCS03 receipts do not qualify the consumer runner path.
- Resolve tasks 2.2/4.1 owners and approval interface before proposing positive promotion/deployment behavior; current pilot lacks deployment approval verifier and destination readback.
- Exit with the selected candidate, artifact digest, recovery reference, approved fixture authority, and isolated destination fixture spec recorded.

## S2 — promotion/readback fixtures

- Task 2.2: bind required checks, exact source/candidate, synthetic artifact digest, fixture approval, and recovery reference; reject wrong revision/artifact, skipped, or failed checks.
- Task 4.1: exercise destination and digest match/mismatch/unavailable results through an isolated readback fixture; require subject attestation and detached approval.
- Keep approval verification independent of subject attestation and keep expected and observed artifact digests distinct.
- Exit only when positive and negative cases produce attributable receipts; if the owner interface is unavailable, preserve both tasks as open with the blocker.

## S3 — independent qualification

- Auditor verifies the existing hosted receipts at their exact run and merge SHAs, then separately checks promotion and readback fixtures.
- Auditor checks actual App decisions, job identities, approval scope/validity, destination identity, and failure reasons; no post-push observation is treated as enforcement.
- Lead resolves any difference between the receipt, the candidate actually tested, and the proposed support statement.

## S4 — integration and closeout

- Task 3.2: run strict OpenSpec, traceability, and independent acceptance after review; archive only if evidence and task states support it.
- Update onboarding only for the exercised hosted path; keep other runners/forges conditional on separate qualification.
- Handoff: approved pilot SHA, native hosted and branch-protection receipts, promotion/readback fixture receipts, accountable owner approvals, auditor verdict, and remaining limits.
- Boundary: synthetic evidence does not authorize a real release or deployment; no private production access is assumed.
