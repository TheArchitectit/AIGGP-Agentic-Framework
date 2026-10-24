# Change: Fleet Manager agent operations (typed allowlist, receipts)

## Why

Sprint 3.1 established *who* is calling: an enrolled host, on a connection it
opened, with a signed, replay-protected report. This change answers the other
half of the same boundary — **what such a caller may be told to do, and what
proves it did it**.

Two normative sentences in the program say it directly. D4: "Host agents expose
no general remote shell." R7's mitigation: "signed desired state, typed
allowlisted operations, no arbitrary command endpoint, receipts, replay
protection." A prose promise of "no arbitrary command endpoint" is not
enforcement; the only way to keep it is to make the instruction vocabulary
closed. If an operation cannot carry a command, an argv, a script, or an
environment, then a future adapter cannot quietly grow a shell.

The other failure this prevents is the receipt gap. D5: "Every mutation has an
authoritative audit receipt." An agent's claim that it did the work is not a
receipt — it is evidence, and evidence is only as good as its tie to work the
manager actually issued. A completion with nothing to show for it, a second
receipt that rewrites the first, or a receipt for a key nobody issued are each a
way for the audit trail to stop being true while still being full.

There is also a vocabulary trap worth naming: the v1 `operation_receipt`
contract enumerates control-plane operations (`enroll`, `assign`, `release`,
`drain`, `apply`, `revoke`), while an adapter performs `ensure_image`,
`create_runner`, `destroy_runner` and so on. Left implicit, that mismatch is
where an agent receipt gets forwarded as if it were the authoritative document.
This change makes the mapping a declared value and tests it against the
contract's own enum.

## What changes

- `fleet-manager/fleet_manager/operations.py` — `OperationKind` (the eight
  adapter operations), `Subject` / `SubjectKind`, `Operation` (closed parameter
  set per kind; shell-shaped parameter names refused by name), `Evidence`,
  `AgentReceipt`, `AgentCapabilities` + `permit()` (deny by default,
  `cancel_or_timeout` behind an explicit policy), and `OperationLedger` (issues
  operations by durable key, takes one receipt per operation, builds the
  contract-v1 authoritative receipt through a declared mapping). Plus
  `RUNNER_ENROLL_MIGRATION`, the table that accounts for every option of
  `scripts/runner-enroll.sh`.
- `fleet-manager/tests/test_operations_v1.py` — 57 tests, floor-pinned to this
  module, including structural tests (no execution primitives, no wall clock)
  and a skip-guarded test that reads the enrollment script and fails if it grows
  an option the migration table does not cover.

## What this does not change

No transport and no executor: this module never runs anything and never opens a
connection. No adapter implementations: the catalogue names what an adapter may
be asked to do, not how a container is started. No persistence: `OperationLedger`
is memory a store will later hold, the same shape as `AgentChannel`. No
signature of its own: a receipt's authenticity comes from the channel (3.1),
which is why a receipt here is keyed by the operation the manager issued rather
than self-certified. And no decision about which Ed25519 provider signs
anything — that remains the open security sign-off from 3.1.
