# QA record: Fleet Manager agent channel (Sprint 3.1)

Scope: `devgate-product-tiers-fleet-manager` box 3.1, "outbound host-agent
channel; enrollment, rotation, signature verification, replay protection"
(FLEET-004). AIGGP change `add-fleet-manager-agent-channel`, requirements
`fleet-004-01..05`.

## What landed

- `fleet-manager/fleet_manager/channel.py` — `AgentChannel` (tokens,
  credentials, rotation, revocation, `accept()`), the values `EnrollmentToken`,
  `HostCredential`, `ChannelEnvelope`, `AcceptedReport`, and the closed wire
  form.
- `fleet-manager/tests/test_channel_v1.py` — 51 tests, floor-pinned to this
  module.

The signature provider is a parameter, not an import. `accept()` takes
`verifier(public_key, message, signature) -> bool`. That is the decision worth
stating first, because the alternative was worse in a way that is easy to miss:
this repository has **two** Ed25519 implementations and both are Gate-0
non-authorizing (`hub.coherence.ed25519` is a reference implementation with a
gate 0 quarantine notice; `hub.coherence.ed25519_vetted` wraps PyCA
`cryptography` but is also quarantined pending independent review). Importing
either one as *the* mandatory verifier would have promoted a quarantined module
to an authorization path in a library that never asked the question. The module
therefore owns the protocol — which key, which bytes, which checks, in what
order — and not the curve, and its import list is pinned by a test so that
stays true.

## FLEET-004 is enforced as a property of the code

The requirement is "agents initiate outbound; the manager SHALL NOT require an
inbound path". A design note saying so is not enforcement. `channel.py` has no
transport in it at all — no socket, no HTTP client, no URL, no address — and
`test_the_channel_imports_only_what_it_declares` parses the file and compares
its imports to an exact set (`__future__`, `hashlib`, `json`, `re`, `secrets`,
`dataclasses`, `datetime`, `enum`, `typing`). Adding `urllib` fails that test.
Mutation M17 plants `import socket` and is killed by it.

## The rules, and why each one fails closed if missing

| Rule | The failure it prevents |
| --- | --- |
| identity from the token, never the request | an agent enrolling as a different host |
| token redeemed once; expiry; pre-issuance refused | a token that becomes a permanent password |
| token is a bearer secret: no document form, `repr=False`, never echoed | a credential printed into a log by an exception |
| `key_id` derived from the key, one key per host | one host's signature indistinguishable from another's |
| revoked keys are never freed for re-enrollment | revocation that is really a re-issuing |
| canonical signed bytes, body stored as that exact text | a signature over bytes the consumer never reads |
| signature before replay state | a forged report burning a sequence number (a lockout) |
| provider raises = refusal, no fallback | silently downgrading authentication |
| verifier must return exactly `True` | "truthy" treated as "verified" |
| strictly increasing sequence per (host, key) | replay and reordering |
| gaps accepted | packet loss turned into an outage |
| nonce unique, retention bounded by expiry | a second lock on the same window |
| lifetime cap and a supplied `at` | a report replayable forever, or freshness read off a clock we do not trust |
| rotation overlap, revocation without one | a report in flight refused; or a revoked host still verified |

## Planted mutations: 17/17 killed

Driver: copy `fleet-manager/` **and `hub/`** into a throwaway tree, patch one
exact string, run only the channel suite, treat a non-zero exit naming
`FAILED` or `SUBFAILED` as a kill.

