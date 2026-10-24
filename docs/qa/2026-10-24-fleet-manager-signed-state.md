# QA: Fleet Manager signed desired state (Sprint 3.3, FLEET-006)

Date: 2026-10-24
Change: `openspec/changes/add-fleet-manager-signed-state`
Box: `devgate-product-tiers-fleet-manager` 3.3 — failure and revocation
fixtures; two test hosts reconcile signed no-op desired state.

## What this slice adds

- `fleet-manager/fleet_manager/state.py` (398 lines) — `SignedState`,
  `signed_bytes()`, the closed wire form, `StateIssuer`, `accept_state()`.
- `fleet-manager/tests/test_state_v1.py` — 46 tests, floor-pinned.
- `fleet-manager/tests/fixtures/two-hosts/world.json` (141 lines) and
  `cases.json` (96 lines) — the two-host world and thirteen failure/revocation
  cases with hand-written expectations.
- `fleet-manager/tests/test_two_hosts_v1.py` (410 lines) — Sprint 3's exit as a
  suite: two hosts reconcile a signed no-op desired state, and every failure
  path fails closed.

`state.py` is the fourth-largest module in the package (after `channel` 754,
`reconcile` 732, `model` 663). `regression_check.py` reports `fleet-manager/`
as "NOT IN SIZE-GATE SCOPE", so the number above is `wc -l`, not a gate.

## The Sprint 3 exit, as a test

`test_two_test_hosts_reconcile_a_signed_no_op_desired_state` runs the whole
path in one test: both hosts enroll (token -> credential -> key id), each signs
a report over its own observation, the manager accepts both, the issuer signs
each host its own desired state (sequence 1 each), each host verifies it, a
second round advances each host to sequence 2 and a replay of it is refused, and
the two accepted report bodies reconcile against the state to no drifts and no
changes. The reconciliation input is the body the host signed
(`AcceptedReport.body()`), not the fixture document — the test asserts those
are equal, so the chain is real rather than parallel.

The pair that makes the refusal meaningful:
`test_a_healthy_hosts_report_becomes_work` drives the same pipeline with the
same capabilities and shows the operation does get issued;
`compromised-host-pipeline` drives it for a revoked host and shows the channel
stops it before the ledger is touched.

## Fixtures

`world.json`: one pool (`phase1-linux`), two active hosts (`host-a`,
`host-b`), one warm runner each (`r-a1`, `r-b1`), one assignment each, limits
1/1/1, halted false, hand-written `expect` of no drifts, no changes, no
deferrals, converged.

`cases.json`: thirteen cases. Each carries `scenario`, `expect`
(`refused`/`accepted`), and `expect_contains` — the message fragment that names
the rule:

| case | rule it must fail closed on |
| --- | --- |
| replayed report | the sequence is not new |
| reordered report | the sequence is not new |
| report signed by the other host's key | the signature does not verify |
| forged report | the signature does not verify, and consumes no sequence |
| report signed by a revoked key | the credential is not usable at this instant |
| revoked key offered for re-enrollment | already enrolled |
| compromised host pipeline | the credential is not usable at this instant |
| replayed desired state | replayed |
| desired state for the other host | different audience |
| tampered desired state | did not verify |
| forged desired state | did not verify |
| expired desired state | expired |
| revoked host's desired state | accepted — revocation cuts the voice, not the manager |

The fixtures carry no signature of their own. A signature in a fixture would be
a signature nobody verified; the suite computes every sign at run time, and a
test enforces that the case files hold a closed key set and no hex run of
signature length.

## Mutation battery

`/tmp/mutate_3_3.py`: 32 planted mutations against `state.py`, one exact
textual change at a time, in a throwaway tree carrying `fleet-manager/` and
`hub/`. Both `test_state_v1.py` and `test_two_hosts_v1.py` run against each.
Kill = non-zero exit naming `FAILED` or `SUBFAILED`.

Baseline green before the first mutation. **32/32 killed.**

