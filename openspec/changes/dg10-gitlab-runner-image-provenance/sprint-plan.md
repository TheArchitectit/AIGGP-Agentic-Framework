# Sprint plan — DG-10 GitLab runner image provenance

**Scope:** establish authoritative signed provenance and offline verification for the runner image; adjacent digest/signature tests are not DG-10 proof.
Tasks 1.1–1.4 remain open. The offline baseline finds no authoritative builder workflow, provenance statement, approved trust policy, or DG-10 preflight.

## Sequence

### S1 — intake/baseline

- Reconfirm the pinned mirror digest and the exact gaps in `offline-verification-evidence.md`; keep registry pulls and live availability outside this acceptance claim.
- Task 1.1 needs the authoritative image source, builder workflow/revision, restricted build identity, permissions, and independently reviewable source.

### S2 — implementation or evidence collection (owner inputs first)

- Only after the source/build and trust owners identify the canonical build and approve a key/identity policy, task 1.2 can bind source revision, workflow/builder identities and permissions to the image digest in signed provenance.
- Implement task 1.3 as an offline preflight over local provenance, approved trust material, and every declared GitLab mirror. Test missing metadata, invalid signature, wrong signer, digest mismatch, and mirror drift without registry access.
- For task 1.4 coordinate file ownership with DG-11 before touching shared mirror/bootstrap files; reconcile release docs and state the offline-check limits.

### S3 — independent qualification

- A separate audit session verifies the signed subject digest and builder identity policy, replays positive and wrong-digest/wrong-signer cases, and confirms mirror checks fail closed offline.
- Stop if authority, key approval, source binding, or DG-11 ownership is unresolved. Do not use generic OAP attestations or local image-cycle tests as substitutes.

### S4 — integration/closeout

- Lead reviews ownership boundaries, release wording, test receipts, and exact candidate revision; rerun focused gates before sign-off.
- No live image fetch, registry availability, or production image-content claim is made unless separately authorized and evidenced.

## Bounded roles

- Lead: choose the acceptance boundary, coordinate DG-11, review, and sign off. Luna: inspect source/build artifacts and implement/collect offline fixtures after trust inputs exist.
- The source/build owner supplies authoritative records; the trust owner approves verification identity. A distinct audit session independently verifies the receipt.
- No session-start/manifest interface changes are proposed; carrier matrix is not applicable.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Offline verification baseline](offline-verification-evidence.md)
- [DG-11 mirror/bootstrap archive](../archive/2026-11-25-dg11-gitlab-mirror-bootstrap/proposal.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
