# Design: Fleet Manager signed desired state

## The envelope carries exactly the control list

The program's security controls ask for "signed configuration with revision,
audience, expiry, and nonce or monotonic sequence". `SignedState` has exactly
those fields and no others:

| field | what it is | why it is signed |
| --- | --- | --- |
| `audience` | one host id | a redirected state is refused before anything in it is trusted |
| `revision` | `DesiredState.revision` | which complete world this is |
| `sequence` | strictly increasing per audience | a captured state cannot be replayed |
| `issued_at` / `expires_at` | bounded lifetime | freshness, judged against a supplied instant |
| `body_json` | canonical text of a desired-state document | the bytes signed are the bytes consumed |
| `signature` | 64 bytes, lowercase hex | not covered by itself |

`MAX_STATE_LIFETIME` is one hour. Long enough to survive a retry and a reboot —
desired state is configuration a host may hold while the network is gone — and
short enough that a captured envelope expires. `MAX_STATE_CLOCK_SKEW` is the
same minute the channel tolerates, because it is the same pair of clocks.

## Monotonic sequence, not a nonce

A nonce proves a state was not seen before; a sequence proves it is *newer*.
For desired state the second is the property that matters: a host that has
already adopted revision 9 must not accept revision 7 again just because it
never saw that particular envelope. So `StateIssuer` allocates `n+1` per
audience and `accept_state()` requires `state.sequence > last_sequence`.

Gaps are accepted. The state stream is at-least-once like the channel: "state 5
never arrived" is not evidence of an attack, and refusing to advance on a gap
would turn one lost message into a host stuck at an old world.

`accept_state()` is a pure check: it does not advance the caller's sequence. The
host advances it after accepting, which is what makes a forgery cost the real
host nothing — the forged envelope cannot burn a sequence number. This is the
same discipline the channel applies to reports, and the same reason.

## One frozen profile, pinned byte for byte

`signed_bytes()` is canonical JSON — sorted keys, compact separators, UTF-8, no
NaN — of every field except `signature`, with `schema` embedded. The body is
re-serialized from its canonical text into the outer document, so the profile is
total.

A test pins the exact bytes. Not because the bytes are sacred, but because a
signature over "roughly this shape" verifies nothing: if the producer and the
consumer disagree about a separator, the signature either fails everywhere or —
worse, with a lenient verifier — succeeds over something nobody intended.

The body is stored as text, not a dict. A value type holding a mutable dict is
not immutable, and two equal values could sign differently.

## The body is a desired state, never a command

`_document_body()` parses the text, re-canonicalizes it, requires the round trip
to be byte-identical, and then requires `documents.from_document` to accept it.
Three refusals, three distinct meanings:

- not JSON → not a document;
- canonical form differs → the producer and consumer would sign different bytes;
- not a desired-state document → this is not configuration.

The third is the boundary. There is no field in `SignedState` that could carry a
shell instruction, and the module imports no way to execute anything. A host
reconciles toward the state; the operations that change a host are the typed,
allowlisted ones from FLEET-005 with receipts.

## The provider is injected, and failure is refusal

`signer(message: bytes) -> bytes` on the manager side,
`verifier(public_key, message, signature) -> bool` on the host side. Both
Ed25519 implementations in this repository are Gate-0 non-authorizing, so
choosing one is a security sign-off, not a module default — the same decision
`channel` records.

The issuer builds the unsigned value first, signs `signed_bytes()` of it, then
constructs the finished value with that signature. Nothing can sign a shape it
does not return. A provider that raises becomes a `StateError` naming the
provider and saying it does not fall back; a provider returning something other
than bytes is refused; a verifier returning anything but exactly `True` fails.

## Order of checks in `accept_state()`

`audience` → `expired` → `clock skew` → `signature` → `sequence`.

Cheapest and most decisive first. A host that receives a document for another
host should learn *that* first — not "the signature did not verify", which would
be true and misleading. Expiry before signature because a stale document is
stale regardless of who signed it. Sequence last because it is the only check
that depends on state the host keeps, and the one a valid-but-old envelope
should fail on.
