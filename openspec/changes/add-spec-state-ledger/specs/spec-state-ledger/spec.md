# Spec State Ledger

## ADDED Requirements

### Requirement: State transitions are recorded in an append-only ledger
<!-- id: spec-state-01 -->
Every change to a requirement's lifecycle state MUST be accompanied, in the same
commit, by exactly one row in `openspec/state-ledger.jsonl` naming the spec, the
requirement, the `from` and `to` states, the opening commit, the landing commit,
the tests exercised, and a sealed evidence reference. The `to` value MUST be one
of `EXERCISED`, `WIRED`, `ABSENT`, `NOT_RUN`, or `DIFFERS`; no additional state
vocabulary is introduced. Rows MUST be append-only: removing or rewriting a row
requires a new row that records the correction.

#### Scenario: closure cell edited without a ledger row
- **WHEN** a closure cell changes from `WIRED` to `EXERCISED` between a base and `HEAD` and no ledger row is added in that range
- **THEN** the gate fails, naming the requirement and stating that the transition has no recorded authority

#### Scenario: ledger row added without a state edit
- **WHEN** a ledger row is added in the range but the corresponding requirement's state is unchanged between base and `HEAD`
- **THEN** the gate fails, because the two records disagree and neither can be trusted alone

### Requirement: The gate derives transitions from the diff, not from prose
<!-- id: spec-state-02 -->
The gate MUST compute the set of changed requirements by diffing the spec tree
between a base revision and `HEAD`, and MUST reconcile that set against ledger
rows added in the same range. A free-text edit to a `Status:` line or closure
cell MUST NOT by itself establish a transition. Both the changed set and the
ledgered set MUST agree exactly; either direction of disagreement is a failure.

#### Scenario: status line edited by hand
- **WHEN** a spec's `Status:` line is edited to `Closed` with no closure table, no ledger row, and no bounding commits
- **THEN** the gate fails rather than accepting the prose as state

### Requirement: Bounding commits resolve, are ordered, and are distinct
<!-- id: spec-state-03 -->
For every transition to a terminal state, the opening commit MUST resolve in
reachable history and be a strict ancestor of the landing commit; the landing
commit MUST resolve and be an ancestor of `HEAD`; and the two commits MUST be
distinct. A commit identifier that does not resolve MUST NOT be accepted as
evidence, and MUST NOT be promoted into a ledger row by migration.

#### Scenario: single-commit declaration
- **WHEN** a requirement is declared terminal with `opened_commit` and `landed_commit` naming the same commit
- **THEN** the gate rejects the transition, because it cannot distinguish planned-then-delivered from declared-at-write

#### Scenario: unresolvable citation
- **WHEN** a ledger row cites a commit that does not resolve in reachable history
- **THEN** the gate fails closed and the requirement cannot be terminal

### Requirement: Work must land at the requirement's declared location
<!-- id: spec-state-04 -->
The diff between the opening and landing commits MUST touch at least one file
carrying the requirement's own `// spec: <id>` or `# spec: <id>` marker, using
the marker contract already defined for requirement traceability, and that file
MUST still exist at `HEAD`. This proves that code changed at the declared
location; it does not prove semantic implementation, and MUST NOT be described
as if it did.

#### Scenario: unrelated commit cited
- **WHEN** the landing window touches only files that carry no marker for the requirement being closed
- **THEN** the gate fails, naming the requirement and the empty marker intersection

### Requirement: Terminal closure requires verifiable evidence
<!-- id: spec-state-05 -->
A transition to a terminal state MUST reference a sealed evidence bundle that
the existing evidence validator accepts with exit code `0`, and every test named
in the row MUST have a passing record in that bundle. Integrity and claim
consistency MUST be verified by that validator rather than by a parallel
mechanism introduced for spec state.

#### Scenario: asserted but unexercised
- **WHEN** a terminal row references a missing bundle, an invalid bundle, or a bundle with no passing record for a named test
- **THEN** the gate fails closed and does not downgrade the failure to a warning

### Requirement: A spec is terminal only when every requirement is exercised
<!-- id: spec-state-06 -->
A spec MUST NOT be reported terminal while any of its requirements is `WIRED`,
`ABSENT`, `NOT_RUN`, or `DIFFERS`. The requirement set MUST be derived from
`<!-- id: ... -->` markers rather than from closure-table rows, so a table that
omits a requirement cannot hide it. A spec yielding zero requirement identifiers
MUST be reported as unsupported format, never as having nothing to check.

#### Scenario: partial closure declared complete
- **WHEN** `Status: CLOSED` appears on a spec whose closure table still carries one `WIRED` requirement
- **THEN** the gate fails and names the non-terminal requirement

#### Scenario: heading-only spec
- **WHEN** a spec contains no requirement identifiers in the supported format
- **THEN** the gate reports unsupported format rather than passing vacuously

### Requirement: The published index is generated, and drift fails
<!-- id: spec-state-07 -->
`openspec/INDEX.md` MUST be rendered from the ledger and closure tables by a
generator in the tree. A check mode MUST regenerate to a temporary path and fail
when the committed file differs. The file's own claim about being generated MUST
match how it is actually produced; a hand-maintained index that describes itself
as generated is a defect.

#### Scenario: hand-edited index
- **WHEN** a status is changed in `INDEX.md` without a corresponding spec or ledger change
- **THEN** the drift check fails and the divergence is reported

### Requirement: Migration proves what is provable and marks the rest
<!-- id: spec-state-08 -->
Backfilled rows MUST be accepted only where the cited implementation path exists
at `HEAD`, a matching requirement marker appears in a file that changed within a
resolvable commit window, and both commits resolve in reachable history. Rows
that cannot meet that standard MUST be recorded as explicitly unproven, remain
visible in the index, and MUST NOT be promotable to proof by editing the spec. A
spec that acquires a ledger row MUST NOT revert to free-text status authority.

#### Scenario: history merged from another repository
- **WHEN** a spec cites a commit that belonged to a fork merged into this repository and does not resolve here
- **THEN** migration records the row as unproven rather than fabricating provenance

### Requirement: Enforcement placement is stated honestly
<!-- id: spec-state-09 -->
The enforcement mechanism MUST be documented together with what it can and
cannot prevent. Where the repository accepts direct pushes to its default
branch without a pull-request gate, a push-time job MUST NOT be described as
blocking a transition; it detects one that already landed. A local hook that can
be bypassed MUST be documented as bypassable, with the auditing mechanism named.

#### Scenario: overclaimed enforcement
- **WHEN** documentation states that a transition cannot be made, but the wired mechanism runs only after the ref has moved
- **THEN** the claim is a defect and must be restated as detection
