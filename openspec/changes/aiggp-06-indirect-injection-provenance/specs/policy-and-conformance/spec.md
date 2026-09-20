## Requirement: class-aware policy

The bundle SHALL be able to express policy on provenance class, including: no destructive action SHALL be justified solely by third-party or unverifiable content.

### Scenario: destructive action from web content

Given a delete action justified only by fetched third-party content, when policy above is active, then mediation SHALL block and escalate.

## Requirement: ancestry reconstruction

Given any mediated action, the full provenance ancestry of its justifying content SHALL be reconstructable from the ledger.

### Scenario: audit query

Given an action from a week ago, when an auditor queries its ancestry, then the result SHALL list every content input with origin class and digest.
