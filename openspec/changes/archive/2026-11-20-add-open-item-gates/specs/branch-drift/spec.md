# Branch Drift

## ADDED Requirements

### Requirement: A commit that exists only on local disk is a failure
<!-- id: bd-01 -->
Every local ref whose tip commit is not reachable from any remote ref MUST be reported as
drift and MUST fail the gate, unless the commit is explicitly archived. The gate MUST
compare local refs against what the remote actually advertises, not against a cached
remote-tracking ref.

#### Scenario: local-only feature branch
- **WHEN** a repository holds a branch with one commit that no remote ref contains
- **THEN** the gate fails naming that branch, its tip, and how many commits it is ahead

#### Scenario: stale remote-tracking cache
- **WHEN** the local clone's `origin/*` refs are behind the real remote
- **THEN** the comparison still uses the remote's advertised tip, so a genuinely pushed ref is not reported as drift

### Requirement: Archiving is a recorded decision, not silence
<!-- id: bd-02 -->
A ref whose commit carries an `archive/<name>-<date>` tag MUST be treated as deliberately
parked rather than lost, and MUST NOT fail the gate. The match MUST be on the commit, not
on the ref name, so a branch keeps its identity while the tag records the decision.

#### Scenario: parked branch
- **WHEN** an unpushed branch's tip is also tagged `archive/feature-x-20261105`
- **THEN** the gate passes and reports the ref as archived rather than as drift

#### Scenario: tag removed
- **WHEN** the archive tag is deleted while the ref remains unpushed
- **THEN** the gate fails again, proving the archive exemption is live state and not a one-time waiver

### Requirement: Scale is reported, not flattened
<!-- id: bd-03 -->
The gate MUST report per-repo ahead counts. A branch one commit ahead and a branch 180
commits ahead are different problems, and a gate that reduces both to "drift" cannot
prioritise the operator's next action.

#### Scenario: large divergence
- **WHEN** a branch is 180 commits ahead of every remote
- **THEN** the report states the count alongside the branch name

### Requirement: No repositories scanned is never a pass
<!-- id: bd-04 -->
When no repositories are discovered under the configured root, the gate MUST exit with the
nothing-scanned code and MUST NOT report success.

#### Scenario: wrong root
- **WHEN** the root path contains no repositories
- **THEN** the gate refuses with a vacuous-pass message instead of printing OK
