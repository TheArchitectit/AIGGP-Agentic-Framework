# spec-gap-audit Delta

## ADDED Requirements

### Requirement: Gap scanning SHALL be mechanical and evidence-pointed <!-- id: SGA-01 -->

The gap scanner SHALL inventory capability anchors and OpenSpec coverage
only, and every emitted row SHALL carry at least one `file:line` evidence
pointer into source that was read. A row without an evidence pointer SHALL
NOT be emitted, and the scanner SHALL NOT author or alter requirement
prose as part of the scan itself.

#### Scenario: a misdescribed anchor is dropped, not printed

GIVEN an inventory pass that suspects a signal is unemitted
WHEN the scanner cannot locate a `file:line` anchor proving the claim
THEN the claim is absent from the report rather than hedged in it
AND no "declared but never emitted" row without an anchor survives to the
human table (the production_ready / merge_sparkle false claims of the
testbed first pass).

### Requirement: Generated drafts SHALL be born unreviewed and excluded from coverage <!-- id: SGA-02 -->

`--draft` output SHALL mark every generated requirement unreviewed, and
coverage floors, ratchet counts, and traceability numerators SHALL treat
unreviewed drafts as if the requirement did not exist. Only a review step
flipping the marker admits a draft to the count.

#### Scenario: scaffolding cannot inflate its own success metric

GIVEN a repo where every requirement is a fresh unreviewed draft
WHEN the coverage floor is computed
THEN the floor sees zero covered requirements
AND the ratchet does not move (review merges, generation proposes).

### Requirement: The gap report SHALL order worst-tracked first and separate claims from gaps <!-- id: SGA-03 -->

The report SHALL rank repositories' and capabilities' gaps by tracking
quality ascending, and SHALL place `CLAIMED-BUT-ABSENT` rows in their own
named section, never unioned with missing-spec rows, never promotable to a
requirement or scaffold without a code pointer supplied by a human.

#### Scenario: a doc claim with no code stays a lead, not a spec

GIVEN a sprint note claiming a hero-merge energy surcharge with no reader
in source
WHEN the scanner runs with `--scaffold`
THEN the claim appears only under CLAIMED-BUT-ABSENT
AND no spec.md stub is generated for it.

### Requirement: "Found nothing" SHALL be distinguished from "did not look" <!-- id: SGA-04 -->

Exit codes SHALL follow the scan convention: `0` scanned clean, `1` gaps
found under `--fail-on-gaps`, `2` the scanner could not run or could not
be pointed at a readable tree. An empty inventory because no capability
anchors exist SHALL be reported as an explicit looked-and-found-nothing
statement, never as a silent pass.

#### Scenario: an unreadable root is a scanner fault

GIVEN the scanner invoked at a path that is not a repository
WHEN it runs
THEN it exits 2 naming the path
AND no clean verdict is written anywhere.

#### Scenario: an empty inventory is unknown scope, never clean

GIVEN a tree with no capability anchors at all
WHEN the scanner completes a full pass
THEN the report says `unknown scope (no anchors found)`
AND that wording is distinct from a zero-gaps verdict, so a reader never
     mistakes an honest empty for a pass.

### Requirement: Coverage discovery SHALL have exactly one implementation <!-- id: SGA-05 -->

The gap scanner and `spec_traceability.py` SHALL share one discovery
mechanism for spec files and markers so the two gates cannot report
different coverage numbers for the same tree.

#### Scenario: the two gates cannot disagree

GIVEN any tree with openspec material
WHEN both gates report coverage for it
THEN the ID sets they see are identical by construction
AND a divergence fails the scanner's own test suite, not production CI.

### Requirement: The scanner SHALL be additive to the traceability refusal <!-- id: SGA-06 -->

The scanner SHALL NOT change `spec_traceability.py`'s exit-2 behavior on a
zero-spec tree; it exists to turn that refusal into an actionable, ranked
gap list upstream of human spec authoring.

#### Scenario: config refusal keeps its meaning

GIVEN a repo with no `openspec/specs/**`
WHEN both run
THEN traceability still exits 2 as a config error
AND the scanner instead prints the scaffold set with evidence anchors.

#### Scenario: scaffolding does not soften the refusal

GIVEN the same repo scanned with `--scaffold`
WHEN traceability runs afterwards on the pre-review tree
THEN it still exits 2 — empty scaffolds do not count as a spec universe
AND only reviewed, marker-bearing specs change that verdict.

### Requirement: The testbed acceptance contract is MergeKingdom <!-- id: SGA-07 -->

The gap scanner SHALL be adopted only after the work-order acceptance list
passes on MergeKingdom: gap table backbone matches the verified GAPS.md
record, `--scaffold` produces its named capability set with evidence
pointers, the known false claims do not reappear as requirements, and the
lane's next CI matrix shows gap-scan and traceability rows with honest
numbers after reviewed IDs land.

#### Scenario: warm bench, cold start

GIVEN the committed GAPS.md and work order in the testbed
WHEN acceptance is claimed
THEN each of its five numbered criteria has a recorded run or output,
locations and shape only.
