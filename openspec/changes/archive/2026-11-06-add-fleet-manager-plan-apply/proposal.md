# Change: Fleet Manager plan and apply

## Why

Sprint 2.1 gave the manager a desired state that only grows by revision. Nothing
yet decides *what* to change, and nothing yet changes it. FLEET-002 asks for
three properties at that seam, and each one fails silently if it is not built
in: a plan that is not deterministic cannot be reviewed, an apply that is not
bound to a revision applies to a world nobody looked at, and an apply that is not
idempotent turns every network retry into a second deploy.

## What changes

- `fleet-manager/fleet_manager/plan.py` — `Change` (one intended operation),
  `Plan` (a checksummed, ordered list with computed capacity impact), and
  `build_plan()`, which simulates the changes against the state and refuses an
  impossible one at plan time with its index.
- `fleet-manager/fleet_manager/apply.py` — `apply_plan()`, the one function that
  turns a plan into a new revision; `IdempotencyLedger`; `ApplyRefused`, which
  carries the log entry recording the refusal.
- `fleet-manager/fleet_manager/audit.py` — `AuditLog` / `AuditEvent`: append-only,
  contiguous sequence, non-decreasing time, and a reason string that cannot
  carry a credential.
- `fleet-manager/fleet_manager/auth.py` — `Principal`, `Scope` and the ladder
  read < plan < apply < admin. This is the authorization decision only: no
  transport, no token parsing, no storage.
- `fleet-manager/tests/test_plan_apply_v1.py` — the suite; 44 tests.

FLEET-002's five plan elements map to the change kinds: creates (`assign`),
drains (`drain` / `complete_drain`), replacements (`rollout`), deletions
(`release`), and capacity impact (computed per host from the simulation).

## What this does not change

No reconciler, no diff against observations (2.3), no persistence, no HTTP
surface, no runtime contact. The audit log is a value the caller keeps; where it
is stored is the store's business.
