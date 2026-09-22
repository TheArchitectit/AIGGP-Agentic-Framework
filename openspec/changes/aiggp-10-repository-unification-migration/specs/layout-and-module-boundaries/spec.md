## ADDED Requirements

### Requirement: canonical layout

The terminal tree SHALL expose modules/policy, modules/devgate, kernel, schemas, bundles, conformance, integrations, docs/generated, and tools/migration with documented ownership and public/private boundaries.

#### Scenario: forbidden root ambiguity

Given executable policy or DevGate code remaining at undocumented root paths after migration, when layout validation runs, then it SHALL fail and name each unowned path.

### Requirement: no circular module authority

The kernel owns verdict and evidence contracts. Policy and DevGate modules emit or consume those contracts but SHALL NOT each define competing canonical versions. Cross-module calls SHALL pass through declared interfaces.

#### Scenario: duplicate verdict enum

Given separate policy and DevGate verdict enums that disagree on EMPTY or ERROR, when schema validation runs, then the build SHALL fail.

### Requirement: generated documentation source

Guardrail documentation SHALL be derived from the shipped policy bundle and SHALL be reproducible from its digest. Hand-edited generated copies in consuming repositories SHALL fail drift validation.

#### Scenario: copied guardrail Markdown

Given a consuming repository with a modified generated guardrail document that does not match the bundle renderer, when the coherence gate runs, then it SHALL fail with bundle and output digests.
