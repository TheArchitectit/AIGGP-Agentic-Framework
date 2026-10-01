# spec-intake-gate Delta

## ADDED Requirements

### Requirement: The fleet SHALL be walked nightly for spec spacing <!-- id: SGA-10 -->

A scheduled workflow SHALL walk the same declaration the secret sweep uses,
run the gap scanner per repository, classify each into exactly one of
`spaced`, `gaps`, `invalid`, `unspaced`, `unscannable`, and commit a capped
trend report to `docs/qa/spec-sweeps/` plus a full artifact.

#### Scenario: a new repo is noticed the night it appears

GIVEN a repository added to the owner scope with no openspec material
WHEN the next nightly walk runs
THEN it appears as `unspaced` in that night's report
AND no human action initiated the discovery.

### Requirement: Unspaced SHALL be informational, never red <!-- id: SGA-11 -->

`unspaced` repositories SHALL be listed and counted but SHALL NOT fail the
run, mirroring the measured SGR-10 lesson that a fleet-wide "not yet
adopted" state rendered red every night is muted by its readers and then
misses real failures. `invalid` SHALL fail the run only for repositories
present in the adoption tier file.

#### Scenario: one hundred twenty-six unspaced repos stay green-eligible

GIVEN a walk where every declared repo lacks openspec material
WHEN the classification is applied
THEN the run is not red
AND the report shows `unspaced=126` with names.

#### Scenario: a tiered repo's invalid specs are red

GIVEN a repository listed in the adoption tier file
WHEN its openspec material fails strict validation
THEN the run is red naming that repository's file and validator line.

#### Scenario: an unparseable tier file is a fault, never an empty tier

GIVEN the adoption tier file exists but cannot be parsed
WHEN the walk applies gating
THEN the run is red as a gate fault naming the tier file
AND the walk does NOT silently read "no tiered repos" — a broken gate
     reading as an empty allowlist is how every repo quietly becomes
     unenforced.

### Requirement: An unclassifiable repository SHALL never read as spaced <!-- id: SGA-12 -->

Clone failures, unreadable trees, and scanner faults SHALL be recorded
`unscannable` with the reason, counted in the summary, and named in the
alert body; the fleet verdict SHALL NOT treat them as passing. Per-repo
reasons in the alert body SHALL be truncated to 100 characters, the same
cap `hub_alert.py` applies to sweep reasons since the T-14 fix.

#### Scenario: a deleted repo names itself

GIVEN a declaration line whose repository no longer exists
WHEN the walk classifies it
THEN it is `unscannable` with the git reason
AND the deduped issue lists its name, not merely a count.

### Requirement: Alerts SHALL dedupe on one issue per key and cap the body <!-- id: SGA-13 -->

The gate SHALL raise its alert through the shared `hub_alert.py` channel
with key `spec_fleet_sweep`: a recurrence comments the same open issue, the
body names affected repositories, and per-section lists are capped with an
omitted count pointing at the run artifact.

#### Scenario: a month of findings files one issue with thirty comments

GIVEN the same spacing failure persists thirty nights
WHEN the walk alerts nightly
THEN exactly one open issue exists for the key
AND its comment count grows by one each night.

### Requirement: Adoption into the fleet SHALL follow testbed acceptance <!-- id: SGA-15 -->

The scanner and the intake gate SHALL NOT be wired into any fleet workflow
until every criterion of the MergeKingdom testbed acceptance (SGA-07) has
a recorded passing run.

#### Scenario: gates follow proven machinery

GIVEN the scanner merged but acceptance criterion 3 unproven
WHEN a CI template would add a gap-scan row
THEN the row is withheld
AND adoption proceeds only after the recorded acceptance evidence lands.

### Requirement: The gate SHALL NOT write into consumer repositories <!-- id: SGA-14 -->

The nightly walk SHALL report gaps and file alerts in this repository only.
Spec files, scaffolds, or tier changes SHALL reach a consumer repository
exclusively through a reviewed commit authored in that repository.

#### Scenario: generation proposes in the audit, merges by hand

GIVEN a repo classified `unspaced` with a strong scaffold set
WHEN the walk finishes
THEN the scaffold exists only in the report/artifact
AND its first appearance in the consumer tree is a commit a human made.
