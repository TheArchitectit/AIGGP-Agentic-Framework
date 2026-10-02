## ADDED Requirements

### Requirement: discovery before reliance

The lab instance SHALL be documented (version, URL, auth shape, network posture) and its backup SHALL be restore-tested before any repo depends on gates running there.

#### Scenario: undocumented instance

Given an instance without completed discovery, when gate availability is declared, then the declaration SHALL be blocked pending the runbook.

### Requirement: runner standard parity

GitLab runners SHALL meet the same standard as the GitHub fleet: rootless container execution, digest-pinned images, fail-closed behavior.

#### Scenario: tag-pinned image

Given a runner image referenced by mutable tag, when the runner standard check runs, then it SHALL FAIL until digest-pinned.

### Requirement: thin mirrored templates

GitLab CI templates SHALL be includes that invoke the identical gate scripts used by the GitHub templates, for all seven gates that ship in `templates/github-workflows/` (guardrails compliance, secret validation, file size, smoke gate, scheduled drift scan, spec-coherence, specs-validation). The set is the shipped one, counted from that directory; adding or retiring a GitHub template updates this requirement in the same change.

#### Scenario: template divergence

Given a GitLab template embedding gate logic inline rather than invoking the shared script, when reviewed, then it SHALL be rejected.