| # | mutation | killed by |
| --- | --- | --- |
| M1 | a state for another audience is accepted | `test_a_state_for_another_audience_is_refused` |
| M2 | an expired state is accepted | `test_an_expired_state_is_refused` |
| M3 | a state from beyond the clock skew is accepted | `test_a_state_issued_beyond_the_clock_skew_is_refused` |
| M4 | a truthy verifier result verifies | `test_only_exactly_true_verifies` (subtest) |
| M5 | a replayed sequence is accepted | `test_a_replayed_sequence_is_refused` |
| M6 | only a strictly older sequence is a replay | `test_a_replayed_sequence_is_refused` |
| M7 | a body that is not its own canonical text is accepted | `test_the_body_must_be_its_canonical_text` |
| M8 | a body that is not a desired-state document is accepted | `test_the_body_must_be_a_desired_state_document` |
| M9 | the value does not check its body | `test_a_body_beyond_the_limit_is_refused` |
| M10 | the lifetime is unbounded | `test_the_lifetime_is_bounded` |
| M11 | a signature of any length is accepted | `test_the_signature_is_64_bytes_of_lowercase_hex` |
| M12 | a signature that is not lowercase hex is accepted | same |
| M13 | the audience is not signed | `test_every_other_field_is_covered` |
| M14 | the sequence is not signed | `test_every_other_field_is_covered` |
| M15 | the schema is not signed | `test_the_profile_is_pinned_byte_for_byte` |
| M16 | the issuer signs bytes other than the state it returns | `test_an_issued_state_verifies` |
| M17 | a signer that raises falls through | `test_a_signer_that_raises_is_a_refusal_not_a_fallback` |
| M18 | a verifier that raises falls through | `test_a_verifier_that_raises_is_a_refusal_not_a_fallback` |
| M19 | every audience shares one sequence | `test_sequences_increase_per_audience` |
| M20 | the issuer never remembers what it issued | `test_sequences_increase_per_audience` |
| M21 | an unknown wire field is accepted | `test_an_unknown_field_is_refused` |
| M22 | a missing wire field is accepted | `test_an_unknown_field_is_refused` |
| M23 | a sequence beyond the range is accepted | `test_the_sequence_is_bounded` |
| M24 | a body beyond the byte limit is accepted | `test_a_body_beyond_the_limit_is_refused` |
| M25 | an expiry before the issue instant is accepted | `test_the_lifetime_is_bounded` |
| M26 | a last sequence that is not an integer is accepted | `test_a_last_sequence_that_is_not_an_integer_is_refused` (subtest) |
| M27 | the declared schema is not required | `test_the_declared_schema_is_required` |
| M28 | the wire body is not canonicalized | `test_the_wire_form_round_trips` |
| M29 | a body past the issuer is not bounded | `test_a_signer_that_raises_is_a_refusal_not_a_fallback` (M29 makes `issue` raise before the signer path the test drives) |
| M30 | a non-callable signer is accepted | `test_a_signer_that_is_not_callable_is_refused` (subtest) |
| M31 | a non-callable verifier is accepted | `test_a_verifier_that_is_not_callable_is_refused` (subtest) |
| M32 | a non-positive ttl is accepted | `test_a_ttl_that_is_not_positive_is_refused` (subtest) |

M30–M32 survived the first run: three checks that no test exercised. They are
the same class of finding as 3.2's M18, from the other side — 3.2 found a guard
nothing could reach; this run found rules nothing checked. Each got a test
rather than a removed guard, because all three are real refusals on the public
surface.

## Gates

Run by hand from the repository root after staging, because the charset, size,
and corruption scanners do not see untracked files.

| gate | result |
| --- | --- |
| `openspec validate --all --strict` | 42 passed, 0 failed |
| `scripts/specs-validate-negative-control.sh` | passed — strict validation refused the malformed fixture, naming its designed defect (missing `## Purpose`), exit 1 |
| `tests/gen_floors.py --check` | 125 suites, 1743 tests — floors hold (core only; fleet-manager suites carry their own floors) |
| `scripts/spec_traceability.py --root . --ratchet` | 124/167 requirements covered; floor raised 120 -> 124 |
| `scripts/check_boundary.py` | 33 files under `fleet-manager/`, all declared; no open-core reference |
| `scripts/check_exec_bits.py` | 116 shebang'd files, all 100755 |
| `scripts/check_manifest_join.py` | OK — 1 join agrees in both directions |
| `scripts/check_charset.py --repo .` | OK — 827 text files within baseline |
| `scripts/check_encoding.py --repo .` | OK — 827 text files within baseline |
| `scripts/check_corruption.py --repo .` | OK — 827 text files within baseline |
| `node scripts/guardrails-scan.mjs` | pattern scan clean (33 non-blocking warnings) |
| `scripts/silent-success-scan.sh` | OK — every detected marker is allowlisted or excluded |
| `scripts/failure_registry_check.py` | exit 0 (three stale-path warnings, all in unrelated trees) |
| `scripts/rules_check.py` | OK — every enabled rule has a registered checker |
| `scripts/artifact_hygiene.py --repo . --audit` | OK — every upload step is bound |
| `fleet-manager/scripts/extraction_rehearsal.py --source .` | OK — boundary stands alone, core stands without it |
| `pytest fleet-manager/tests -q` | 296 passed, 190 subtests |
| `pytest tests -q` | 1743 passed, 182 subtests (130s) |
| `regression_check.py --base origin/main --fail-if-empty --pre-commit` | 0 over hard limit, 0 pre-existing oversize, 37 over soft limit, 4 scope gaps |

Two notes on the gates as measured rather than as assumed:

- The boundary gate initially failed on `fleet-manager/.pytest_cache/*` —
  a local artifact of my own test runs inside the boundary, matched by no
  declared path. Removing the cache (not a tracked file) cleared it; the gate
  result above is after that.
- `regression_check.py` reports `fleet-manager/` as a scope gap, so the size
  numbers in this document are `wc -l`, not a gate result. The gap predates
  this slice and belongs in a repo-hygiene change, not a security one.

## Deliberately absent

- **No signature implementation.** Both Ed25519 providers in this repository
  are Gate-0 non-authorizing. The provider is injected, as in `channel`;
  choosing one is a security sign-off, not a module default.
- **No persistent sequence store.** `StateIssuer` and the host's last-sequence
  are in memory, the same shape as `AgentChannel`. A store replaces both.
- **No transport.** How a host fetches its state is not this slice; the
  envelope is the unit, and it is checked the same way regardless of carriage.
- **No revocation list in `state`.** Revocation lives in `channel`, where the
  host's voice is; a revoked host still verifies state addressed to it, which
  the fixtures pin as deliberate.
