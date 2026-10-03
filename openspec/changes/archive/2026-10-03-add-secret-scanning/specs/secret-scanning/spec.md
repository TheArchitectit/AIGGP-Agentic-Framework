# Spec: Secret scanning on the push path

## ADDED Requirements

### Requirement: Every push is scanned, and a scan that did not run is not a pass
<!-- id: secret-scan-01 -->
The push path SHALL run a secret scan over the commits being pushed and over
the working tree. Exit 0 SHALL mean the scanner ran over the named scope and
found nothing. When the scanner is absent or unusable the gate SHALL exit
non-zero and name the reason; when the invocation itself is wrong it SHALL exit
non-zero and distinguish that from a finding. A scan that could not run SHALL
NOT be reported as a clean repository.

#### Scenario: scanner not installed
- **WHEN** the gate runs on a host with no secret scanner on PATH
- **THEN** it exits non-zero with a message naming the missing scanner, and
  does not report the repository clean

#### Scenario: the scanner runs and finds nothing
- **WHEN** the gate scans a range with no findings
- **THEN** it exits 0 and says which scope it scanned

#### Scenario: a first push with no usable base
- **WHEN** the range's base commit does not exist (first push, forced update)
- **THEN** the gate scans the full history, states in its output that it fell
  back to that scope, and does not scan nothing

### Requirement: A finding fails the push and is reported without the secret
<!-- id: secret-scan-02 -->
A finding SHALL fail the gate non-zero. Every reported finding SHALL name the
rule, the path, the line, and the commit, and SHALL NOT print the matched
value: redaction SHALL be applied to all console output and to every report
the gate writes, so a scan cannot republish a secret into logs or artifacts.

#### Scenario: a credential is committed in the pushed range
- **WHEN** a pushed commit adds a credential the scanner's rules match
- **THEN** the gate exits non-zero and names rule, path, line, and commit

#### Scenario: the report is redacted
- **WHEN** the gate writes a report for a run that found something
- **THEN** the report contains no matched value, only the finding's location

### Requirement: Dispositions are explicit, reasoned, and expire visibly
<!-- id: secret-scan-03 -->
A tolerated finding SHALL require an allowlist entry that names the rule, the
path, and a reason. A finding not covered by such an entry SHALL fail. The gate
SHALL report entries that no longer match any finding, so suppression that has
outlived its subject is visible rather than silent. Dispositions SHALL NOT be
implemented by disabling a rule or by excluding a file class from the scan.

#### Scenario: new occurrence of an allowlisted rule in another file
- **WHEN** the same rule fires in a path no entry covers
- **THEN** the gate fails, because the entry covers a location, not a rule

#### Scenario: allowlist entry with no subject left
- **WHEN** an entry's rule and path no longer match any finding
- **THEN** the gate reports that entry as stale, naming it

#### Scenario: entry without a reason
- **WHEN** an entry carries no reason
- **THEN** the gate refuses the allowlist and exits non-zero

### Requirement: The push gate and the history sweep are separate scopes
<!-- id: secret-scan-04 -->
The push gate SHALL scan the commits being pushed. A full-history sweep SHALL
be available as an explicit invocation. The push gate SHALL NOT silently widen
its scope to the whole history, and the sweep SHALL NOT be run as part of the
per-push path.

#### Scenario: history sweep requested
- **WHEN** the gate is invoked for a full-history sweep
- **THEN** it scans every reachable commit and reports that scope

#### Scenario: per-push invocation does not sweep history
- **WHEN** the gate is invoked with a pushed range
- **THEN** its scope is that range, and commits outside it are not scanned

### Requirement: The scanner is pinned and checksum-verified, not a marketplace action
<!-- id: secret-scan-05 -->
The gate SHALL use a pinned scanner version, and the installation path used in
CI SHALL verify the artifact against the vendor's published checksum before
running it. The push path SHALL NOT introduce a third-party marketplace action
for scanning, and SHALL NOT depend on a hosted-only runner.

#### Scenario: checksum mismatch
- **WHEN** the fetched scanner artifact does not match the pinned checksum
- **THEN** the installation fails and no scan is attempted

#### Scenario: scanner already present on the runner
- **WHEN** a self-hosted runner already provides the pinned version
- **THEN** the gate uses it without fetching

### Requirement: The drop-in template enforces the same contract
<!-- id: secret-scan-06 -->
The workflow template shipped for consumers SHALL use the same gate and the
same pinned-scanner mechanism as this repository's own push path, so the
contract a consumer adopts is the one that is exercised here, and so the
template works on a self-hosted runner without a scanner licence.

#### Scenario: consumer copies the template
- **WHEN** a consumer installs the secret-scanning template
- **THEN** the workflow invokes the gate script, and its failure semantics match
  the ones specified above

### Requirement: Absence of fleet scan state is reported, never implied healthy
<!-- id: secret-scan-07 -->
The fleet sweep SHALL report, per declared repository, either a positive scan
result with its scope and time, or an explicit reason it could not scan. A
repository with no recorded scan state SHALL be rendered as unknown, never as
healthy.

#### Scenario: repository could not be fetched
- **WHEN** the sweep cannot fetch a declared repository
- **THEN** that repository is reported with the failure reason, not omitted

#### Scenario: repository never scanned
- **WHEN** the fleet view renders a repository with no scan record
- **THEN** it shows unknown rather than a passing state
