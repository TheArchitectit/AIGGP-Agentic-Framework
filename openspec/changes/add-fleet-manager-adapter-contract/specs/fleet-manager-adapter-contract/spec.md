# Spec: Fleet Manager adapter contract

## ADDED Requirements

### Requirement: One closed adapter contract, checked without calling it
<!-- id: fleet-007-01 -->
The manager SHALL define exactly one adapter contract, naming the eleven calls
the program's Sec. 5.2 requires: `discover_capabilities`, `validate_host`,
`ensure_image`, `create_runner`, `observe_runner`, `mark_drain`,
`cancel_or_timeout`, `destroy_runner`, `prove_cleanup`, `report_receipts`, and
`rollback_configuration`.

A candidate adapter SHALL be checked against that contract without being called.
The check SHALL refuse, in one refusal, every member that is missing and every
member that is present but not callable, naming each.

The check SHALL verify that every mutating call accepts a parameter named
`operation_key`; that `ensure_image` accepts `digest`; that `create_runner`
accepts `registration_ref` and no parameter whose name suggests registration
material; that `cancel_or_timeout` accepts `policy`; and that `prove_cleanup`
accepts `instance_id`. A catch-all `**kwargs` SHALL NOT satisfy any of those
names.

An adapter SHALL serve exactly one runtime, and a pool whose runtime differs
from the adapter's SHALL be refused rather than attempted.

#### Scenario: a complete adapter

- **WHEN** an object implements every call with the required parameters
- **THEN** the check accepts it and returns the contract it satisfies

#### Scenario: a missing call

- **WHEN** a candidate does not implement `prove_cleanup`
- **THEN** the refusal names `prove_cleanup`, and only that name is missing from
  the refusal's list

#### Scenario: several missing calls

- **WHEN** a candidate is missing three of the eleven calls
- **THEN** one refusal names all three

#### Scenario: a call with the wrong signature

- **WHEN** `ensure_image` has no parameter named `digest`, or a mutating call has
  no `operation_key`, or `cancel_or_timeout` has no `policy`
- **THEN** the refusal names the call and the parameter that is absent

#### Scenario: a catch-all signature

- **WHEN** a call is defined as `def create_runner(self, **kwargs)`
- **THEN** it does not satisfy `registration_ref` and the adapter is refused

#### Scenario: the wrong runtime

- **WHEN** a docker adapter is checked against a podman pool, or the runtime is
  not a `Runtime`
- **THEN** it is refused, naming both runtimes

#### Scenario: checking does not call

- **WHEN** every one of a candidate's methods raises as soon as it is called
- **THEN** the check still accepts the candidate, because conformance is a
  property of the shape

### Requirement: Adapter failures are typed and closed
<!-- id: fleet-007-02 -->
Every adapter failure SHALL be an `AdapterError` whose kind is one of exactly
eight: invalid desired state, unavailable host, registration failure, runtime
failure, cleanup failure, capacity exhaustion, policy denial, and unknown state.
A kind that is not one of those values, including a string that equals one,
SHALL be refused at construction.

An error's detail SHALL NOT be echoed when it matches the credential shape the
package already refuses in audit reasons and receipt details; the refusal SHALL
state that a value was withheld, not what it was.

An unexpected exception SHALL be classifiable as a runtime failure that records
the exception's type and not its message, because an arbitrary message is where
a credential is most likely to appear.

#### Scenario: an unknown kind

- **WHEN** an `AdapterError` is built with `kind="runtime_failure"` or with any
  value outside the eight
- **THEN** it is refused at construction, naming the eight valid kinds

#### Scenario: a detail that looks like a credential

- **WHEN** an error's detail matches the credential shape
- **THEN** it is refused, and neither the refusal nor the error's text contains
  the detail

#### Scenario: an unexpected exception

- **WHEN** a non-`AdapterError` exception is classified
- **THEN** the result is a runtime failure whose text names the exception type
  and not its message

#### Scenario: an empty kind argument

- **WHEN** the kind is omitted entirely
- **THEN** the error is refused, because "some failure" is not a kind

### Requirement: The runner image is pinned by an immutable digest
<!-- id: fleet-007-03 -->
The fleet's runner image SHALL be referenced by repository and an immutable
`sha256` digest, never by tag. A reference containing a tag rather than a digest
SHALL be refused, naming that a tag is mutable.

The package's default runner image digest SHALL equal the digest recorded by the
fleet's runner standard in `templates/runner/self-hosted-runner.container`, and
a test SHALL compare them so the two cannot drift.

A pool's pinned digest SHALL be the digest used to build its instances, and an
instance SHALL NOT be built from any other image.

#### Scenario: a tag instead of a digest

- **WHEN** an image reference is built from `ghcr.io/actions/actions-runner:2.337.0`
- **THEN** it is refused as a tag, not accepted as a pin

#### Scenario: the standard's digest

- **WHEN** the fleet standard's quadlet records an `Image=` digest
- **THEN** it equals the package's default, or the suite fails

#### Scenario: an instance from another image

- **WHEN** an ephemeral instance is requested for a pool whose digest is not the
  one the instance was built from
- **THEN** it is refused

### Requirement: One job per instance, and warm means never used
<!-- id: fleet-007-04 -->
A warm instance SHALL be either a pre-pulled image or a container that has never
run a job and is stopped clean. An instance that has run a job SHALL NOT count as
warm, and a warm pool SHALL refuse to hold one.

Warm stock SHALL be within the pool's `warm_min`..`warm_max` bounds: stock above
`warm_max` SHALL be refused as well as admitted up to it, and every warm
instance SHALL carry the pool's own id and pinned image digest.

A job instance SHALL be created with an anonymous work directory and SHALL be
removed when it exits; its rendered command SHALL contain no durable work
volume and no `/_work` mount. Registration material SHALL reach the instance
through an environment file, never as a value in the command's arguments.

#### Scenario: a used container offered as warm

- **WHEN** a warm pool is built with an instance whose state is `USED`
- **THEN** it is refused, naming that a used instance is not warm stock

#### Scenario: admitting beyond the ceiling

- **WHEN** warm stock is at `warm_max` and another instance is admitted
- **THEN** it is refused as capacity exhaustion

#### Scenario: warm stock from another image

- **WHEN** a warm instance carries a digest other than the pool's
- **THEN** it is refused, naming both digests

#### Scenario: a shortfall below the floor

- **WHEN** warm stock is below `warm_min`
- **THEN** the pool reports the shortfall and does not claim to be at its floor

#### Scenario: the ephemeral command

- **WHEN** a job instance is rendered for a pool
- **THEN** the command removes the container on exit, sets ephemerality, mounts
  no durable work volume, and names the registration reference only through an
  environment file
