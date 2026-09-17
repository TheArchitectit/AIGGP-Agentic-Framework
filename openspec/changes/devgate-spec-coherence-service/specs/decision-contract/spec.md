## ADDED Requirements

### Requirement: single decision precedence matrix

<!-- id: coh-dec-01 -->

The service MUST apply one published total ordering over error and outcome classes when computing the top-level decision and exit code. ERROR-class conditions (invalid input, untrusted policy, evaluator/resource failure, evidence or signing failure) take precedence over FAIL-class conditions within the same run; FAIL takes precedence over ADVISORY; ADVISORY takes precedence over PASS. Every exit code MUST map to exactly one decision state, and every decision state to exactly one exit code.

#### Scenario: simultaneous crash and violation

- **GIVEN** one required evaluator crashed (UNRESOLVED) and another produced an enforced VIOLATED finding
- **WHEN** the decision is computed
- **THEN** the matrix yields a single deterministic decision and exit code, recorded with both condition classes visible in the result, and repeated runs of the same inputs yield the same decision.

#### Scenario: exit code and result disagree

- **GIVEN** a caller observes exit code 20 but the result file parses as PASS, or the result file is missing or malformed
- **WHEN** the caller applies the contract
- **THEN** the caller treats the run as ERROR and MUST NOT promote; disagreement is never resolved in favor of the more permissive signal.

### Requirement: structured error envelopes

<!-- id: coh-dec-02 -->

When evaluation cannot produce a trustworthy result, the service MUST emit a structured error envelope with a stable error class, reason code, and the identities it could verify. Identity fields that could not be computed MUST be explicitly null or absent, never fabricated. An error envelope is never a PASS and never carries a decision of PASS or ADVISORY.

#### Scenario: invalid input before digests exist

- **GIVEN** the subject root does not exist or fails manifest validation
- **WHEN** the error envelope is emitted
- **THEN** `subject_digest` is null or absent, the error class is `invalid-input`, and no invented digest appears anywhere in the envelope.

#### Scenario: unsupported protocol version

- **GIVEN** a request declares an `api_version` the service does not support
- **WHEN** the invocation adapter validates the request
- **THEN** the service exits 40 with an envelope naming the supported versions, before any resolver runs.

### Requirement: canonical versus envelope separation

<!-- id: coh-dec-03 -->

The canonical result MUST exclude runtime duration, host name, wall-clock timestamps, worker identities, and nondeterministic log excerpts. Those belong to a noncanonical run envelope that is never an input to the decision, the attestation binding, or replay equivalence.

#### Scenario: envelope differs, decision identical

- **GIVEN** two runs on different hosts at different times with identical immutable inputs and context
- **WHEN** results are compared
- **THEN** canonical result bytes are identical while run envelopes may differ, and envelope differences never change either decision.

### Requirement: exit code contract

<!-- id: coh-dec-04 -->

The service MUST use the published exit codes: 0 PASS, 10 ADVISORY, 20 FAIL, 30 invalid input or package, 31 policy resolution error, 32 evaluator error or incomplete execution, 33 evidence or attestation error, 40 unsupported protocol version. Callers MUST use both the exit code and the parsed result. Exit codes 30–33 and 40 are ERROR-class: in enforced mode they block promotion, and in inventory (Stage 0) mode they MUST NOT be reported as a coherence authorization for the subject.

#### Scenario: full exit-code sweep

- **GIVEN** a conformance fixture suite with one fixture per exit code
- **WHEN** each fixture is evaluated
- **THEN** each produces its documented exit code, matching decision state, and a parseable result or error envelope.

#### Scenario: ERROR in enforced mode

- **GIVEN** an enforced-stage evaluation that exits 32
- **WHEN** a promotion consumer reads the result
- **THEN** promotion is blocked and the blocked reason cites the error class, not a violation count.

### Requirement: finding sort order and stability

<!-- id: coh-dec-05 -->

Findings MUST be sorted by assertion ID, then subject location under a defined path ordering, then a stable finding key derived from deterministic content (never from hashes of timestamps, pointers, or map iteration order). Two runs over identical inputs MUST produce byte-identical findings arrays.

#### Scenario: unordered inputs

- **GIVEN** subject files traverse in different OS-dependent orders across two hosts
- **WHEN** findings are canonicalized
- **THEN** the sorted findings arrays are byte-identical.
