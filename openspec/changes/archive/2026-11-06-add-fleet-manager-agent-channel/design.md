# Design: Fleet Manager agent channel

## The manager never dials a host, and the code says so

FLEET-004 is enforced twice: the module contains no transport at all (no
socket, no HTTP client, no URL type, no address parameter), and a test parses
`channel.py` and compares its import set to an exact allowlist. Adding
`urllib` to the file fails that test, which is the point: "outbound-only" is a
property of the code that a reviewer can check, not a sentence in a design
document.

The consequence is a pull model. An agent calls in with a signed report; the
manager answers. There is no path by which the manager reaches a home-lab host,
so there is no path to protect, and no inbound port to expose.

## Identity comes from the token, and the token is a bearer secret

`enroll(token_id, public_key)` takes the host identity from the token, never
from the request. An agent cannot enroll as another host by asking to; it would
have to hold that host's token.

A token is therefore treated as a credential, not as an identifier:

- it is redeemed once (`_consumed` outlives the token itself, so the refusal
  says "already used" rather than "unknown");
- its lifetime is capped at an hour and it refuses redemption before issuance
  and after expiry;
- it has no document form, so it cannot be written to the store by accident;
- `EnrollmentToken.token_id` is `repr=False`, so a token cannot print itself
  into a log;
- no error message echoes it — a refusal names the rule, and the tests assert
  the value is absent from the message.

When the caller does not supply a token id, one is generated with
`secrets.token_hex(16)`. A caller-chosen id repeats the moment somebody uses a
counter, and generating bearer secrets is this module's job.

## A key belongs to exactly one host

`key_id_for(public_key)` derives the identifier from the key: `key-` plus the
first 16 hex of its SHA-256. Deriving it rather than minting it means the same
key has the same id everywhere, which is what turns "this key is already
enrolled" into a check instead of a hope. Both `enroll` and `rotate` refuse a
key another host already holds, and `_keys` keeps revoked keys, so revocation
does not quietly free a key for re-enrollment — revocation that frees the key
is not revocation.

`HostCredential.__post_init__` also refuses a `key_id` that does not match its
public key, so a hand-built credential cannot mislabel one key as another.

## One frozen byte profile

`signed_bytes()` is the canonical JSON of the envelope without `signature`:
sorted keys, no whitespace, UTF-8, `allow_nan=False`. The test pins the exact
byte string rather than a hash, because the string is what a reader can check.

The body is stored as canonical text (`body_json`), not as a dict: a frozen
value holding a mutable dict is not immutable, and the text is exactly what the
signature covers. `ChannelEnvelope` refuses a body whose canonical spelling
differs from the text it was given — otherwise a valid signature could be
presented over bytes that disagree with the bytes a consumer reads.

## Checks in order, and state committed last

`accept()` runs: credential lookup → usability at the supplied instant →
freshness (expired, or issued beyond the clock skew) → signature → sequence →
nonce. Then, and only then, it records the sequence and the nonce.

That order is a security property, not a style choice: if the replay state
advanced before verification, an unauthenticated attacker could burn sequence
numbers and lock a host out of the channel. The suite pins it — a forged report
is refused, `last_sequence` is still `None`, and the genuine report with the
same sequence is then accepted.

A provider that raises is a refusal, not a crash: the exception is caught at
the boundary of the foreign callable and reported as "the signature provider
refused the report", and there is no fallback. A verifier returning a truthy
non-bool is refused as well; "truthy" is not "verified".

## Replay protection: strict sequence, unique nonce, bounded lifetime

- The sequence must strictly increase per (host, key). Gaps are accepted: the
  channel is at-least-once, and refusing the report after a lost one would turn
  packet loss into an outage.
- The nonce must be unused for that key. Retention is bounded by the envelope's
  own expiry, so the set is at most one message lifetime of traffic; a nonce is
  pruned only after the envelope that carried it can no longer be accepted.
- Lifetime is capped at 300 seconds, so no report is replayable forever.
- Freshness is judged against a caller-supplied `at`. Nothing here reads the
  wall clock, and a test reads the file to keep it that way: freshness is a
  decision about a supplied instant, not a fact about the process.

Replay state is per (host, key), so rotation starts a fresh sequence without a
window in which the old counter blocks the new key.

## Rotation overlaps; revocation does not

`rotate(host, key, new_key, at)` returns the new active credential and the old
one, now `RETIRING` with `retires_at = at + overlap` (600 seconds). The overlap
exists because the report in flight when rotation happened was signed before
the agent could know about it. After `retires_at` the old key is refused by
name, not forgotten.

`revoke()` has no overlap. It also applies to a still-retiring key, so
revoking the host does not leave the previous generation usable. A credential's
absolute lifetime (`not_after`, 90 days by default) is a separate bound from
the overlap, and both are tested.

## What is deliberately not here

No provider. No transport. No persistence. No body semantics — the payload is
opaque to this layer and becomes interesting in 3.2, where an agent is told what
it may be asked to do. And no re-enrollment path: a host that has fully revoked
its key needs a new token, which is an operator action by design rather than a
self-service one.
