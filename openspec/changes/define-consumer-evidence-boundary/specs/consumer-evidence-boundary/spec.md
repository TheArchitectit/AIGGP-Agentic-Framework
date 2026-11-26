# Consumer Evidence Boundary

## Purpose

Define the consuming application's responsibility for invoking required checks, validating their evidence, and separately authorizing effects. Evaluator output is evidence about a declared immutable subject and execution context; it is not runtime authority, a grant of effect, or proof that every client surface was intercepted.

## ADDED Requirements

### Requirement: Evaluator evidence does not authorize consumer effects
<!-- id: coh-consumer-evidence-01 -->
An evaluator or guardrail check SHALL return evidence under its supported contract and SHALL NOT itself authorize a consumer effect. The consuming application SHALL make the effect decision under its own trusted policy after validating required evidence. A valid evaluator PASS, signature, or attestation alone SHALL NOT grant authority to deploy, invoke a tool, or write to an external system.

#### Scenario: a passing check is not an effect grant

- **GIVEN** a valid PASS result for an immutable subject
- **WHEN** the consumer has no independent authorization for the requested effect
- **THEN** the consumer does not perform or authorize that effect
- **AND** the evaluator result remains evidence only

#### Scenario: consumer authorizes a permitted effect

- **GIVEN** a required result validates for the exact subject and trusted context
- **AND** the consumer's independent policy authorizes the requested effect
- **WHEN** the consumer evaluates the operation
- **THEN** only the consumer authorization path may permit the effect

### Requirement: Required evidence is validated against the exact subject and provenance
<!-- id: coh-consumer-evidence-02 -->
Before a mandatory effect, the consumer SHALL invoke or verify every required check using the supported versioned contracts. It SHALL validate that each result is supported, complete, and bound to the exact immutable subject, source provenance, and declared evaluator identity being considered. The consumer SHALL NOT accept a result for a different subject, provenance, unsupported contract version, or unverifiable binding.

#### Scenario: matching evidence is accepted for consideration

- **GIVEN** every required result uses a supported version and matches the immutable subject, provenance, and declared evaluator
- **WHEN** the consumer validates the evidence
- **THEN** the evidence may be considered by consumer policy
- **AND** no effect is authorized until that policy makes its independent decision

#### Scenario: evidence subject or version differs

- **GIVEN** a result names a different subject or provenance, has an unsupported version, or has an unverifiable binding
- **WHEN** the consumer validates it for a mandatory operation
- **THEN** validation fails and the result cannot authorize the operation

### Requirement: Mandatory checks fail closed and advisory checks remain non-authorizing
<!-- id: coh-consumer-evidence-03 -->
The consumer SHALL obtain the advisory or mandatory classification from its trusted policy, not from evaluator output or subject-controlled input. In a mandatory path, failed, missing, skipped, stale, unavailable, or mismatched required evidence SHALL prevent the effect. In an advisory path, the consumer MAY report the evidence or its uncertainty, but SHALL NOT treat advisory output as a mandatory pass or an effect grant.

#### Scenario: required evidence is unavailable

- **GIVEN** trusted consumer policy requires a check before an effect
- **WHEN** the check is unavailable, skipped, missing, or produces an invalid result
- **THEN** the consumer denies or withholds the effect and records the unresolved check

#### Scenario: advisory check is unavailable

- **GIVEN** trusted consumer policy marks a check advisory
- **WHEN** that check is unavailable or returns a finding
- **THEN** the consumer reports the advisory state and does not represent it as a mandatory pass or authorization

### Requirement: Tenant and tool context comes from trusted consumer state
<!-- id: coh-consumer-evidence-04 -->
The consumer SHALL derive tenant and tool context from its own trusted, versioned authority and SHALL pass only opaque references required by supported contracts. Repository content, prompts, agent claims, ambient environment, and evaluator output SHALL NOT select or broaden trusted tenant, tool, policy, or effect context. Secrets SHALL NOT be included in evidence or context references.

#### Scenario: untrusted content attempts to choose tenant or tool

- **GIVEN** a prompt, repository file, or agent output proposes a tenant or tool reference that differs from consumer-controlled state
- **WHEN** the consumer constructs evaluation context
- **THEN** the untrusted value is rejected or ignored and cannot widen the consumer's grants

#### Scenario: a secret is present in input context

- **GIVEN** the consumer has a secret needed to perform an operation
- **WHEN** it constructs references or evidence for evaluation
- **THEN** it uses an opaque reference where supported and does not disclose the secret value

### Requirement: Coverage claims name the checked consumer surfaces
<!-- id: coh-consumer-evidence-05 -->
A consumer integration SHALL identify the entry points and effect classes that invoke its required checks. An entry point without verified integration SHALL remain declared unsupported or unverified. A consumer integration SHALL NOT claim universal client interception or coverage beyond the surfaces its evidence demonstrates.

#### Scenario: an effect route is not integrated

- **GIVEN** an effect route does not invoke or validate the declared required checks
- **WHEN** the consumer reports its integration coverage
- **THEN** that route is identified as unsupported or unverified and is not counted as covered

#### Scenario: coverage is reported

- **GIVEN** checks are integrated at a named set of consumer entry points
- **WHEN** coverage is described
- **THEN** the description is limited to those evidenced entry points and does not claim universal interception

### Requirement: Consumer evidence is minimized
<!-- id: coh-consumer-evidence-06 -->
Consumer evidence SHALL use existing supported redaction and digest conventions. It SHALL NOT include raw prompts, credentials, or unrelated subject content as proof. Any separately authorized retention of exact subject bytes remains governed by the existing retention policy and SHALL remain separate from consumer evidence.

#### Scenario: sensitive content is present

- **GIVEN** a test subject includes a synthetic secret or prompt text unrelated to a finding
- **WHEN** consumer evidence is produced
- **THEN** it contains neither the raw secret nor unrelated prompt content
- **AND** it uses an existing digest or redaction convention

### Requirement: Consumer acceptance tests have no external effects
<!-- id: coh-consumer-evidence-07 -->
Acceptance tests SHALL exercise allow, deny, unavailable, and mismatch outcomes with hermetic fixtures and a fake effect sink. The tests SHALL verify that no external system write occurs.

#### Scenario: required outcome matrix runs locally

- **GIVEN** hermetic fixtures for allowed, denied, unavailable, and mismatched evidence
- **WHEN** the consumer acceptance suite runs with a fake effect sink
- **THEN** it checks each outcome and confirms that the fixtures caused no external system write
