# Spec: Runner-owned evaluator-image cycling

## ADDED Requirements

### Requirement: Fleet hosts converge on the recorded identity out of band
<!-- id: img-cycle-01 -->
The fleet SHALL keep the pinned evaluator image present on each enrolled
runner by an out-of-band cycle — a timer installed alongside the runner's
heartbeat — and SHALL NOT pull at gate time (coh-rt-01). The cycle SHALL
resolve the image by its digest-qualified form `image@image_manifest_digest`
and SHALL NOT resolve a tag or a locally built image's `.Digest`. It SHALL be
idempotent: a host already holding the pinned digest SHALL NOT be re-pulled.
A host holding a DIFFERENT build of the same image name SHALL NOT count as
converged, because the executed bytes are resolved by digest.

#### Scenario: pinned image absent on the host
- **WHEN** the cycle ticks on a host whose podman store has no
  `image@image_manifest_digest`
- **THEN** it pulls the digest-qualified ref, and reports convergence only
  after the ref is present

#### Scenario: pinned image already present
- **WHEN** the cycle ticks on a host already holding the pinned digest
- **THEN** it performs no pull and exits 0

#### Scenario: the tag has moved ahead of the record
- **WHEN** the registry serves a `:main` manifest whose digest differs from
  the recorded `image_manifest_digest`
- **THEN** the cycle does not follow the tag: the record is the desired state

#### Scenario: no gate-time pull
- **WHEN** the coherence gate runs and the pinned image is absent
- **THEN** it reports the phase as SKIPPED with that reason and does not pull

### Requirement: The cycle fills the storage the gated job reads
<!-- id: img-cycle-02 -->
The runner is itself a container whose job-side podman is not automatically
the host's. The cycle SHALL target the container storage the gated job's
podman actually reads, and SHALL verify presence through that same path in
the same namespace, digest-qualified. When it cannot — wrong store, wrong
namespace, podman unreachable from the job — it SHALL fail non-zero and name
the mismatch. It SHALL NOT report success on the strength of a presence check
performed against a different store.

#### Scenario: cycler store is not the job store
- **WHEN** the cycle's verification resolves the pinned ref in a store the
  gate cannot see
- **THEN** the cycle fails with the mismatch named, rather than reporting
  convergence

#### Scenario: green cycler cannot coexist with a skipped doctor
- **WHEN** a host reports image convergence for a tick
- **THEN** a gate running on that host resolves the pinned ref and does not
  report the container phase unavailable for a missing image

### Requirement: Per-host image identity is reported and absence is visible
<!-- id: img-cycle-03 -->
Each host SHALL report its evaluator-image state with its heartbeat
(mon-registry-01, mon-online-01): the digest-qualified ref present, or an
explicit absence with a reason (podman missing, pull failed, store mismatch).
An absent or unreported field SHALL be rendered as unknown — never as healthy
— and a host that cannot serve the pinned image SHALL be visible on the fleet
dashboard.

#### Scenario: host converged
- **WHEN** a heartbeat carries the digest-qualified ref for the pinned digest
- **THEN** the fleet view shows that host as able to execute the evaluator

#### Scenario: host cannot serve the pinned image
- **WHEN** a heartbeat carries an absence with a reason, or the field is
  omitted entirely
- **THEN** the fleet view shows the deficiency and its reason, and a host
  with no image at all is not counted as ready to gate

### Requirement: Advancing the pinned identity is deliberate and atomic
<!-- id: img-cycle-04 -->
The published image tag SHALL NOT advance the pinned identity. Moving the pin
SHALL be one explicit operation that updates the registry's
`image_manifest_digest`, the workflow template's `COHERENCE_IMAGE` and
`COHERENCE_IMAGE_MANIFEST_DIGEST`, and `DEVGATE_PIN`, and SHALL fail closed
unless the pinned commit's tree carries the moved record (coh-id-04). Fleet
hosts SHALL hold no authority to perform it: the cycle SHALL NOT require
repository write credentials.

#### Scenario: a push publishes a new manifest
- **WHEN** the publish job pushes a build whose served manifest digest differs
  from the recorded one
- **THEN** no pin literal changes, and the divergence is reported (img-cycle-05)

#### Scenario: partial re-pin
- **WHEN** the digest literals are updated without moving `DEVGATE_PIN`
- **THEN** the pinned-tree chain guard fails

#### Scenario: a fleet host is compromised
- **WHEN** an operator inspects what a runner's cycle credentials can do
- **THEN** they grant no repository write authority and cannot move the pin

### Requirement: Served-versus-recorded divergence is a reported fact
<!-- id: img-cycle-05 -->
The cycle SHALL compare the registry's currently served manifest digest for
the published tag with the recorded `image_manifest_digest` and report a
divergence as an advisory alert (mon-alert-01) through the same path the
fleet already watches. Divergence SHALL NOT fail an individual host's tick —
it is a fact about the repository, not a fault on the host — and SHALL NOT be
reported only as a log notice inside a CI job.

#### Scenario: tag moved ahead of the record
- **WHEN** the served manifest digest differs from the recorded one
- **THEN** the divergence appears as an advisory on the fleet surface, naming
  both digests

#### Scenario: tag matches the record
- **WHEN** the served digest equals the recorded digest
- **THEN** no divergence advisory is raised

### Requirement: The publish job's stated trigger matches its condition
<!-- id: img-cycle-06 -->
A CI job's comment SHALL NOT describe a trigger condition that its `if:`
contradicts. The publish job SHALL publish only on a deliberate trigger, and
its documentation SHALL name that trigger exactly.

#### Scenario: documented trigger disagrees with the condition
- **WHEN** the publish job's comment claims manual dispatch while its `if:`
  fires only on push to main
- **THEN** a test fails, naming both
