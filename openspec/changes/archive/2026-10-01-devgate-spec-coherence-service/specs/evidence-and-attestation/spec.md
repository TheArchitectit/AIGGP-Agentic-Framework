## ADDED Requirements

### Requirement: acyclic sealing order

<!-- id: coh-ev-01 -->

Sealing MUST proceed in one acyclic order: immutable inputs → evidence objects → evidence manifest → canonical decision → detached attestation → transport envelope. The canonical decision MUST NOT contain its own attestation's digest or signature. The attestation is a detached object binding the decision digest and the evidence manifest digest; consumers obtain it alongside the decision, never from inside it.

#### Scenario: re-signing leaves decision unchanged

- **GIVEN** a sealed canonical decision
- **WHEN** a new attestation is produced over the same decision and evidence digests (new key, new signature, new timestamp)
- **THEN** the canonical decision bytes are unchanged and both attestations verify against the same decision digest.

#### Scenario: attestation field absent from decision

- **GIVEN** any canonical result
- **WHEN** its schema is validated
- **THEN** no field inside the canonical decision carries attestation signature bytes or an attestation digest; the transport envelope may reference the detached attestation location.

### Requirement: complete evidence manifest

<!-- id: coh-ev-02 -->

Every result MUST identify all evidence objects by digest, media type, assertion ID, and retention classification. The evidence manifest MUST NOT hash itself or any downstream object (decision, attestation, envelope).

#### Scenario: evidence write failure

- **GIVEN** an enforced finding requires evidence
- **WHEN** local sealing of the evidence bundle fails
- **THEN** the evaluation returns ERROR (exit 33) and blocks promotion.

#### Scenario: retryable remote upload after seal

- **GIVEN** a locally sealed and digested evidence bundle whose remote upload fails
- **WHEN** the caller retries the upload later
- **THEN** the canonical decision and evidence manifest digest are unchanged, and policy states explicitly whether confirmed remote durability is a promotion prerequisite for this stage.

### Requirement: reproducible findings

<!-- id: coh-ev-03 -->

A finding MUST contain enough information to rerun the assertion against the immutable inputs without depending on the original host: assertion ID and version, evaluator identity and digest, declared input digests, parameters, and the finding key derivation.

#### Scenario: reproduce without the original runner

- **GIVEN** a finding and its evidence bundle identify immutable inputs and the approved evaluator
- **WHEN** an operator reruns the assertion on a supported replacement runner
- **THEN** the finding is reproducible without depending on the original host.

### Requirement: authorized input retention

<!-- id: coh-ev-04 -->

Where reproduction requires the exact subject or package bytes, an authorized retention channel MUST preserve the immutable input bundle separately from public evidence. Public evidence carries digests and minimum-disclosure excerpts only; retrieval of retained inputs MUST require an authorization distinct from evidence read access, and retention expiry MUST invalidate cached-result reuse for the affected identities.

#### Scenario: evidence outlives retention

- **GIVEN** a cached signed result whose retained input bundle has expired
- **WHEN** a consumer attempts cache-based promotion
- **THEN** the cache entry is invalid and a full reevaluation against re-supplied inputs is required.

### Requirement: attestation binding

<!-- id: coh-ev-05 -->

From Stage 2 onward, every promotion-authorizing result MUST carry a signed detached attestation binding the subject, package, policy, evaluation-context, evaluator image, canonical decision, and evidence manifest digests. Signing MAY be optional only in Stage 0–1 observation runs that are labeled non-promotion-authorizing. Verification MUST check signer identity against the current approved signer set and MUST fail closed on expired or revoked signers.

#### Scenario: result substituted

- **GIVEN** any bound digest changes
- **WHEN** attestation verification runs
- **THEN** verification fails.

#### Scenario: revoked signer

- **GIVEN** an attestation signed by a key revoked in the current control-plane signer set
- **WHEN** verification runs at promotion time
- **THEN** verification fails even though the signature is mathematically valid.

### Requirement: minimal disclosure

<!-- id: coh-ev-06 -->

Evidence MUST store only the content needed to prove the finding. Secrets and unrelated source content MUST be redacted or represented by digests.

#### Scenario: source contains unrelated sensitive content

- **GIVEN** an assertion input contains secrets or source content unrelated to the finding
- **WHEN** evidence is produced
- **THEN** that content is redacted or represented by digests rather than disclosed.

### Requirement: approval records are detached

<!-- id: coh-ev-07 -->

A package approval record MUST be detached from the normative bytes it approves: approval identity binds the package digest, approving authority, repository scope, and validity window without including the approval record in the digested content. Self-referential approval (an `approved_revision` field inside the approved bytes) is invalid.

#### Scenario: approval binds exact revision

- **GIVEN** an approval for package digest D1
- **WHEN** the package is edited to produce digest D2
- **THEN** the approval does not bind D2 and an enforced evaluation rejects the unapproved revision.
