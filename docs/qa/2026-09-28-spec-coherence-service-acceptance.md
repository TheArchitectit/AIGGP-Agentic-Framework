# Acceptance — `devgate-spec-coherence-service`

**Date:** 2026-09-28
**Act:** Owner acceptance of the package for DEP-001 (predecessor gate of
`devgate-product-tiers-fleet-manager`).
**Accepted SHA:** `30aa60d505a36e75e46ae5a72b96f3ea2125eabb`
**Package:** `openspec/changes/devgate-spec-coherence-service/`
**Contract freeze:** `design.md` v2 (`s1-freeze-record.md`)
**Decision/exit matrix:** `decision-exit-matrix.md` (frozen)

## What "accepted" means here

The preceding DEP-001 wording is satisfied: sealed identity, green required
gates from a clean reading of the tree, this record with the exact SHA. It
does **not** mean every sprint checkpoint is implemented. It means the
shipped surface is built, measured, independently reviewed, and the
remaining work is named and scoped — not hidden in the package.

## Sealed identity

| Artifact | Identity |
|---|---|
| Contract | `design.md` v2, frozen 2026-09-17, lead-reviewed 2026-09-28 (R1–R9 finding-by-finding) |
| Schemas | 15 files under `schemas/` (12 at freeze + 3 later: `execution-profiles`, `run-envelope`, `signer-set`) — `test_frozen_schema_files_are_strict` |
| Evaluator image | `ghcr.io/thearchitectit/aiggp-agentic-framework/devgate-coherence@sha256:d798dc48d1cec73446bbc77459f8a3f1f32008b034bca172ea7ef59f155cc6a4` |
| Pin | `DEVGATE_PIN` = `ab88905c66848ba0c80c1e8cc463746770d1176c` (first tree carrying that identity) |
| Registry record | `container/execution-profiles.json` — anonymous pull verified; schemas load from fetched bytes |
| Golden vectors | `tests/fixtures/coherence/` — `compute_golden.py` reproduces `vectors.json` byte-for-byte |
| Delivery profile | `linux-amd64-v1` (only profile; Q5 = amd64-only byte-equivalence at launch) |

## Green required gates at `30aa60d`

Measured 2026-09-28 on this host against that tree:

| Gate | Result |
|---|---|
| `python3 scripts/regression_check.py --all --pre-commit` | 0 over hard limit; 21 pre-existing soft warnings (does not block) |
| `node scripts/guardrails-scan.mjs` | pattern scan clean; 26 non-blocking PREVENT-024 warnings |
| `python3 scripts/spec_traceability.py --report` | 79/142 covered, advisory (no gate-config blocking mode) |
| `python3 -m pytest -q tests/` | **1238 passed, 3 skipped**, 35 subtests passed |

Hosted evidence already on the ledger (prior runs, not re-run for this act):
pinned-image CI green (run 36022160394), publish + re-pin (36276335042),
real containerized stage-1 PASS on two hosts, hosted fleet-half coherence
green (run 36501521466), determinism 100/100 byte-identical, mutation
batteries no survivors.

## Review chain

- S0 independent audit 2026-09-22 (`s0-independent-audit.md`) — 1 MAJOR + 2
  MINOR, all dispositioned.
- Lead review of R1–R9 + ADR disposition 2026-09-28 — R1–R7 closed against
  shipped code; R8 gated on Q7 (now decided); R9 closed both halves.
- ADR-001…014, 016, 017, 019 **accepted**; ADR-015 (plugin sandbox) and
  ADR-018 (retention clause) deliberately **unaccepted** (`adrs.md` header).
- S3 ladder demo: round-5 independent APPROVE at `0db45ed`; **owner-accepted
  2026-09-28**.
- Q1–Q5, Q9 decided 2026-09-26. Q6, Q7 decided 2026-09-28. Q8, Q10 open and
  non-gating (Q10 is Redeye's domain).

## Named limits (explicitly inside this acceptance)

1. **3D vertical slice not implemented.** Spec requirements `coh-3d-01..04`
   and `coh-assert-05` are part of the frozen contract and are accepted as
   *specified*. Implementation moved 2026-09-28 to
   `openspec/changes/add-3d-vertical-slice/`.
2. **arm64 execution profile absent.** No arm hardware exists in this fleet
   (owner: "we don't have arm to test with"). Machinery accepts a second
   platform entry without further code. Q5 already froze amd64-only
   byte-equivalence at launch.
3. **Stage-2 signing inside the containerized path.** `attest.seal_run` runs
   inside the container and fails closed exit 33 `signer-key-not-configured`
   because the driver forwards only the evaluator-digest env. Present-time
   gap, fail-closed, tracked on its own ledger line.
4. **Evaluation-availability SLO not set.** Need real fleet duration/failure
   distributions after pilots. Max advisory age SLO **is** set (30 days, Q3).
5. **Published capability spec deferred to S8 archive** (GD-3 double-count
   measured; `2026-09-13-runner-monitor` precedent). IDs live in deltas.
6. **Envelope-only env defaults:** `hub/config.py` has no `coherence_*_root`
   defaults. Superseded by Phase-3 hub fetch when that lands.
7. **External enforcement boundary (coh-pol-07) is a repo-settings act.**
   Anti-rollback is in-tree; required-status-check / ruleset binding is
   operator action outside the repository.
8. **Stage 3 enforced-fleet-rollout sign-off is NOT given here.** That act
   is separate and remains open (`tasks.md` S8 line; inputs in
   `stage3-readiness.md`). This acceptance is the DEP-001 predecessor gate,
   not an authorization to enforce the gate on the fleet.

## What this unblocks

`devgate-product-tiers-fleet-manager` DEP-001 may now be considered met. The
package itself remains PROPOSED and ITS OWN "Do not implement this package
yet" instruction stands until Sprint 0 runs at whatever date-ordered position
the backlog queue gives it (2026-09-28 queue: after `consolidate-shared-gate-logic`
and the rest of the live backlog drain).

## Disposition of the remaining 3 checklist items in the package

| Item | Disposition |
|---|---|
| Publish `openspec/specs/spec-coherence-service/spec.md` | Stays open. Archive-time (S8), GD-3. |
| arm64 execution profile | Stays open as a hardware-gated line, not a pending action. |
| Stage 3 readiness review | Stays open. Owner sign-off for *enforced rollout*. Inputs assembled. |

No other checklist item remains open in the package.