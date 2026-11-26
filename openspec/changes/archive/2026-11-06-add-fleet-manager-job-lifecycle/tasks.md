# Tasks: Fleet Manager one-job lifecycle (Sprint 4.2)

## 1. The lifecycle as data

- [x] 1.1 `JobState` — the closed set of 4.1's instance states extended with
      the job's own: assigned, running, refused, and the four terminals.
      Eleven states, one enum; `PREPULLED` and `QUARANTINED` spell the same
      word as their `InstanceState` counterparts because they are the same
      fact seen from two sides.
- [x] 1.2 The transition table — one machine, no transition from a terminal
      back to a warm state, and a refusal naming the state pair for every
      transition the table does not have. `next_states()` exposes the table so
      the closure is testable as data; `_transition()` is the only place a
      state changes (the first battery found `offer` bypassing it — M1).
- [x] 1.3 One job per instance — a second offer is a `POLICY_DENIAL` and leaves
      the state unchanged. `offer()` checks it before the table, because an
      instance that already took a job has no arrow to `ASSIGNED` either and
      the reason the caller must be told is the one-job rule.

## 2. Cleanup evidence

- [x] 2.1 `Disposal` — `DISPOSED`, `ABSENT`, `FAILED`, and nothing else.
      `ABSENT` is admissible and is not a weaker `DISPOSED`: an instance that
      created no volume leaves nothing behind.
- [x] 2.2 `CleanupEvidence` — instance identity, image digest, job identity if
      known, volume and network disposal, start and finish timestamps; only job
      identity optional; a proof with a `FAILED` disposal is not a proof. The
      required fields default to `None` and are refused by name, so a missing
      field is a typed `CLEANUP_FAILURE` rather than a `TypeError`. Timestamps
      reuse `channel._timestamp` — an offset is required, never assumed.
- [x] 2.3 Admission gate — a replacement is not admitted while a predecessor is
      unproven and unquarantined, and the gate reports the shortfall. The
      check lives on `admit_replacement(..., replacing=...)`: RUN-002's rule is
      about the replacement, not about the destroy, so new capacity is not
      held up by somebody else's unfinished accounting.

## 3. Quarantine

- [x] 3.1 `Quarantine` — instance id, failure kind, time; quarantined stock is
      not capacity. Fields are required and refused by name; the reason is
      bounded at 512 characters.
- [x] 3.2 A failed proof quarantines rather than dropping the instance: a
      `FAILED` disposal is recorded, refused by `prove()`, and the instance
      then takes the `DESTROYED -> QUARANTINED` arrow carrying its identity.

## 4. Resource limits

- [x] 4.1 `ResourceLimits` — memory, cpu, pids; each required, positive, and
      bounded (65536 MiB, 32 cpus, 4096 pids); a missing or unbounded limit is
      refused at construction, naming the field. Memory and pids must be whole
      numbers: a process count of 1.5 is not a smaller 2, it is not a count.
- [x] 4.2 The rendered command carries the limits it was constructed with:
      `--memory <n>m --cpus <n> --pids-limit <n>`, rendered once by
      `ResourceLimits.arguments()` and spliced into `command()`.

## 5. Typed errors

- [x] 5.1 Every lifecycle failure lands in one of the eight Sec. 5.2 kinds, with
      the mapping the design names; nothing introduces a ninth. A table-driven
      test pins fourteen representative failures to their kinds, and another
      pins the taxonomy itself at eight.
- [x] 5.2 A lifecycle call never propagates a bare exception: identifier and
      digest checks are re-raised as typed kinds, `ChannelError` becomes
      `CLEANUP_FAILURE`, and `WarmPool.admit`'s contract error becomes
      `INVALID_DESIRED_STATE`.

## 6. Evidence

- [x] 6.1 `fleet-manager/tests/test_lifecycle_v1.py` — 64 tests, 145 subtests,
      floor-pinned by `EXPECTED_TEST_COUNT`.
- [x] 6.2 Planted mutation battery against `lifecycle.py` and the new
      `adapters.py` limits code — 43 mutations, 43 killed.
- [x] 6.3 `docs/qa/2026-10-24-fleet-manager-job-lifecycle.md` with gates,
      mutation table, and residuals.

## 7. Residuals to name in the record

- [x] 7.1 No adapter implementation and no process: the disposal results and
      timestamps are values this change validates, not observations 4.3
      collects.
- [x] 7.2 The closed error taxonomy is unchanged from 4.1; this change proves
      lifecycle failures land in it rather than adding to it.
- [x] 7.3 Docker evidence is still absent; the fleet runs rootless Podman.
