# instance-and-runner Delta

## ADDED Requirements

### Requirement: Discovery SHALL precede reliance <!-- id: GLF-10 -->

A GitLab instance SHALL be documented (version, URL, auth shape, network
posture) and its backup SHALL be restore-tested before any repo depends on
gates running there. The lab instance is tailnet-only and version-pinned.

#### Scenario: undocumented instance

GIVEN an instance without completed discovery documentation
WHEN gate availability is declared for repos on it
THEN the declaration SHALL be blocked pending the runbook.

#### Scenario: untested backup

GIVEN an instance whose backup has not passed a restore drill
WHEN any gate work is scheduled to depend on the instance
THEN the dependency SHALL be blocked and the block SHALL name the missing
restore-drill evidence.

### Requirement: GitLab runners SHALL meet the fleet runner standard <!-- id: GLF-11 -->

GitLab runners SHALL meet the same standard as the GitHub fleet: rootless
container execution, digest-pinned images, fail-closed behavior — expressed
through the shipped runner contract (`scripts/runner-enroll.sh`,
`hub/schema/runners.schema.json`) extended with a forge field, never a
forked standard.

#### Scenario: tag-pinned image

GIVEN a runner image referenced by mutable tag
WHEN the runner standard check runs
THEN it SHALL FAIL until the image is digest-pinned.

#### Scenario: fail-closed registration

GIVEN a runner enrollment attempt that cannot complete verification
WHEN `runner-enroll.sh` processes it
THEN it SHALL fail closed (no runner registered) exactly as on the GitHub
fleet.

### Requirement: Mirrored templates SHALL be thin launchers <!-- id: GLF-12 -->

GitLab CI templates SHALL be includes that invoke the identical gate scripts
used by the GitHub templates, for every gate that ships in
`templates/github-workflows/` (seven at writing time: guardrails compliance,
secret validation, file size, smoke gate, scheduled drift scan,
spec-coherence, specs-validation). The set is the shipped one, counted from
that directory; adding or retiring a GitHub template updates the GitLab
mirror in the same change.

#### Scenario: template divergence

GIVEN a GitLab template embedding gate logic inline rather than invoking
the shared script
WHEN reviewed
THEN it SHALL be rejected.

#### Scenario: count drift between template families

GIVEN `templates/github-workflows/` and `templates/gitlab-ci/` whose
template sets differ
WHEN the mirror check runs
THEN it SHALL fail naming the unmatched template(s).

### Requirement: Instance ownership SHALL be declared per instance <!-- id: GLF-13 -->

Per-instance ownership identity, security-patch cadence, upgrade cadence,
and adapter-supported GitLab version SHALL be declared in deployer
configuration — never hardcoded in code. Ownership identity is a key-hash
allowlist entry when no CA runs (CA-optional per SA-9). The adapter's
contract SHALL cover self-hosted GitLab and GitLab.com as surfaces of one
adapter; enabling GitLab.com for a deployment is an opt-in exposure
decision, never default-on.

#### Scenario: undeclared instance

GIVEN a GitLab instance with no ownership/cadence declaration
WHEN the adapter is asked to serve it
THEN it SHALL refuse and name the missing declaration.

#### Scenario: hosted surface off by default

GIVEN a fresh deployment whose declaration names only a self-hosted instance
WHEN the adapter initializes
THEN GitLab.com SHALL NOT be enabled as a surface
AND enabling it SHALL require an explicit declaration change.