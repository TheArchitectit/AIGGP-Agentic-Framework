# Design: Fleet Manager plan and apply

## The plan is a value, and its id is the review

`Plan.plan_id` is `sha256` over the canonical JSON of `(base_revision,
changes)` — nothing else. It does not include the capacity impact, the clock, or
the principal, because those are *derived*: two callers planning the same work
against the same revision must produce the same id, or "review plan A, apply
plan A" cannot be enforced. `Plan.__post_init__` recomputes the id and refuses a
plan whose id and changes disagree, so a plan is not editable after it is built.

The capacity impact is computed, not accepted: `build_plan` walks the changes
through the real model and records each touched host's free slots before the
first change and after the last. An impact a caller supplies would be a second
opinion about arithmetic that already exists in `DesiredState.capacity()`.

## Planning does not read the clock

A plan must be reproducible, so the simulation cannot use `datetime.now()`.
Using a fixed epoch was the obvious answer and it was wrong: a state created at
06:00 cannot have a release simulated at 1970 — `Assignment` refuses a release
before its issue. The clock is therefore derived from the state itself
(`plan_clock`): the newest timestamp the state already carries, or the epoch if
it carries none. It is deterministic per revision and it can never precede the
work a change acts on. Apply is the authority on time and revalidates with the
real instant.

## Apply revalidates everything, and records nothing it did not do

`apply_plan` checks, in order: authorization (including the admin requirement
for a destructive plan), the idempotency key, the base revision, then each
change against the real state. The first three refusals happen before any work.

The fourth is a re-run of the simulation, deliberately: a plan is a prediction,
and apply is where a prediction meets reality. Its audit entries are collected
on a *pending* log and only committed when the last change has applied. The
first version appended as it went, which recorded `applied` for a change that
was discarded when a later change failed — an audit log that says work happened
when it did not is worse than no log, and the suite now pins the atomic form.

## Idempotency is a promise about *which* work

A key maps to a plan id and the revision that plan produced. Replaying the same
key with the same plan returns the recorded result, appends a `replayed` entry,
and touches no state — replay works even after the state has moved on, because
the point of a retry is that the original work may already have landed. Reusing
a key for a *different* plan is refused: widening what a key covers is how a
retry becomes a second deploy. A second key for the same plan is a stale apply,
which is the correct refusal — the caller's retry contract is the key.

The ledger is a frozen value with an append operation, like every other value
here. Persisting it is the store's job.

## Authorization is a ladder, written out

`Scope` is `fleet.read` < `fleet.plan` < `fleet.apply` < `fleet.admin`, and
`_SATISFIED_BY` spells out which scopes satisfy which. There is no string
comparison and no wildcard, so widening the ladder is a visible diff. The
principal that was authorized is the object stored on the audit event: the
decision and the record cannot name different actors.

The audit event's actor is `auth.Principal` rather than a separate actor type,
for the same reason: a second identity type is a second place for them to
disagree.

## The refusal is a value

`ApplyRefused` carries the whole log with the refusal appended
(`.audit_log`), not just a message. An API layer that catches the exception and
formats an error still has the entry it must persist. A refusal that only exists
in a stack trace is invisible exactly when it matters.

## Audit invariants

- `AuditLog` is frozen; `append` returns a new log.
- Sequence numbers are exactly `1..n`: a gap, a reorder or a duplicate is
  refused at construction.
- Timestamps must be non-decreasing: an entry cannot be back-dated into a log
  that already covers that instant.
- A `reason` that matches a credential shape (provider token prefixes, PEM
  header) is refused, and the refusal does not repeat it.

## Not in this change

- **No HTTP, no sessions, no token verification.** `Principal` is the *result*
  of authentication, produced by whatever the API layer does in Sprint 7.
- **No persistence** of the ledger or the log.
- **No reconciliation.** A plan is built from desired state alone; comparing
  with observations is 2.3 and produces a diff, not a plan.
- **No concurrency control beyond the revision check.** Two applies against the
  same revision with different keys both succeed if serialized; the store's
  compare-and-set is what makes that safe, and it is not in this package.
