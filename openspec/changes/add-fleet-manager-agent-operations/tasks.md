# Tasks: add-fleet-manager-agent-operations

Program package: `devgate-product-tiers-fleet-manager`, Sprint 3 box 3.2
(operation allowlist and receipts — FLEET-005). Predecessors:
`add-fleet-manager-domain-models` (2.1), `add-fleet-manager-plan-apply` (2.2),
`add-fleet-manager-reconciliation-fixtures` (2.3),
`add-fleet-manager-agent-channel` (3.1).

## 1. The catalogue

- [x] 1.1 `OperationKind` — the eight adapter operations of the adapter
      contract, and no others
- [x] 1.2 `Operation` — a closed parameter set per kind; a shell-shaped
      parameter name (`command`, `argv`, `script`, `shell`, `exec`,
      `entrypoint`, an environment) is refused by name before any value is read
- [x] 1.3 A required parameter that is missing, a parameter that is not of this
      kind, and a parameter given twice are each refused; parameters are stored
      sorted so equal operations are equal values
- [x] 1.4 `Subject` / `SubjectKind` — an operation acts only on the subject
      kinds it names
- [x] 1.5 Immutable digests for image operations; an opaque `ref:<name>` for
      registration, never the material itself
- [x] 1.6 Parameter values and receipt details that match a credential shape are
      refused and never echoed (SEC-001)

## 2. Deny by default

- [x] 2.1 `AgentCapabilities` — declared adapters and operation kinds; nothing
      is implied
- [x] 2.2 `permit()` — refuses an undeclared kind, refuses an agent with no
      runtime adapter, and refuses `cancel_or_timeout` without the explicit
      policy grant
- [x] 2.3 Observation is an operation like any other: a read-only kind still
      goes through the allowlist

## 3. Receipts

- [x] 3.1 `Evidence` — a digest and a location; a completion without evidence
      is refused at the value, which is the one place the rule lives
- [x] 3.2 `OperationLedger.issue()` — an operation key is a durable promise:
      the same key and the same operation is a retry; the same key and different
      work is refused
- [x] 3.3 `OperationLedger.record()` — refuses an unissued key, a receipt from
      another host, and a second receipt that differs; the identical receipt
      twice is idempotent
- [x] 3.4 A read-only operation has nothing to attest and produces no receipt

## 4. The authoritative receipt

- [x] 4.1 `_CONTRACT_OPERATION` — one declared mapping from the adapter
      vocabulary to the contract's; the mapping is tested in both directions,
      including against the enum in `contracts/v1/operation-receipt.schema.json`
- [x] 4.2 `authoritative_receipt()` — built by the manager through the mapping,
      never forwarded; a kind with no declared row is refused by name rather
      than failing as a missing dict key

## 5. runner-enroll.sh

- [x] 5.1 `RUNNER_ENROLL_MIGRATION` — every option the enrollment script
      documents is accounted for, naming where the duty went
- [x] 5.2 A skip-guarded test reads the script's own option list and fails if
      the two sets differ

## 6. Evidence

- [x] 6.1 `tests/test_operations_v1.py` — 58 tests, floor-pinned to this module
- [x] 6.2 Structural tests: the module imports no way to execute a process and
      never reads the wall clock
- [x] 6.3 Planted mutations (20) against `operations.py`, all killed
- [x] 6.4 `docs/qa/2026-10-24-fleet-manager-agent-operations.md` — the mutation
      table, the gate table, the dead-guard finding, and what is deliberately
      absent
