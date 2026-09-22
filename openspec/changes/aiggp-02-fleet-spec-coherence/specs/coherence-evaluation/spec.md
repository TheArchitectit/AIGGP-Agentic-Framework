## ADDED Requirements

### Requirement: deterministic evaluation

Evaluation SHALL be a pure function of digested inputs: repo revision, spec package, policy package, evaluator image. Reading wall-clock time, network state, or ambient environment to influence a verdict SHALL fail conformance.

#### Scenario: repeated execution

Given identical inputs, when evaluation runs three times, then all verdicts and assertion results SHALL be identical.

#### Scenario: evaluator reads time

Given an assertion plugin whose result depends on the current time, when conformance runs, then the plugin SHALL be rejected.

### Requirement: complete required assertion execution

Every assertion required by the policy SHALL execute or the run SHALL report ERROR. A plugin crash SHALL NOT downgrade a requirement to SKIP.

#### Scenario: plugin crash

Given an assertion plugin that crashes mid-run, when evaluation completes, then the run SHALL report ERROR naming the assertion, and SHALL NOT be green.

### Requirement: semantic assertion traceability

Every normative requirement in the spec package SHALL map to at least one executed assertion. An unmapped requirement SHALL fail coherence.

#### Scenario: orphan requirement

Given a spec with a requirement no assertion covers, when evaluation runs, then the verdict SHALL be FAIL naming the orphan requirement ID.
