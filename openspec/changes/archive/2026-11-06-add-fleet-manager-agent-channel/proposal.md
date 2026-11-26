# Change: Fleet Manager agent channel (outbound, signed, replay-protected)

## Why

FLEET-004 says Phase 1 host agents initiate outbound communication and Fleet
Manager SHALL NOT require an inbound path to home-lab hosts. That is one
sentence with an architectural consequence: the manager never dials a host, so
everything the manager knows about a host arrives on a connection the host
opened. Which raises the question this change answers — over a channel the
manager did not initiate, how does the manager know that the host on the other
end is the host it claims to be?

A token that can be redeemed twice is a password. A key that belongs to two
hosts makes one host's signature indistinguishable from another's. A signature
over bytes that are not exactly the bytes the receiver reads verifies nothing.
A report that can be replayed is a report that can be repeated forever. Each of
those is a rule that fails open if it is missing, and each is cheap to state.

## What changes

- `fleet-manager/fleet_manager/channel.py` — `AgentChannel`, the manager's side
  of the channel as in-memory state: one-time enrollment tokens bound to one
  host, credentials derived from a public key, rotation with a bounded overlap,
  immediate revocation, and `accept()`, which verifies a signed report and
  records it as seen. Plus the values (`EnrollmentToken`, `HostCredential`,
  `ChannelEnvelope`, `AcceptedReport`) and the closed wire form
  (`envelope_to_document` / `envelope_from_document`).
- `fleet-manager/tests/test_channel_v1.py` — 51 tests, floor-pinned to this
  module, including a structural test that reads `channel.py` and fails if it
  ever gains a network import or reads the wall clock.

The signature provider is injected, not imported: `accept()` takes a
`(public_key, message, signature) -> bool` callable. Both Ed25519
implementations in this repository are Gate-0 non-authorizing, so choosing the
mandatory verifier is a security decision with a sign-off. Keeping the provider
out of the module means that decision cannot be made by accident, and the
import list (pinned by a test) has no crypto in it.

## What this does not change

No transport, no session, no storage: nothing here opens a socket, and
`AgentChannel` is memory a store will later hold. No operations: the body of a
report is opaque to this layer, and what an agent may be told to do is the next
box (3.2). No policy about *which* hosts may enroll beyond the token a human or
bootstrap script issued.
