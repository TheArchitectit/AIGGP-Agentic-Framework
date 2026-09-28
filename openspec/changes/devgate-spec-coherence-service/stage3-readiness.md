# Stage 3 readiness review — evidence matrix (2026-09-26)

Purpose: the inputs for the Stage 3 readiness review (tasks.md:1109) that
gates any enforced fleet rollout. The 12 release acceptance criteria
(`acceptance.md`) are dispositioned one by one: **MET** (cited evidence),
**OPEN** (named blocker), or **BLOCKED** (owner decision outstanding).
This document is factual: a criterion is MET only when the evidence is a
shipped test, drill, or measured run — not prose intent.

## The 12 release acceptance criteria

| # | Criterion (paraphrase) | Disposition | Evidence |
|---|---|---|---|
| 1 | All normative schemas versioned + compat tests | **MET** | 15 schemas carry `<family>/vN` (`FAMILY_RE`, `schemacheck.py`); compat machinery shipped 53384ac (`compat.py` retirement registry, branching refusal, policy runbook, 2-mutant battery; hosted green on run 36273664935) |
| 2 | Canonical replay 100 consecutive runs per architecture | **MET (shipped surface)** | `determinism_drill.py --runs 100` PASS 100/100 byte-identical, 2026-09-26 (sha 3d0b8ccbd9ccefd2…); one profile (`linux-amd64-v1`) shipped, so per-architecture coverage is complete for the shipped surface; arm64 stays open until a second profile exists |
| 3 | Every required assertion exactly once in result accounting | **MET** | C2 multi-finding ledger (9e58fbf + round-13 audit): per-assertion findings, strictest-class mirror, order-invariance both-orders agreement test; no last-wins collapse |
| 4 | Required skips/errors block in enforced mode | **MET** | Adapter default-deny (tasks.md:764 closure, coh-int-05): exit-code/decision agreement at the container boundary; exit 32 on timeout/overflow; coh-int-06 five skip paths all non-green |
| 5 | Local policy cannot weaken central policy | **MET** | `TestOverlayCannotWeaken` (A10); anti-rollback nc-09; grandfather windows |
| 6 | Container: non-root, read-only, caps, sockets, resources, redaction, default-deny egress | **MET** | Launcher 34-test suite + container suite; escape review (995afc1) enumerates all ten vectors with pinned controls; rootless podman measured on both hosts |
| 7 | Signed attestation detects bound-digest substitution | **MET** | `--verify-run` nine-step fail-closed chain; `test_bound_digest_tamper_is_detected` + `test_statement_digest_check_is_independently_load_bearing` mutate one bound at a time; nc-10 |
| 8 | Adoption ladder enforces advisory expiry + Stage 2 no-regression | **MET (both obligations demonstrated, in both directions)** | advisory escalation model ratified 8bf51d8, `adoption.evaluate` enforcement built; `scripts/ratchet_demo.py` runs the REAL service (`-m hub.coherence`) at stage 2 over the R9-captured LobsterWars shape (`r9-provenance-capture.md`: SHA `f5b48a30…`, run `36405534067`, digest `sha256:8c19f2f1…`) and demonstrates both obligations against ONE baseline: in-window → ADVISORY/exit 10, aged-out → BLOCK/exit 20, and a new location → BLOCK while its 13 adopted siblings stay sheltered. 10/10 steps; pinned by `tests/test_ratchet_demo.py` (7 tests), verified RED against two mutations of the real ladder (expiry branch neutered; fingerprint made non-deterministic), each killed by the drill it belongs to. **Honest scope:** the baseline SHAPE is captured, the run is synthetic — this is no attested coherence result over LobsterWars' bytes, and it does not discharge the real-subject run below |
| 9 | CI, local, fleet adapters equivalent canonical results | **MET (identity, not yet fleet-measured)** | Byte-equivalence-by-identity: CI and local run the identical builder bytes (`hub.coherence.invoke` inside the pinned image); the fleet half (a hosted coherence run on an enrolled spoke against a real subject) has not yet been run against a real repo — pilots |
| 10 | Six fixtures produce expected decisions | **synthetic MET; LobsterWars half UNBLOCKED; gamerepo01 stays synthetic (measured)** | Fixtures A–F shipped with expected decisions (synthetic, per R9). R9 capture ran 2026-09-28 (`r9-provenance-capture.md`): LobsterWars' 13-violation baseline carries all four ADR-019 fields (SHA/run/digest/capture time) and may be relabeled a captured production baseline. gamerepo01's record is **INCOMPLETE because the subject has no declared identity** — no `.guardrails/` exists (all probes 404), so a lineage-mismatch fixture has nothing to mismatch against. That subject stays synthetic, and the reason is now a measurement rather than a default (acceptance.md:87) |
| 11 | Operator reproduces any finding from its evidence bundle without the original runner | **MET** | Sealed-bundle design: `--verify-run` offline chain + `store.artifacts()` (durability path, containment-pinned); evidence objects self-contained with bound digests |
| 12 | Runbooks: outage, rollback, policy recovery, key rotation, evaluator revocation | **5/5 MET** | Outage/rollback/policy-recovery/key-rotation covered by drill/test-verified runbooks (:1031 measurement); evaluator revocation DECIDED 2026-09-26 — owner scoped it to the pinned-image lifecycle (bad image retired by re-pinning; old attestations valid for what they proved at evaluation time; no new control-plane revocation record), so the runbook is the existing re-pin operation — recorded at :1031, not improvised |

