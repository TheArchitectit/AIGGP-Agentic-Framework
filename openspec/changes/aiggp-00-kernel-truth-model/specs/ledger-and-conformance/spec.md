## ADDED Requirements

### Requirement: append-only verifiable ledger

Verdicts, waivers, and bundle publications SHALL be recorded in a hash-chained append-only ledger. The standalone verifier SHALL confirm integrity offline and SHALL detect removal, reordering, or modification of entries.

#### Scenario: deleted entry

Given a ledger with one entry removed, when the verifier runs, then it SHALL report the exact break in the chain.

### Requirement: public conformance profiles

The kernel SHALL publish conformance profiles per capability, with valid fixtures and invalid counterexamples, and a runner reporting pass/fail per claimed capability.

#### Scenario: module overclaims

Given a module claiming a capability it fails, when the kit runs, then the report SHALL list that capability as non-conformant and the module SHALL NOT receive its badge.

### Requirement: deterministic renderer inputs

The kernel SHALL define the data contract from which deployment documents are generated, such that the same bundle plus ledger regenerates the identical document.

#### Scenario: hand-edited output detected

Given a generated document edited by hand afterward, when regeneration is compared, then the difference SHALL be detected and reported.
