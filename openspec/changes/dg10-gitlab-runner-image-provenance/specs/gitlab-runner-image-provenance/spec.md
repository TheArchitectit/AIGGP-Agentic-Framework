# Spec Delta

## Purpose

Defines traceable provenance for runner container images used by GitLab CI mirrors so consumers can review their source and build authority.

## ADDED Requirements

### Requirement: GitLab runner image provenance is cryptographically bound
<!-- id: glf-image-prov-01 -->
A GitLab CI runner image SHALL be considered verified only when signed provenance binds its immutable digest to the reviewed source revision and authorized build workflow identity, and the signature verifies against the approved trust key and identity policy.

#### Scenario: signed provenance matches the pinned digest
- **WHEN** offline verification checks a mirror digest, provenance subject, approved source/build identity, and valid signature
- **THEN** it reports provenance verified without claiming a registry pull or live image availability

#### Scenario: signer or trust key is not approved
- **WHEN** provenance is signed by an identity outside the approved policy or cannot be verified with the approved key
- **THEN** the image is not reported as verified and the signer/trust failure is identified

### Requirement: Offline preflight rejects unverifiable image references
<!-- id: glf-image-prov-02 -->
Offline preflight SHALL reject a missing provenance record or digest mismatch and SHALL report unverifiable local provenance as unverified; it SHALL NOT claim that the image was fetched or is reachable in a live registry.

#### Scenario: digest does not match provenance
- **WHEN** a mirror image reference has a digest different from its signed provenance subject
- **THEN** preflight fails with a digest-binding mismatch without claiming the image is malicious or absent

#### Scenario: provenance is missing or unverifiable offline
- **WHEN** preflight cannot verify signed provenance using local approved trust material
- **THEN** it reports the reference unverified and does not pass based only on digest syntax
