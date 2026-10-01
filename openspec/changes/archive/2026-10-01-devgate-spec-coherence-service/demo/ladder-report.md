# S3 ladder demo — acceptance Fixture C through the real CLI

**Date:** 2026-09-17 · **World:** SYNTHETIC (R9 provenance rule) — 13 identity
assertions violated at once, baseline of 13 named fingerprints. This models the
advisory-debt CLASS; it is not LobsterWars data and must not be represented as
a captured production baseline.

Driven by `python -m hub.coherence --request ...` (the shipped CLI), not unit
mocks. Test suite: `tests/test_hub_coherence_ladder.py` (8 tests).

| scenario | exit | decision | BLOCK / ADVISORY / EXC-ADVISORY findings | expected |
|---|---|---|---|---|
| Stage 1 (advisory baseline) | 10 | ADVISORY | 0 / 13 / 0 | 10 ADVISORY 0/13/0 |
| Stage 2, 13 named debts unchanged | 10 | ADVISORY | 0 / 13 / 0 | 10 ADVISORY 0/13/0 |
| Stage 2 + one NEW violation (13+1) | 20 | FAIL | 1 / 13 / 0 | 20 FAIL 1/13/0 |
| Stage 2, one EXPIRED exception | 20 | FAIL | 1 / 12 / 0 | 20 FAIL 1/12/0 |
| Stage 2, one LIVE exception | 10 | ADVISORY | 0 / 12 / 1 | 10 ADVISORY 0/12/1 |
| Stage 2, WILDCARD exception | 31 | ERROR | (no result — envelope at request dir) | 31 invalid policy |

All six scenarios match acceptance Fixture C. Additional pinned properties
(tests, not table rows):

- underlying truth preserved at Stage 1: summary violated == ledger VIOLATED
  count (coh-eval-05) — advisory enforcement never rewrites outcomes;
- expired-exception ledger entry stays `VIOLATED` with enforcement BLOCK
  (coh-pol-06);
- pilot path via `issue_context`: baseline bound at issuance; a post-issuance
  set swap fails closed at exit 31 (coh-ctx-01);
- documented boundary: UNBOUND sets are re-read silently — pilots must bind
  (pinned so the protection's scope is explicit, not assumed);
- the classic trap from ADR-006 — 13 fixed + 13 new at constant count — is
  covered by `test_one_fixed_one_new_at_constant_count_blocks` (exitcodes file)
  at smaller N; the ladder's stage-2-plus-new case exercises the same
  fingerprint-set logic at 13.

**LobsterWars anti-goal status:** the demo shows the only steady state the
ladder permits: debt either gets remediated, gets an expiring exception, or
escalates to a block at its cap (report.summarize flags age/expiry for
visibility, coh-pol-03).
