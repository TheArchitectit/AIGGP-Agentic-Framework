# Spec Delta

## Purpose

Provides exact, reviewable evidence for each fleet App enrollment contract without treating a local fixture as proof of live fleet operation.

## ADDED Requirements

### Requirement: Enrollment requirements have exact implementation and test traceability
<!-- id: fleet-app-10 -->
The enrollment verification record SHALL map each `fleet-app-01` through `fleet-app-09` requirement to its enforcing entry point or workflow step, a behavioral test with the asserted outcome, and the CI invocation that runs it. Static contract checks SHALL be labeled as such and SHALL NOT substitute for behavior tests.

#### Scenario: requirement has no enforcing site
- **WHEN** a requirement has only a source marker or a test that inspects text without exercising the behavior
- **THEN** the record identifies the absent enforcement/test evidence and does not report the requirement as code-proven

#### Scenario: hermetic fixture is the evidence
- **WHEN** an enrollment behavior passes against the in-memory API fixture
- **THEN** the record labels the result hermetic and does not claim a live GitHub workflow or fleet run

### Requirement: Enrollment proof outputs are sealed and credential-safe
<!-- id: fleet-app-11 -->
A terminal evidence record for an enrollment requirement SHALL reference a bundle accepted by the existing evidence validator and a signed attestation bound to that bundle digest and commit, accepted by the existing attestation verifier and configured signer set. It SHALL identify test outcomes and contain no private key or token. If signing or live-only evidence is unavailable, that proof SHALL be marked NOT_RUN and SHALL NOT be inferred from hermetic tests.

#### Scenario: verified enrollment evidence
- **WHEN** a requirement is reported exercised
- **THEN** its sealed bundle validates, the attestation verifies against the configured signer set and binds the bundle digest and commit, the passing test is named, and no credential material is present

#### Scenario: no live signed output
- **WHEN** only local fixture evidence exists for a live fleet outcome
- **THEN** that outcome remains NOT_RUN and the record states that no signed live output was reviewed; it is not labeled EXERCISED
