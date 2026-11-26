# Qualify consumer delivery evidence

## Why

Several DevGate templates provision tooling on hosted runners. The evaluator
workflow and DevGate's own CI also have a documented private runner lane.
A consumer needs one verified delivery path that distinguishes runner
placement, required checks, release evidence, and deployment approval.

## What Changes

- Define a reference consumer workflow that runs eligible gates on hosted
  Linux against a fixture with public inputs and immutable tool pins.
- Qualify each additional runner path against the same required checks before
  documenting it as supported for that consumer.
- Bind a passing check set and approval reference to an exact candidate,
  artifact digest, and recovery reference. Verify those bindings before
  promotion.
- Document enforcement on the protected delivery path separately from
  post-push findings and source repository release publication.

## Impact

- Affected capability: `consumer-delivery-evidence`.
- Affected surfaces: consumer workflows, onboarding, fixture validation,
  evidence export, and consumer promotion verification.
- The active test-runner, runner portability, forge adoption, and upstream
  release packages retain their scope. Consumers own organization rules,
  signing or attestation policy, approvals, registries, and production access.
