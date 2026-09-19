# Spec Delta: harden-security-boundaries

## ADDED Requirements

### Requirement: Repository-supplied paths are contained
<!-- id: coh-sec-01 -->
Every path originating from repository-supplied content (package inventory
entries, assertion selector paths, captured-fact ids) SHALL be validated for
containment under its declared root before any read. Traversal, absolute,
escaping-symlink, and NUL-bearing paths SHALL be rejected as invalid input
(exit 30 class) without reading the target, and the rejection reason SHALL
name the offending path.

#### Scenario: inventory traversal
- **WHEN** a package manifest's inventory names a path escaping the package root
- **THEN** resolution fails as invalid input and no bytes outside the root are read

#### Scenario: selector exfiltration
- **WHEN** an assertion's file selector resolves outside the subject tree
- **THEN** the assertion is UNRESOLVED with a stable containment reason and no
  content from outside the subject tree appears in findings or sealed evidence

### Requirement: Hub request and shutdown contracts
<!-- id: mon-sec-01 -->
The hub SHALL enforce a configurable maximum request body size on JSON
endpoints and SHALL reject oversized, negative, or malformed lengths with a
4xx JSON envelope. The hub SHALL shut down cleanly (exit 0) on SIGTERM/SIGINT
without waiting for the next inbound request. Enrollment name-uniqueness
SHALL be decided atomically with token consumption under the registry lock.

#### Scenario: oversized body
- **WHEN** a request declares a Content-Length above the cap
- **THEN** the hub responds with an error envelope and does not buffer the body

#### Scenario: signal shutdown
- **WHEN** the hub receives SIGTERM while idle
- **THEN** the process exits 0 promptly without requiring another request

#### Scenario: concurrent duplicate enrollment
- **WHEN** two enrollments with the same runner_name race
- **THEN** exactly one succeeds and the other receives already_enrolled

### Requirement: Tokens are not stored or logged in plaintext
<!-- id: mon-sec-02 -->
Heartbeat token verifiers SHALL be stored hashed (keyed or salted) at rest;
revocation SHALL remove the stored verifier; enrollment tooling SHALL NOT
print issued token material to stdout or CI logs; hub responses carrying
token material SHALL be written only to the 0600 env file. Verification
remains constant-time.

#### Scenario: volume read
- **WHEN** the registry file is read off the hub volume
- **THEN** no usable heartbeat token value is present

#### Scenario: enroll output
- **WHEN** runner-enroll.sh completes
- **THEN** its stdout contains no token substring from the hub response

### Requirement: Template actions and images are immutably referenced
<!-- id: ci-sec-01 -->
Shipped workflow templates SHALL reference external actions by commit SHA and
container images by digest (with the human-readable version recorded adjacent);
runner-monitor service templates SHALL include a liveness HEALTHCHECK where the
service exposes a health endpoint; the documented secrets drop-in mechanism
SHALL be a single canonical form that the shipped unit files actually parse.

#### Scenario: template audit
- **WHEN** a consumer audits templates/github-workflows and templates/runner*
- **THEN** no mutable action tag or :latest image reference is present

#### Scenario: secrets drop-in parses
- **WHEN** an operator follows the runner docs' secrets step verbatim
- **THEN** the resulting drop-in is consumed by the shipped quadlet as written
