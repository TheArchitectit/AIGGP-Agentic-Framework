## ADDED Requirements

### Requirement: immutable runtime

<!-- id: coh-rt-01 -->

Production invocation MUST reference the service image and plugins by digest.

#### Scenario: tag-only image

- **GIVEN** invocation uses only `latest`
- **WHEN** enforced evaluation begins
- **THEN** it is rejected before assertions run.

### Requirement: launcher-validated isolation

<!-- id: coh-rt-02 -->

The isolation profile MUST be established and verified by the launcher or orchestrator outside the container, not by the container self-reporting. The container MUST run non-root with a read-only root, read-only inputs, bounded scratch space, dropped capabilities, and no host control sockets. A launch configuration granting root, writable input mounts, host sockets, host networking, or forbidden capabilities MUST be rejected by the launcher before evaluation.

#### Scenario: runtime violates isolation requirements

- **GIVEN** a launch configuration grants root, writable inputs, host control sockets, or other forbidden privileges
- **WHEN** the reference launcher validates the launch configuration
- **THEN** the configuration is rejected rather than treated as compliant isolation.

#### Scenario: self-report not trusted

- **GIVEN** a container image that internally claims to be non-root and read-only
- **WHEN** the launcher applies the effective OCI/Podman security context
- **THEN** the enforced context comes from launcher configuration, and a mismatch between claimed and effective context is a launch failure.

### Requirement: default-deny network

<!-- id: coh-rt-03 -->

Network egress MUST be disabled by default.

#### Scenario: approved external registry lookup

- **GIVEN** one assertion needs a registry record
- **WHEN** policy grants a named endpoint and response-capture rule
- **THEN** the lookup runs outside the evaluator as a capture step, its response digest becomes a bound context fact, and replay uses the captured response rather than a live fetch.

#### Scenario: evaluator attempts direct egress

- **GIVEN** an evaluator without a network capability grant attempts a socket connection
- **WHEN** the runtime mediates
- **THEN** the connection is denied and recorded; a required assertion depending on it becomes UNRESOLVED, never SATISFIED.

### Requirement: least-privilege secrets

<!-- id: coh-rt-04 -->

Secrets MUST be injected only for a named capability, MUST NOT be exposed to other evaluators, MUST NOT enter evidence or logs, and SHOULD use short-lived credentials.

#### Scenario: evaluator lacks the named secret capability

- **GIVEN** a secret is granted only to a different named evaluator capability
- **WHEN** an evaluator without that grant executes
- **THEN** it cannot access the secret and the secret is absent from its evidence and logs.

#### Scenario: secret redaction

- **GIVEN** a granted secret value appears in evaluator output or an error message
- **WHEN** evidence and logs are produced
- **THEN** the secret is redacted before sealing; an unredacted secret in sealed evidence is an evidence error.

### Requirement: bounded execution

<!-- id: coh-rt-05 -->

Each evaluator MUST have CPU, memory, time, file, process, and output limits. Limit exhaustion is ERROR, not PASS.

#### Scenario: evaluator exhausts a configured limit

- **GIVEN** an evaluator has explicit resource and output limits
- **WHEN** it exhausts any configured limit
- **THEN** evaluation returns ERROR rather than PASS.

#### Scenario: output overflow

- **GIVEN** an evaluator writes more than its bounded output allowance
- **WHEN** the runtime enforces the limit
- **THEN** execution is terminated, the assertion is UNRESOLVED, and the run is ERROR-class.

### Requirement: built-in evaluators for the initial runtime

<!-- id: coh-rt-06 -->

Until a separately approved plugin sandbox exists (its own ADR), evaluators MUST be bundled, reviewed, deterministic built-ins shipped inside the pinned image by digest. Repository-supplied executable code MUST NOT run as an evaluator. The built-in set MUST run with no network and no secrets by default.

#### Scenario: repository supplies executable evaluator

- **GIVEN** a package or overlay references evaluator code from the subject repository
- **WHEN** the planner resolves evaluators
- **THEN** the reference is rejected as an unapproved evaluator; only allowlisted built-in digests may execute.

### Requirement: writable output handling

<!-- id: coh-rt-07 -->

The only writable filesystem is the bounded scratch volume plus a designated bounded output location. Evidence and results MUST be sealed within scratch and exported atomically; a partially written result or evidence bundle MUST be treated as an error, never as a truncated pass.

#### Scenario: partial output

- **GIVEN** the process is killed while writing the result bundle
- **WHEN** the caller inspects the output location
- **THEN** no complete canonical result is present, the exit status is ERROR-class, and no consumer mistakes partial bytes for a decision.
