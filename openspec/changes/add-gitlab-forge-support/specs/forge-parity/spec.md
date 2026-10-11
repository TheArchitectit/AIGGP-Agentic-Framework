# forge-parity Delta

## ADDED Requirements

### Requirement: Gate behavior SHALL be identical across forges <!-- id: GLF-01 -->

Every gate SHALL produce identical findings for identical repository content
regardless of which forge runs it. Findings SHALL match on gate, rule,
severity, and file evidence. A finding that differs by forge alone is a
parity defect.

#### Scenario: seeded corpus parity

GIVEN the seeded-failure corpus pushed to both GitHub and GitLab
WHEN all gates run on each forge
THEN the finding sets SHALL be identical (gate, rule, severity, file evidence)
AND any difference SHALL fail the parity drill and block release.

#### Scenario: parity drill is permanent

GIVEN the parity drill has passed once
WHEN CI runs thereafter
THEN the drill SHALL run again on a pinned corpus version
AND its removal SHALL require an explicit superseding change.

### Requirement: Gate logic SHALL be forge-neutral <!-- id: GLF-02 -->

Gate scripts SHALL contain no forge-conditional behavior. All forge
differences SHALL be confined to the adapter (`hub/forge/`) and the CI
template families. The gate scripts invoked by GitLab templates SHALL be
byte-identical to those the GitHub templates invoke.

#### Scenario: forge branch in gate code

GIVEN a gate script containing forge-conditional logic (a branch on
`forge == "gitlab"` or equivalent)
WHEN reviewed or scanned
THEN it SHALL be flagged as a parity defect and rejected.

#### Scenario: identical script invocation

GIVEN a GitHub template and its GitLab mirror for the same gate
WHEN the two launchers are compared
THEN both SHALL invoke the same script path with the same arguments
AND neither SHALL embed gate logic inline.

### Requirement: Evidence SHALL be uniform across forges <!-- id: GLF-03 -->

Evidence from both forges SHALL validate against the same shipped
sealed-bundle format (`hub/coherence/evidence.py`, checked by
`scripts/evidence-validate.py`), with forge identity recorded as a metadata
field on the bundle. Forge identity SHALL never alter a verdict.

#### Scenario: GitLab evidence validation

GIVEN an evidence bundle emitted from a GitLab run
WHEN `scripts/evidence-validate.py` validates it
THEN it SHALL pass against the same schema as GitHub evidence
AND carry a `forge` metadata field naming GitLab and the instance.

#### Scenario: no forge-trusted shortcut

GIVEN evidence arriving from any forge
WHEN it is admitted to the coherence record
THEN it SHALL pass the same validation as every other bundle
AND no forge SHALL be trusted to self-certify its own evidence.