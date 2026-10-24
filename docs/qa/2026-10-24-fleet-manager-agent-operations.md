# QA record: Fleet Manager agent operations (Sprint 3.2)

Scope: `devgate-product-tiers-fleet-manager` box 3.2, "operation allowlist +
receipts (no remote shell); runner-enroll.sh compatibility or migration"
(FLEET-005). AIGGP change `add-fleet-manager-agent-operations`, requirements
`fleet-005-01..05`.

## What landed

- `fleet-manager/fleet_manager/operations.py` — `OperationKind` (the eight
  adapter operations), `Operation` / `Subject` / `SubjectKind`, `Evidence`,
  `AgentReceipt`, `AgentCapabilities` + `permit()`, `OperationLedger`, and
  `RUNNER_ENROLL_MIGRATION`.
- `fleet-manager/tests/test_operations_v1.py` — 58 tests, floor-pinned to this
  module.

The decision worth stating first: **the agent's receipt is evidence, and the
manager's contract receipt is authority, and those are two different
documents.** The v1 `operation_receipt` contract enumerates control-plane
operations (`enroll`, `assign`, `release`, `drain`, `apply`, `revoke`) while an
adapter performs `ensure_image`, `create_runner`, `destroy_runner` and the
rest. Two vocabularies, two audiences. The mapping between them is one dict,
`_CONTRACT_OPERATION`, and `authoritative_receipt()` builds the contract
document from an accepted claim rather than forwarding the claim. A test reads
`contracts/v1/operation-receipt.schema.json` and asserts every mapped value is
in the contract's own enum — the contract is the authority for its own
vocabulary, so the test consults it instead of restating it.

## No remote shell, as a property of the type

D4 ("Host agents expose no general remote shell") and R7's mitigation ("typed
allowlisted operations, no arbitrary command endpoint") are enforced twice,
because they fail differently:

1. `_PARAMETERS` is a closed table: a parameter the kind does not name does not
   exist for it.
2. `_SHELL_SHAPED` refuses `command`, `cmd`, `argv`, `args`, `shell`, `script`,
   `exec`, `entrypoint`, `env`, `environment`, `stdin`, `sh`, `bash`,
   `commands`, `stdout` **by name**, before the value is read.

So a future table edit that adds `("command", ...)` is still refused. A
structural test also asserts the module contains no `subprocess`, `os.system`,
`eval(`, `exec(`, `popen(` or `importlib` — the module cannot run a process even
if the name set were edited away.

## The rules, and the failure each prevents

| Rule | The failure it prevents |
| --- | --- |
| closed catalogue, closed parameter set | an operation that quietly grows a "run this" field |
| shell-shaped names refused before values | a smuggled command whose value is never inspected |
| deny by default; no adapter, no work | an agent performing work it never declared |
| `cancel_or_timeout` behind an explicit policy | a cancellation path that is on because nobody turned it off |
| observation is not a free action | a read path that bypasses the allowlist |
| `ref:<name>` for registration, never the material | a registration token stored in an operation |
| credential-shaped values and details refused, never echoed | a secret printed into a log by a refusal |
| an operation key is a durable promise | a retry that becomes a second mutation (the 2.2 lesson again) |
| one receipt per key; the first answer is the answer | an outcome quietly rewritten after the fact |
| a completion needs an evidence digest | a "done" with nothing behind it |
| receipts tied to the issued host | a receipt that speaks for someone else's work |
| read-only kinds have nothing to attest | an observation treated as a mutation in the audit trail |
| the mapping is declared and checked against the contract | an agent claim forwarded as if it were the authoritative receipt |

## Planted mutations: 20/20 killed

Driver: copy `fleet-manager/` **and** `hub/` into a throwaway tree, patch one
exact string, run only the operations suite, treat a non-zero exit naming
`FAILED` or `SUBFAILED` as a kill. Baseline green before the first mutation.

| # | Mutation | Killed by |
| --- | --- | --- |
| M1 | a shell-shaped parameter name is accepted | `test_a_shell_shaped_parameter_name_is_refused` |
| M2 | an unlisted parameter is accepted | `test_a_parameter_that_is_not_of_this_kind_is_refused` |
| M3 | a missing required parameter is accepted | `test_a_missing_required_parameter_is_refused` |
| M4 | a credential-shaped parameter value is accepted | `test_a_parameter_value_that_looks_like_a_credential_is_refused` |
| M5 | registration material accepted instead of a reference | `test_a_registration_reference_is_a_reference_not_the_material` |
| M6 | a mutable image tag is accepted where a digest is required | `test_ensure_image_needs_an_immutable_digest` |
| M7 | an operation may act on any subject kind | `test_an_operation_acts_only_on_the_subjects_it_names` |
| M8 | work not in the allowlist is permitted | `test_a_read_only_operation_is_still_denied_by_default` |
| M9 | an agent with no adapter may be given work | `test_an_agent_with_no_adapter_may_not_be_given_work` |
| M10 | `cancel_or_timeout` needs no explicit policy | `test_cancel_or_timeout_needs_the_explicit_policy` |
| M11 | a completion without evidence is accepted by the value | `test_a_completion_without_evidence_is_not_a_receipt` |
| M12 | a credential-shaped detail is accepted | `test_a_detail_that_looks_like_a_credential_is_refused` |
| M13 | an operation key can be widened | `test_a_key_cannot_be_widened` |
| M14 | a receipt from another host is accepted | `test_a_receipt_from_the_wrong_host_is_refused` |
| M15 | a second, different receipt is accepted | `test_a_second_receipt_that_says_something_else_is_refused` |
| M16 | a read-only operation can be receipted | `test_a_read_only_operation_has_nothing_to_attest` |
| M17 | the authoritative receipt names the wrong subject kind | `test_the_authoritative_receipt_is_built_not_forwarded` |
| M18 | a kind with no contract mapping builds a receipt anyway | `test_a_kind_with_no_declared_contract_operation_is_refused` |
| M19 | a receipt for an unissued key is accepted | `test_a_receipt_for_an_unissued_key_is_refused` |
| M20 | the agent claim is forwarded in the agent's own vocabulary | `test_the_agent_claim_is_not_the_authoritative_vocabulary` |

