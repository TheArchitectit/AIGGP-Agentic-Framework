# Spec: Fleet Manager agent channel

## ADDED Requirements

### Requirement: The manager never initiates contact with a host
<!-- id: fleet-004-01 -->
The channel SHALL consist only of documents the manager receives and checks.
The manager SHALL NOT open a connection to a host, resolve a host address, or
expose anything that requires an inbound path to a home-lab host. This SHALL be
a property of the code rather than of a deployment note: the module SHALL import
no transport and no network library, and a test SHALL read its imports to
enforce that.

#### Scenario: a network import is added

- **WHEN** the channel module gains an import of a socket, HTTP, or address
  library
- **THEN** the structural test fails and names the unexpected import

#### Scenario: an agent calls in

- **WHEN** a host agent has a report for the manager
- **THEN** the agent opens the connection and the manager only answers

### Requirement: Enrollment is one-time and bound; a key belongs to one host
<!-- id: fleet-004-02 -->
An enrollment token SHALL be bound to exactly one host and its pools, SHALL have
a bounded lifetime, and SHALL be redeemable once. The host identity of an
enrollment SHALL be taken from the token, never from the request. A token SHALL
be treated as a bearer secret: it SHALL have no document form and SHALL NOT
appear in a refusal message.

A public key SHALL identify exactly one host. Enrollment and rotation SHALL both
refuse a key that is already enrolled, and revocation SHALL NOT free a key for
re-enrollment.

#### Scenario: a token is redeemed twice

- **WHEN** the same token is presented a second time
- **THEN** it is refused as already used

#### Scenario: a key is offered by a second host

- **WHEN** an enrollment or rotation presents a public key another host already
  holds
- **THEN** it is refused, and the refusal names the host that holds it

#### Scenario: a refusal for an unknown token

- **WHEN** an unknown token is presented
- **THEN** it is refused without the token value appearing in the message

### Requirement: Reports are signed over one frozen profile
<!-- id: fleet-004-03 -->
A report SHALL carry a signature over exactly the canonical bytes of the
envelope without its signature field: sorted keys, no whitespace, UTF-8, and no
NaN or Infinity. The body SHALL be stored as that canonical text, and an
envelope whose body is not canonical SHALL be refused, so the bytes that were
signed and the bytes a consumer reads cannot differ.

The manager SHALL verify the signature against the enrolled key before acting on
any part of the report. The signature provider SHALL be supplied by the caller.
A provider that raises SHALL produce a refusal, not a crash, and SHALL NOT be
replaced by a fallback; a result that is not exactly `True` SHALL be treated as
a failed verification.

#### Scenario: a forged signature

- **WHEN** a report's signature does not verify against its key
- **THEN** the report is refused

#### Scenario: the bytes change

- **WHEN** any signed field differs from the field the signature covers
- **THEN** verification fails

#### Scenario: the provider is unavailable

- **WHEN** the verifier raises
- **THEN** the report is refused, the reason names a provider refusal, and the
  channel does not fall back to another check

### Requirement: Replay protection is stateful and strict
<!-- id: fleet-004-04 -->
Per (host, key), a report's sequence SHALL strictly increase and its nonce SHALL
not have been used. A gap in the sequence SHALL be accepted. A report's lifetime
SHALL be bounded, and freshness SHALL be judged against an instant supplied by
the caller, never the host clock; a report older than its lifetime, or issued
beyond the permitted clock skew, SHALL be refused.

Replay state SHALL be recorded only after the signature has verified, so a
report that fails verification cannot consume a sequence number or a nonce.

#### Scenario: a captured report is replayed

- **WHEN** a previously accepted report is presented again
- **THEN** it is refused as not new

#### Scenario: a report is lost

- **WHEN** the sequence skips from 1 to 7
- **THEN** the report with sequence 7 is accepted

#### Scenario: a forged report arrives first

- **WHEN** a report with a bad signature is refused and the genuine report with
  the same sequence follows
- **THEN** the genuine report is accepted

#### Scenario: a nonce is reused under a new sequence

- **WHEN** a report carries a nonce already seen for its key
- **THEN** it is refused

### Requirement: Rotation overlaps for a bounded window; revocation is immediate
<!-- id: fleet-004-05 -->
Rotation SHALL issue a new active credential and SHALL keep the previous key
verifying until a fixed instant, so a report signed before the agent learned of
the rotation is still accepted. After that instant the previous key SHALL be
refused. Rotation SHALL refuse the current key, a revoked credential, and a key
enrolled elsewhere, and SHALL advance the generation by exactly one.

Revocation SHALL take effect immediately for the active credential and for any
still-retiring one, and a second revocation SHALL be refused. A credential's
absolute lifetime SHALL be enforced separately from the rotation overlap.

#### Scenario: a report in flight during rotation

- **WHEN** a report signed with the previous key arrives within the overlap
- **THEN** it is accepted

#### Scenario: a report after the overlap

- **WHEN** a report signed with the previous key arrives after the overlap
- **THEN** it is refused

#### Scenario: a revoked host

- **WHEN** a credential is revoked
- **THEN** no report under that key is accepted from that instant, including one
  under a still-retiring previous key

#### Scenario: a credential outlives its absolute lifetime

- **WHEN** a report arrives after the credential's `not_after`
- **THEN** it is refused even though the rotation window has not closed
