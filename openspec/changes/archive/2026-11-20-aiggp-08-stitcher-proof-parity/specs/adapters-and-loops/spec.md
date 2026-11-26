## ADDED Requirements

### Requirement: identity-preserving ingestion

External tool results SHALL be ingested with tool identity, version, and raw output reference. They SHALL NOT be re-issued as AIGGP-originated findings.

#### Scenario: adapter output

Given an ingested external scanner result, when evidence is queried, then it SHALL show the original tool identity and version.

### Requirement: agent-loop verdict contract

Coding-agent loops SHALL consume promote/halt verdicts through the AIGGP-02 contract, keyed to subject digests. Loop-produced changes SHALL re-enter as unverified subjects.

#### Scenario: loop self-certification attempt

Given a loop presenting its own prior output as verified input, when evaluated, then it SHALL be treated as a new unverified change.