| # | Mutation | Killed by |
| --- | --- | --- |
| M1 | a token can be redeemed twice | `test_a_token_cannot_be_redeemed_twice` |
| M2 | a key may be enrolled to two hosts | `test_a_public_key_already_enrolled_is_refused...` |
| M3 | an expired token still enrolls | `test_an_expired_token_is_refused` |
| M4 | a rotated key retires at once (no overlap) | `test_a_retiring_key_verifies_until_its_window...` |
| M5 | rotation may reuse a key enrolled elsewhere | `test_rotation_onto_a_key_enrolled_elsewhere...` |
| M6 | revocation is a no-op on the wire | `test_revocation_refuses_a_retiring_key_immediately` |
| M7 | a retiring key keeps verifying past its window | `test_a_retiring_key_verifies_until_its_window...` |
| M8 | the signature covers the document including `signature` | `test_a_retiring_key_verifies_until_its_window...`, forged report |
| M9 | an unverified signature is accepted | `test_a_forged_report_is_refused_and_does_not_consume...` |
| M10 | a replayed sequence is accepted (off by one) | `test_the_same_report_twice_is_refused_as_a_replay` |
| M11 | a reused nonce is accepted | `test_a_new_sequence_reusing_a_nonce_is_refused` |
| M12 | a report's lifetime may exceed the maximum | `test_a_report_whose_lifetime_exceeds_the_maximum...` |
| M13 | a report from the future is accepted | `test_a_report_issued_beyond_the_clock_skew...` |
| M14 | a non-canonical body is accepted | `test_a_body_that_is_not_canonical_text_is_refused` |
| M15 | NaN is serialized into a body | `test_a_body_carrying_nan_is_refused` |
| M16 | a credential is usable past `not_after` | `test_a_credential_is_not_usable_past_its_absolute_lifetime` |
| M17 | the manager gains an outbound network import | `test_the_module_imports_only_what_it_declares` |

**M16 survived the first run and the test was the thing that was wrong, not the
mutation.** Rotation overlap and the credential's absolute lifetime are two
different clocks, and every rotation test exercised only the first; a credential
that outlived its `not_after` was accepted, and nothing noticed. The fix was the
missing test (59 minutes accepted, one hour and one second refused), not the
removal of the mutation. That is the second time in this package that a mutation
found an untested rule rather than a broken one.

## The mutation harness earned its keep in a different way this time

Unlike 2.3, there was no spurious kill: the throwaway tree copies `hub/` from
the start, because 2.3's harness defect taught that lesson. What it caught was a
genuine gap (M16). Both are recorded so the table is read as evidence rather
than decoration.

## Gates, re-run by me (from the workflow's list)

| Gate | Result |
| --- | --- |
| `openspec validate --all --strict` | 40 items, 0 failed |
| `specs-validate-negative-control.sh` | rc 0, refused as designed |
| `tests/gen_floors.py --check` | 125 suites, 1743 tests, floors hold |
| `check_manifest_join.py --repo .` | OK, both directions |
| `guardrails-scan.mjs` | non-blocking warnings only, pattern scan clean |
| `spec_traceability.py --root . --ratchet` | 115/158, ratchet raised 110 to 115 |
| `check_boundary.py --repo .` | 26 files, all declared |
| `artifact_hygiene.py --repo . --audit` | OK |
| `check_exec_bits.py` | all shebang'd files 100755 |
| `check_charset.py` / `check_encoding.py` / `check_corruption.py` | OK |
| `silent-success-scan.sh` | OK |
| `failure_registry_check.py` | rc 0 (two pre-existing stale-entry warnings) |
| `rules_check.py` | OK |
| `extraction_rehearsal.py --source .` | OK, both phases (the new module and suite extract and pass) |
| `pytest fleet-manager/tests -q` | 184 passed, 73 subtests |
| `pytest tests -q` | 1743 passed, 182 subtests |
| `regression_check.py --base origin/main` | staged-tree run: 0 over hard limit |

**One gate lesson, re-run and recorded.** The hygiene trio (charset, encoding,
corruption) reported "803 text files" before this slice was staged — and 803 is
what it said for the *previous* slice too, so it was not looking at any of the
files just written. After `git add` it reads 810 and still passes. The same
blindspot `regression_check.py` has for size ("NOT IN SIZE-GATE SCOPE", and the
memory that its hard limit ignores untracked files) applies to these: a green
result before staging is not evidence about the new files. Both runs are
recorded rather than only the green one.

A note on size, since the gate cannot see it: `fleet-manager/` is reported by
`regression_check.py` as outside the size-gate scope ("NOT IN SIZE-GATE
SCOPE"), so the 300-line soft limit is not applied to this module by the tool.
`channel.py` is 754 lines and one concern — the second-largest module in the
package after `reconcile.py` (732), and larger than `model.py` (663).

## What this deliberately does not do

No transport, no session and no persistence: nothing here opens a connection,
and `AgentChannel` is memory a store will later hold. No signature provider: the
verifier is injected, and choosing one is a security decision recorded as an
open item, not a default. No body semantics: the report body is opaque here, and
what an agent may be asked to do — plus the receipts that prove it did — is box
3.2. No re-enrollment path: a host that has revoked every key needs a new token
from an operator, which is the point rather than a gap.
