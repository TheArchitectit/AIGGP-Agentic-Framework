# Change: Fleet Manager signed desired state (audience, sequence, expiry)

## Why

Sprint 3.1 gave a host a way to speak to the manager — an enrolled key, a
signed report, replay protection on the report. This change is the other
direction, and the pull model does not work without it: the agent calls in, and
the manager hands back a document the agent can *check* before it acts.

The program's security controls name it twice, in exactly these terms:
"replay protection on desired-state envelopes and action requests" and "signed
configuration with revision, audience, expiry, and nonce or monotonic
sequence". Sprint 3's exit is the same control exercised rather than described:
"two test hosts reconcile signed no-op desired state; compromised/replayed
commands fail closed."

What this prevents, concretely:

- **A document redirected at another host.** A signed state that does not name
  its audience is a privilege escalation with a valid signature on it: take the
  bytes meant for `host-a`, deliver them to `host-b`, and `host-b` adopts a
  world it was never authorized to become. Audience is therefore part of the
  signed profile *and* the first check, before the signature is even looked at.
- **A captured state played back later.** Desired state is configuration, not a
  status: it is fetched, cached, and may outlive the network it arrived on. A
  monotonic sequence per audience, allocated by the issuer, is what makes "this
  state" mean *now* and not *whenever it was captured*.
- **A state whose signature covers bytes the consumer does not read.** The body
  is stored as the exact canonical text the signature covers, so the signed
  bytes and the consumed document cannot disagree.
- **A signed state that carries a command.** The body must parse as a
  desired-state document. The host reconciles toward a state; it does not
  execute it. Anything that would change a host is a typed operation from
  FLEET-005 with its own receipt.
- **A signing provider that fails and is silently replaced.** Both signature
  providers in this repository are Gate-0 non-authorizing, so the provider is
  injected; a provider that raises is a refusal, never a fallback, and only
  exactly `True` verifies.

## What changes

- `fleet-manager/fleet_manager/state.py` — `SignedState` (audience, revision,
  sequence, issued/expires, canonical body text, signature), `signed_bytes()`
  (the one frozen profile), `state_to_document()` / `state_from_document()`
  (closed wire form), `StateIssuer` (one monotonic sequence per audience, signs
  after building the value it returns), and `accept_state()` (audience →
  lifetime → clock skew → signature → sequence, as a pure check that advances
  nothing).
- `fleet-manager/tests/test_state_v1.py` — 40 tests, floor-pinned.
- `fleet-manager/tests/fixtures/two-hosts/world.json` and `cases.json` — the
  two-host world and thirteen hand-written failure/revocation cases.
- `fleet-manager/tests/test_two_hosts_v1.py` — the Sprint 3 exit as a suite:
  both hosts enroll, sign a report, are accepted, verify their own signed no-op
  desired state, and reconcile it to no changes; every fixture fails closed on
  the rule it names.

## What does not change

No key material, no curve, and no signature implementation ships here. The
provider is injected exactly as it is in `channel`, for the same reason and with
the same consequence: choosing the Ed25519 implementation is a security
decision with a sign-off, not a module default.
