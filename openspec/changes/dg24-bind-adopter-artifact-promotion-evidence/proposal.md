# Bind adopter promotion evidence to immutable artifacts

## Why

DevGate provides scoped checks and non-authorizing evidence. Existing evidence and attestation can identify evaluated subjects. The adopting deployment still needs a verified handoff from those results to the selected artifact and target readback.

## What changes

Define a redacted handoff containing immutable source, requirement, evaluated policy, required checks, evaluator and image identities. Validate artifact and intended-target match, approval reference and deployment readback. Report missing and inconsistent proof explicitly.

## Capabilities

Add the `adopter-artifact-promotion-evidence` capability.

## Impact

The supported change applies to the repository-owned deployment or verification paths identified in the design. Authoritative adopter acceptance remains with the relevant service or release owner.
