## Requirement: identical gate behavior across forges

Every gate SHALL produce identical findings for identical repository content regardless of forge. Findings SHALL match on gate, rule, severity, and file evidence.

### Scenario: seeded corpus parity

Given the seeded-failure corpus pushed to both forges, when all gates run, then the finding sets SHALL be identical; any difference SHALL fail the drill and block release.

## Requirement: forge-neutral gate logic

Gate scripts SHALL contain no forge-conditional behavior. Forge differences SHALL be confined to the adapter and templates.

### Scenario: forge branch in gate code

Given a gate script containing forge-conditional logic, when reviewed or scanned, then it SHALL be flagged as a parity defect.

## Requirement: uniform evidence

Envelopes from both forges SHALL validate against the same AIGGP-00 schema, with forge identity recorded as metadata.

### Scenario: GitLab envelope validation

Given an envelope emitted from a GitLab run, when the verifier validates it, then it SHALL pass schema validation and carry forge identity.
