## Requirement: bundle-declared categories

Content categories and their actions SHALL be declared in the policy bundle. A category without a declared action set, corpus reference, and failure-mode statement SHALL be invalid.

### Scenario: vague category rejected

Given a bundle adding a category with no corpus or failure modes, when the bundle is validated, then validation SHALL FAIL naming the missing fields.

## Requirement: named classifier per decision

Every filtering decision SHALL record classifier provider, model, version, and runtime where applicable. A decision lacking classifier identity SHALL fail envelope validation.

### Scenario: unnamed model

Given a decision emitted without model version, when the envelope is validated, then it SHALL be rejected.

## Requirement: conservative boundary defaults

At send, commit, and publish boundaries, sub-threshold or errored classification SHALL default to escalate or block per category policy, never silent allow.

### Scenario: classifier error at send

Given the classifier times out while evaluating an outbound message, when mediation decides, then the send SHALL be held for escalation.
