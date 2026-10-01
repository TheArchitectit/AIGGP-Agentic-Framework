## ADDED Requirements

### Requirement: deterministic evaluation

<!-- id: coh-eval-01 -->

The service MUST produce the same canonical result for the same subject, package, policy, evaluator image, evaluation context, and declared capabilities.

#### Scenario: repeated execution

- **GIVEN** identical immutable inputs and identical evaluation context
- **WHEN** the evaluation runs repeatedly on supported hosts within the declared execution profile
- **THEN** canonical result bytes and evidence manifest digest are identical.

#### Scenario: evaluator reads time

- **GIVEN** an evaluator attempts to use undeclared wall-clock time
- **WHEN** it executes
- **THEN** the capability is denied or the evaluation returns ERROR; the check cannot pass using that value.

### Requirement: complete required assertion execution

<!-- id: coh-eval-02 -->

Every required assertion MUST end as SATISFIED, VIOLATED, or UNRESOLVED in the assertion results ledger. It MUST NOT disappear from the result.

#### Scenario: plugin crash

- **GIVEN** a required evaluator crashes
- **WHEN** the decision is computed
- **THEN** its assertions are UNRESOLVED with a stable reason code and enforced policy blocks.

#### Scenario: repository attempts to skip assertion

- **GIVEN** central policy requires assertion `X`
- **WHEN** a repository overlay omits or disables `X`
- **THEN** planning fails or `X` remains required.

#### Scenario: dependency-blocked assertion

- **GIVEN** an assertion depends on an assertion that ended UNRESOLVED or VIOLATED
- **WHEN** the planner schedules execution
- **THEN** the dependent assertion is recorded as UNRESOLVED with reason `dependency-blocked` and is never counted as satisfied or silently omitted.

### Requirement: assertion results ledger

<!-- id: coh-eval-03 -->

A completed evaluation MUST emit an `assertion_results` ledger with exactly one entry per planned required assertion, recording assertion ID, version, outcome, reason code, and enforcement. Findings are zero-or-many per assertion and MUST NOT substitute for the ledger.

#### Scenario: ledger accounting

- **GIVEN** a planned graph of N required assertions
- **WHEN** evaluation completes
- **THEN** the ledger contains exactly N entries, and the summary counts equal the ledger tallies by outcome.

#### Scenario: assertion with no findings

- **GIVEN** an assertion ended VIOLATED
- **WHEN** its evaluator produced no finding objects
- **THEN** the ledger entry remains VIOLATED with reason `violation-without-finding-detail`, and the missing detail is itself an evidence error for enforced assertions.

### Requirement: semantic assertion traceability

<!-- id: coh-eval-04 -->

Every assertion MUST trace to one or more normative requirements and every normative requirement marked testable MUST trace to at least one assertion.

#### Scenario: orphan requirement

- **GIVEN** a normative requirement is marked testable
- **WHEN** it has no assertion
- **THEN** traceability is violated and enforced policy may block.

#### Scenario: assertion without requirement

- **GIVEN** an assertion declares no normative requirement reference
- **WHEN** the package is validated
- **THEN** the package is rejected as structurally invalid.

### Requirement: underlying truth is preserved

<!-- id: coh-eval-05 -->

Enforcement policy MUST NOT change the assertion outcome.

#### Scenario: advisory violation

- **GIVEN** an assertion is violated during Stage 1
- **WHEN** policy is applied
- **THEN** the finding remains VIOLATED with advisory enforcement and the top-level decision is ADVISORY.

### Requirement: evaluators execute only declared inputs

<!-- id: coh-eval-06 -->

An evaluator MUST receive only the subject locations, package content, captured facts, and environment values its assertion declares. Evaluators MUST NOT read sibling evaluators' inputs, ambient environment, or undeclared filesystem paths.

#### Scenario: undeclared path access

- **GIVEN** an evaluator requests a filesystem path not declared by its assertion
- **WHEN** the runtime mediates the access
- **THEN** the access is denied and recorded; if the assertion is required, its outcome is UNRESOLVED, never SATISFIED.
