# spec-template-provenance Delta

## ADDED Requirements

### Requirement: Every vendored openspec template SHALL be locked by hash <!-- id: SGA-20 -->

A lock file SHALL record, per vendored template artifact, its upstream
source URL, the sha256 of the copy in tree, the upstream version or commit
it came from, and the adoption date. A template present in tree without a
lock entry is a finding in the nightly walk.

#### Scenario: an unhashed copy is named, not trusted

GIVEN a template file added to the templates directory without editing the
lock
WHEN the provenance step runs
THEN it names the file as unlocked
AND no workflow treats it as canonical.

### Requirement: Upstream drift SHALL be detected automatically and adopted only by review <!-- id: SGA-21 -->

The scheduled walk SHALL fetch each locked upstream artifact, hash it, and
compare against the pinned hash. A mismatch SHALL raise the deduped drift
alert naming the template and both hashes. No automated process SHALL
overwrite a vendored template with upstream content.

#### Scenario: upstream moved, nothing changed locally

GIVEN a template whose upstream has advanced
WHEN the refresh check runs
THEN the alert names template, pinned sha256, and upstream sha256
AND the tree is byte-identical to before the run.

#### Scenario: adoption is a commit with a reason

GIVEN a drift alert is open
WHEN a human decides to take the upstream change
THEN the lock file and the vendored copy change in one reviewed commit
AND the alert's issue can be closed against that commit.

### Requirement: The walk SHALL refuse to certify provenance it could not check <!-- id: SGA-22 -->

If an upstream source is unreachable or the local copy is unreadable, the
provenance step SHALL report the state as unknown and fail the walk's
provenance section as a scanner fault; unknown SHALL never be summarized
as "in sync".

#### Scenario: a network outage is not a green check

GIVEN every upstream fetch times out
WHEN the walk runs
THEN provenance reads `unknown (fetch failed)` per template
AND the run is red for the fault, not green for silence.
