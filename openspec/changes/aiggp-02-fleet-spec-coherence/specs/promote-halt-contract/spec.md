## Requirement: uniform promote/halt verdict

The service SHALL expose a promote/halt verdict usable by code pipelines and the AI 3D design pipeline identically, expressed as an AIGGP verdict with evidence references.

### Scenario: 3D candidate passes

Given a 3D asset candidate meeting its spec assertions, when the pipeline requests evaluation, then it SHALL receive PROMOTE with the envelope reference.

### Scenario: repair changes the candidate

Given a repaired candidate whose content changed, when re-evaluated, then the verdict SHALL be computed on the new digest, never inherited from the prior candidate.

## Requirement: no implicit trust from upstream

A passing upstream stage SHALL NOT confer trust on downstream stages; each stage SHALL evaluate its own subject digest.
