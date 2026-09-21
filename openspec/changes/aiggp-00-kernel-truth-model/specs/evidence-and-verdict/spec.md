## ADDED Requirements

### Requirement: signed evidence envelope

Every module result SHALL be wrapped in a signed evidence envelope carrying subject digests, bundle digest, module identity and version, claimed capability, raw result, and provenance chain. An envelope failing schema, digest, or signature validation SHALL be rejected.

#### Scenario: substituted result

Given an envelope whose raw result was replaced after signing, when the verifier runs, then it SHALL reject the envelope and name the failing check.

### Requirement: verdict algebra integrity

Aggregation SHALL follow the kernel-versioned algebra: EMPTY and ERROR never aggregate to PASS; SKIP requires a reason code; FAIL dominates PASS.

#### Scenario: zero discovery

Given a module run that discovered zero applicable items and returned EMPTY, when results aggregate, then the aggregate SHALL NOT be PASS regardless of other results.

#### Scenario: skip without reason

Given a SKIP result with no reason code, when the envelope is validated, then validation SHALL fail.

### Requirement: waiver validity

A waiver SHALL be scoped, owned, reasoned, and expiring, and SHALL exist as a ledger entry. An expired or out-of-scope waiver SHALL be treated as absent.

#### Scenario: expired waiver

Given a FAIL result and a waiver whose expiry passed, when aggregation runs, then the result SHALL remain FAIL.

#### Scenario: wildcard scope rejected

Given a waiver scoped to all subjects, when validated, then it SHALL be rejected.
