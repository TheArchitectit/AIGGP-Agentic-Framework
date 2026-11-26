# Bind adopter promotion evidence to immutable artifacts

## Context

DevGate provides scoped checks and non-authorizing evidence. Adopters need a verified contract linking evidence, immutable delivery artifacts and runtime readback across eligible execution lanes.

## Decisions

Reuse the evaluator result and subject identity defined by the [existing evidence and attestation contract](../../specs/evidence-and-attestation/spec.md). The new verification boundary is the adopter's promotion handoff, including selection and runtime readback. Require matching artifact identity and owning gate outcomes in any permitted runner lane. Preserve distinct verified stage evidence, external release approval and runtime action authority. An adopting environment specifies source and deployment context.

## Risk and verification

A healthy run can refer to another source tree, evaluator, digest or target. Link each of them and test wrong revision, stale or missing report, conflicting digest, missing selection authority and a later diverging deployment.

## Rollout

Review the scenario matrix, exercise it with an isolated configuration, and record exact source and artifact identities before enabling the supported profile or recording acceptance.
