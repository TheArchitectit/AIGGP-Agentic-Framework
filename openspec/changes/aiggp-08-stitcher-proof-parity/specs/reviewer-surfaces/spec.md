## Requirement: SARIF validity

Findings SHALL be emittable as schema-valid SARIF with rule, severity, location, and evidence reference.

### Scenario: SARIF round-trip

Given emitted SARIF, when loaded by a standard viewer, then all findings SHALL render with locations and evidence links.

## Requirement: local-CI parity

Pre-commit execution SHALL use the same images and scripts as CI and SHALL produce identical verdicts for the same change.

### Scenario: divergent local verdict

Given a change passing pre-commit but failing CI, when the parity harness investigates, then the cause SHALL be classified as a defect and the parity fixture SHALL fail until fixed.

## Requirement: evidence-linked review comments

Forge review comments SHALL reference the finding's evidence record. A comment without an evidence link SHALL NOT be posted.

### Scenario: comment with evidence

Given a blocking finding on a pull request, when comments post, then each SHALL carry rule, severity, and a link to the envelope.
