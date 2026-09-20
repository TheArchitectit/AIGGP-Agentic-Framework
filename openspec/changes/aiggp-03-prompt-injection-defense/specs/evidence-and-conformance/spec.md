## Requirement: per-decision evidence

Every classification and mediation decision SHALL emit an AIGGP envelope carrying subject identity, classifier identity and version, bundle digest, and raw classification output.

### Scenario: classifier swap invalidates claims

Given a module release that changes classifier version without re-running the corpus, when conformance status is queried, then prior pass claims SHALL be reported as stale.

## Requirement: adversarial conformance corpus

A versioned public corpus SHALL cover at minimum: direct injection, instruction-in-content, encoded/obfuscated payloads, multi-turn setup, authority impersonation, and exfiltration lures. Verified status SHALL require meeting the declared pass bar per category on the pinned corpus version.

### Scenario: category miss published

Given a corpus category below the bar, when the conformance report is generated, then the category SHALL be listed as failing with fixtures named.

## Requirement: benign-corpus false-positive budget

The module SHALL declare and meet a false-positive budget on a benign corpus. Regression beyond budget SHALL block release.

### Scenario: budget breach

Given a release candidate exceeding the budget, when the release gate runs, then it SHALL FAIL with the measured rate.
