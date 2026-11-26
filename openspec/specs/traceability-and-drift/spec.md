# traceability-and-drift Specification

## Purpose
The stitcher's three proofs: commits and tasks map to each other in both directions, a spec verdict cites a deterministic evidence reference, and a behavior change with no spec update in range is reverse drift.

## Requirements

### Requirement: bidirectional task traceability
<!-- id: trace-01 -->

Every spec task SHALL map to implementing commits, and every commit SHALL map to covering spec tasks or be reported as uncovered. Both directions SHALL appear in evidence.

#### Scenario: orphan commit

Given a commit touching behavior with no covering task, when traceability runs, then it SHALL be reported as uncovered with file evidence.

#### Scenario: orphan task

Given a task marked complete with no implementing commit, when traceability runs, then it SHALL be reported as unimplemented.

### Requirement: spec-to-diff review
<!-- id: trace-02 -->

A change SHALL be evaluated against the requirements it declares, with a verdict per requirement. A change declaring no requirements SHALL be flagged.

#### Scenario: undeclared change

Given a diff with no declared requirement coverage, when review runs, then the change SHALL be flagged and SHALL NOT receive a clean review verdict.

### Requirement: reverse drift detection
<!-- id: trace-03 -->

Changes altering behavior covered by no spec requirement SHALL be findings at the severity the bundle declares.

#### Scenario: silent behavior change

Given a diff changing gated behavior with no spec update, when reverse-drift runs, then it SHALL produce a finding naming the behavior and files.
