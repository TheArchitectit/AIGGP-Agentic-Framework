# Spec: Fleet Manager signed desired state

## ADDED Requirements

### Requirement: A desired state is a signed document and cannot carry a command
<!-- id: fleet-006-01 -->
A desired state SHALL be an envelope signed over one frozen canonical profile
that covers every field except the signature, and that profile SHALL be pinned
byte for byte by a test. The body SHALL be the canonical JSON text of a
desired-state document: a body that is not JSON, that is not its own canonical
form, or that the desired-state document reader refuses SHALL be refused, and
the refusal SHALL distinguish those three cases.

The envelope SHALL carry no field in which a command could be placed, and the
module holding it SHALL import no way to execute a process and SHALL never read
the wall clock.

The signature provider SHALL be injected by the caller. A provider that raises
SHALL be a refusal that does not fall back to another provider, and only exactly
`True` from the verifier SHALL count as verified.

#### Scenario: a body that is not a desired state

- **WHEN** an envelope is built with a body that is not a desired-state document
- **THEN** it is refused, naming that the body must be a desired-state document

#### Scenario: a body that is not its own canonical text

- **WHEN** an envelope's body text differs from the canonical form of the
  document it parses to
- **THEN** it is refused as not canonical, because the signed bytes and the
  consumed document would disagree

#### Scenario: a signature provider fails

- **WHEN** the signer raises, or the verifier raises, while a state is issued or
  accepted
- **THEN** the failure is a refusal that states no fallback provider is used

#### Scenario: a verifier that is not certain

- **WHEN** the verifier returns a truthy value that is not exactly `True`
- **THEN** the state is refused as not verified

### Requirement: A signed state names exactly one audience
<!-- id: fleet-006-02 -->
Every envelope SHALL name exactly one audience, and that audience SHALL be a
valid host identifier. A host SHALL refuse a state whose audience is not its
own, and the audience check SHALL run before the signature is verified, so a
redirected document is refused as a matter of authorization rather than as a
matter of cryptography.

#### Scenario: a state meant for another host

- **WHEN** a host accepts a state whose audience is a different host
- **THEN** it is refused as being for a different audience

#### Scenario: a redirected state with a bad signature

- **WHEN** a state names another audience and would also fail verification
- **THEN** the audience refusal is the one reported

### Requirement: A state is fresh and cannot be replayed
<!-- id: fleet-006-03 -->
The issuer SHALL allocate a strictly increasing sequence per audience, and a
host SHALL refuse a state whose sequence is not greater than the last sequence
it accepted, naming it as a replay. A gap in the sequence SHALL be accepted,
because a lost state is not evidence of an attack.

The envelope's lifetime SHALL be bounded above, and a host SHALL refuse a state
that has expired at the instant supplied to it, and a state issued further in
the future than the tolerated clock skew. Freshness SHALL be judged against an
instant supplied by the caller and never against the wall clock.

Acceptance SHALL be a pure check: it SHALL NOT advance the caller's last
accepted sequence, so a forged envelope cannot consume a sequence number. The
host advances its sequence only after a state is accepted.

#### Scenario: a captured state replayed

- **WHEN** a host that has accepted sequence N is offered sequence N again
- **THEN** it is refused as a replayed state

#### Scenario: an older state arriving late

- **WHEN** a host that has accepted sequence N is offered a lower sequence
- **THEN** it is refused as a replayed state

#### Scenario: a state is missing from the stream

- **WHEN** a host that has accepted sequence 1 is offered sequence 3
- **THEN** it is accepted, and its sequence becomes the new last accepted

#### Scenario: an expired state

- **WHEN** a state is accepted at an instant after its `expires_at`
- **THEN** it is refused as expired

#### Scenario: a forged envelope is offered first

- **WHEN** an envelope fails verification and the genuine envelope for the same
  state is offered afterwards
- **THEN** the genuine one is still accepted, because the forgery consumed
  nothing

### Requirement: Two test hosts reconcile signed no-op desired state
<!-- id: fleet-006-04 -->
The failure and revocation paths SHALL be exercised by fixtures, not described
in prose: a world of two enrolled hosts already converged, and a set of cases
each naming the rule it must fail closed on and the message fragment that names
that rule.

Each host SHALL receive its own envelope and its own sequence, and both hosts
SHALL verify and reconcile a signed no-op desired state to no drifts and no
changes. A report signed by another host's key, a forged report, a replayed
report, a revoked key, a replayed state, a wrong-audience state, a tampered
state, a forged state, and an expired state SHALL each be refused.

A host whose key has been revoked SHALL still be able to verify a desired state
addressed to it, because revocation removes the host's voice and not the
manager's authorization to instruct it; that acceptance SHALL NOT be a way back
in, and the revoked host's reports SHALL remain refused.

#### Scenario: the two-host world is already converged

- **WHEN** both hosts' signed reports are reconciled against the signed no-op
  desired state
- **THEN** the reconciliation reports no drifts and no changes

#### Scenario: a revoked host tries to speak

- **WHEN** a host whose key is revoked submits a report
- **THEN** the channel refuses it before any operation is issued, and the
  operation ledger stays empty

#### Scenario: a revoked host tries to return

- **WHEN** another host offers a revoked public key for enrollment
- **THEN** it is refused, and the revoked key is not reusable