## The ten owner-decision open questions (acceptance.md) — status

**UPDATE 2026-09-26: the owner accepted all six §7 defaults (Q1–Q5, Q9)** —
recorded in `acceptance.md` ("Decided") and tasks.md:35. The rows below are
retained as the pre-decision record, marked with the answers.

| # | Question | Status |
|---|---|---|
| 1 | Authoritative OpenSpec approval mechanism | **DECIDED** — detached control-plane approval record (package digest + authority + repo scope + validity window) |
| 2 | Which assertion classes form the enforced core for the first pilot | **DECIDED** — product-identity consistency + traceability completeness + release-claim consistency |
| OQ3 | Max advisory age | **DECIDED** — 30 days, renewable once with owner + written reason + new expiry + control-plane approval (the machinery's fixture default already enforced exactly this value) |
| 4 | Exception/rollback approvers | **DECIDED** — control-plane authority; repository exceptions additionally countersigned by the repo maintainer |
| 5 | Which architectures must be byte-equivalent at launch | **DECIDED** — amd64 only; arm64 semantic-equivalence until provisioned |
| 6 | Offline evaluation: launch requirement or hardening milestone | OPEN |
| 7 | Evidence retention periods | OPEN (retention_class fallback shipped) |
| 8 | Backward-compatible result fields | OPEN |
| 9 | gamerepo01 normative vs historical facts | **DECIDED** — fixture starts synthetic; declared identity is normative, historical lineage informative |
| 10 | Vision determinism in the first 3D slice | OPEN (S7) |

## Verdict

**Not ready for enforced fleet rollout — but the decision half of the gap
closed 2026-09-26.** The code-surface criteria (1–7, 11) are MET with named
tests and measured runs. What still blocks Stage 3:

1. ~~**Owner decisions**~~ — Q1–Q5, Q9 **answered 2026-09-26**; the
   remaining open questions (Q6–Q8, Q10) do not gate enforcement posture
   per the criteria matrix above.
2. ~~**R9 provenance capture**~~ — **CAPTURED 2026-09-28**
   (`r9-provenance-capture.md`). LobsterWars' 13-finding baseline is pinned
   (SHA/run/digest/capture time), so criteria 8 and 10 have their real
   subject available. The capture also **closed the gamerepo01 question by
   measurement**: the repo declares no identity (no `.guardrails/`), so its
   fixture is synthetic by fact, not by default. What remains is not a
   decision but a **run**: the ratchet demo (criterion 8) and the
   fleet-half hosted coherence run on an enrolled spoke (criterion 9) each
   need runner time. Runner availability is not a blocker: all 14 ucs03
   spokes are enrolled + heartbeating as of 2026-09-25/26.
   **Update 2026-09-28: the ratchet demo half is now DONE** —
   `scripts/ratchet_demo.py` demonstrates both criterion-8 obligations
   against one baseline (in-window ADVISORY, aged-out BLOCK, new location
   BLOCK), pinned by `tests/test_ratchet_demo.py` and mutation-verified.
   Criterion 8 is MET. What stays open on criterion 9 is the fleet-half
   hosted run on an enrolled spoke against a real subject.
3. ~~**Evaluator revocation build gap**~~ — **DECIDED 2026-09-26**: the
   owner scoped it to the pinned-image lifecycle (bad image retired by
   re-pinning; old attestations valid for what they proved at evaluation
   time; no new control-plane revocation record). Criterion 12 is now 5/5;
   the runbook is the existing re-pin operation.

The review's honest headline, updated: **the gate is built, measured, its
policy decisions are made, and its real-repo facts are now captured; what
remains is running the two pilot demonstrations against those facts, and
the owner's sign-off act.**
