# Design

## Context

Mirror checks verify template counts and `@sha256` syntax. All ten mirrors reference `ghcr.io/aiggp/devgate-runner@sha256:4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b`. Repository search found no local build definition or release workflow; external registry existence and provenance were not verified in this offline review.

## Goals / Non-Goals

**Goals:** Trace the digest to reviewed source/build authority and enable network-free consumer preflight.

**Non-Goals:** Claim compromise or artifact absence, disclose credentials, or require live GitLab adoption.

## Decisions

Publish signed provenance binding source repository/revision, build workflow revision, authorized builder identity/permissions, and the artifact subject digest. The offline verifier validates the signature against a checked-in or otherwise locally provisioned approved public trust key and its identity policy, then checks every mirror against the subject digest. Reject wrong digest, wrong signer, missing attestation, and unverifiable signature. DG-10 owns image provenance and digest references; DG-11 owns GitLab job checkout provisioning. Coordinate mirror-file changes so each edit has a single responsibility. Offline signature validation proves a local binding only; it makes no claim that the image was fetched or is currently reachable in a registry.

## Risks / Trade-offs

[Build identity changes] → require reviewed provenance update with digest change; [offline validation does not prove live registry availability] → state that limitation; [trust key/identity policy drifts] → require a reviewed trust-key rotation and provenance update.