## M18 survived first, and the mutation was right: the guard was dead

The first battery was 18 mutations and ran 17/18. The survivor was "the ledger
accepts a completion without evidence" — planting that change in
`OperationLedger.record()` broke nothing, because `AgentReceipt.__post_init__`
already refuses a completion without evidence. The ledger's copy of the rule
was **unreachable**.

That is a different finding from 3.1's M16 (a rule that was never tested). Here
the rule was tested, in the only place it can fire, and the second copy was
noise: a check nothing can reach reads like defence and behaves like a comment.
The fix was to delete it and say where the rule lives, not to write a test that
pretends it is reachable. The same audit found the symmetric case in
`authoritative_receipt()` — a `read_only` check after a lookup that already
refuses — and replaced it with a live guard: a kind with no declared contract
mapping is refused by name rather than crashing as a missing dict key, and a
test (M18) now pops the table row to prove it.

## runner-enroll.sh is accounted for, not silently dropped

`scripts/runner-enroll.sh` predates this catalogue and talks to the monitor
hub. Its six documented options (`--runner-name`, `--repo`, `--labels`,
`--host-alias`, `--interval`, `--revoke`) each appear in
`RUNNER_ENROLL_MIGRATION` with the place their duty went: pool declared
repositories and labels in desired state, `create_runner.runner_name`, the
agent's poll, `AgentChannel.revoke`. A skip-guarded test parses the script's own
`#   --option` lines and fails if the sets differ. Skip-guarded because the
extraction rehearsal does not copy `scripts/`, so a missing script is a skip
and a changed one is a failure.

## Gates, re-run by me (from the workflow's list)

| Gate | Result |
| --- | --- |
| `openspec validate --all --strict` | 41 items, 0 failed |
| `specs-validate-negative-control.sh` | rc 0, refused as designed |
| `tests/gen_floors.py --check` | 125 suites, 1743 tests, floors hold |
| `check_manifest_join.py --repo .` | OK, 1 join both directions |
| `guardrails-scan.mjs` | non-blocking warnings only, pattern scan clean |
| `spec_traceability.py --root . --ratchet` | 120/163, ratchet raised 115 to 120 |
| `check_boundary.py --repo .` | 28 files, all declared |
| `artifact_hygiene.py --repo . --audit` | OK |
| `check_exec_bits.py` | 116 shebang'd files, all 100755 |
| `check_charset.py` / `check_encoding.py` / `check_corruption.py` | OK, 816 text files |
| `silent-success-scan.sh` | OK |
| `failure_registry_check.py` | rc 0 (three pre-existing stale-entry warnings, none from this slice) |
| `rules_check.py` | OK |
| `extraction_rehearsal.py --source .` | OK, both phases (the new module and suite extract and pass) |
| `pytest fleet-manager/tests -q` | 242 passed, 122 subtests |
| `pytest tests -q` | 1743 passed, 182 subtests |
| `regression_check.py --base origin/main` | staged-tree run: 0 over hard limit |

The hygiene trio read 816 text files after staging — six new files, matching
what this slice added. Recorded for the same reason as in 3.1: the number that
matters is the post-staging one, and a pre-staging green run is not evidence
about files those gates have not seen.

A note on size, since the gate cannot see it: `fleet-manager/` is again
reported as outside the size-gate scope ("NOT IN SIZE-GATE SCOPE"). Measured by
hand, `operations.py` is 538 lines — the fourth module in the package by size
after `channel.py` (754), `reconcile.py` (732) and `model.py` (663). One
concern: the catalogue, the ledger, and the migration table.

## What this deliberately does not do

No executor and no adapter implementation: this module names what an adapter
may be asked to do and never starts anything. No transport: still no socket,
and the receipt carries no address. No persistence: `OperationLedger` is memory,
the same shape as `AgentChannel`, and a store will later hold both. No signature
of its own: a receipt is authentic only through the channel (3.1), which is why
it is keyed to work the manager issued instead of self-certified. No decision
about the Ed25519 provider — still the open security sign-off from 3.1, not a
default. And no runner lifecycle: `create_runner` is a typed instruction with a
registration *reference*, not a bootstrap path.
