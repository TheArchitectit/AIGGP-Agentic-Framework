# Tasks

See the [hosted pilot and enforcing owners](hosted-pilot.md) for source revisions, job receipts and the scope of this qualification.

## 1. Define the reference consumer

- [x] 1.1 Select a small reference application, check set, eligible hosted runner,
  and exact tooling revisions. Document requirements inherited from active
  bootstrap, template portability, and test-runner work.
- [x] 1.2 Map each gate and deployment decision to its enforcing surface and
  owner. Record optional runner and forge paths with their activation criteria.

## 2. Verify the full delivery path

- [x] 2.1 Run the clean consumer on the eligible hosted runner. Record exact
  source/tool revisions and successful checks with a negative control.
- [ ] 2.2 Verify promotion evidence against a synthetic artifact digest,
  authorized fixture approval, and recovery reference. Reject wrong-revision,
  wrong-artifact, skipped, and failed-check fixtures.
- [x] 2.3 Demonstrate required check enforcement on a disposable protected
  promotion path. Keep post-push observations visible as observations.

## 3. Publish only verified support

- [x] 3.1 Update onboarding with the exercised workflow and remaining
  environment-specific setup. Any additional runner path needs its own receipt.
- [ ] 3.2 Run strict OpenSpec, traceability, and independent acceptance review.
  Archive when tracked evidence and tasks support closure.

## 4. Verify deployed artifact identity

- [ ] 4.1 Replay exact and mismatched destination and digest controls using an isolated deployment readback fixture. Require the existing subject attestation and detached approval before recording verified deployment.
