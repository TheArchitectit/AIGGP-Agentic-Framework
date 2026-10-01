## ADDED Requirements

### Requirement: digest and canonicalization profile

<!-- id: coh-id-01 -->

All content identity MUST use SHA-256 over explicitly defined byte sequences. Canonical JSON MUST use a restricted RFC 8785 profile: sorted object keys, no duplicate keys, UTF-8, integers within int64, and a single defined number format. File payloads MUST be hashed as raw bytes; normalization applies to manifest representation only and MUST NOT alter the bytes a file digest commits to.

#### Scenario: golden vectors

- **GIVEN** a committed set of golden canonicalization vectors
- **WHEN** any implementation version computes their digests
- **THEN** results match the vectors byte-for-byte, and any deviation fails the compatibility suite.

#### Scenario: line-ending change is a content change

- **GIVEN** a subject file's line endings change from LF to CRLF
- **WHEN** the subject manifest is computed
- **THEN** the file digest changes and the subject digest changes; representation-level normalization never masks it.

### Requirement: subject manifest

<!-- id: coh-id-02 -->

The subject manifest MUST address every considered file by normalized relative path and raw-byte digest, and MUST record explicit policy outcomes for symlinks, submodules, generated outputs, large files, and exclusions. Path traversal (`..`, absolute, backslash forms), Unicode normalization collisions, and case collisions on case-insensitive targets MUST be rejected as invalid input, not silently rewritten.

#### Scenario: path escape

- **GIVEN** the subject tree contains a symlink or path resolving outside the declared root
- **WHEN** the manifest is built under the default policy
- **THEN** the input is rejected with exit code 30 and the offending entry named.

#### Scenario: input mutated during evaluation

- **GIVEN** a subject file changes after its digest was recorded but before an evaluator reads it
- **WHEN** the runtime verifies read-time digests
- **THEN** the evaluation returns ERROR (exit 32) rather than mixing pre- and post-mutation content.

### Requirement: package normative digest

<!-- id: coh-id-03 -->

The package digest used for conformance MUST cover exactly the normalized manifest and the normative file closure, computed under the canonicalization profile. Informative content MUST be digestible separately as an archive digest.

#### Scenario: normative edit changes identity

- **GIVEN** one normative file changes by a single byte
- **WHEN** identity is recomputed
- **THEN** the package digest changes and prior approvals no longer bind.

### Requirement: image and platform identity

<!-- id: coh-id-04 -->

The evaluation context MUST distinguish the image index digest (if any), the executed platform image manifest digest, and the execution profile label. The canonical result MUST carry identity fields whose values are stable across the equivalence class the launch acceptance promises: byte-equivalence within one execution profile, and semantic equivalence across profiles when declared.

#### Scenario: cross-architecture replay

- **GIVEN** the same subject, package, policy, and context evaluated on two supported architectures under a declared semantic-equivalence profile
- **THEN** decisions, findings, and ledger agree, and the result records each platform's executed image manifest digest.

#### Scenario: undeclared profile

- **GIVEN** a runner whose execution profile is not in the declared supported set
- **WHEN** evaluation is attempted
- **THEN** the invocation is rejected before assertions run (exit 30), and it is never reported as PASS.

### Requirement: domain-separated digests

<!-- id: coh-id-05 -->

Distinct artifact kinds (subject manifest, package, policy bundle, evaluation context, evidence manifest, canonical decision) MUST use domain-separated, versioned digest inputs so identical bytes in different roles cannot collide into the same identity.

#### Scenario: role confusion attempt

- **GIVEN** bytes crafted so a policy file equals a subject file
- **WHEN** digests are computed
- **THEN** the role-tagged digests differ and no cross-role substitution verifies.
