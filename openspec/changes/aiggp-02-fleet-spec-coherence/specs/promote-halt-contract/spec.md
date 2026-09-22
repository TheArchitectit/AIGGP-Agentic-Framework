## ADDED Requirements

### Requirement: uniform promote/halt verdict

The service SHALL expose a promote/halt verdict usable by code pipelines and the AI 3D design pipeline identically, expressed as an AIGGP verdict with evidence references.

#### Scenario: 3D candidate passes

Given a 3D asset candidate meeting its spec assertions, when the pipeline requests evaluation, then it SHALL receive PROMOTE with the envelope reference.

#### Scenario: repair changes the candidate

Given a repaired candidate whose content changed, when re-evaluated, then the verdict SHALL be computed on the new digest, never inherited from the prior candidate.

### Requirement: no implicit trust from upstream

A passing upstream stage SHALL NOT confer trust on downstream stages; each stage SHALL evaluate its own subject digest.

#### Scenario: upstream pass does not transfer

Given an upstream stage whose PROMOTE verdict covers a specific subject digest, when a downstream stage evaluates content whose digest differs from that envelope subject, then the downstream evaluation SHALL run against its own digest and SHALL NOT reuse the upstream verdict, because the envelope binds the verdict to the subject it covered, not to the pipeline position that produced it.
