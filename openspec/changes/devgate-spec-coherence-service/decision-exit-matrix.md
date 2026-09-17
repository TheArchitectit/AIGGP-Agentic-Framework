# Decision and exit-code matrix

**Status:** frozen contract candidate · governs coh-dec-01, coh-dec-04, coh-dec-05, coh-eval-02.

This is the single published total ordering. Every stage × outcome × error-class combination resolves to exactly one decision and one exit code. Within a run, ERROR-class conditions dominate FAIL-class; the result records all condition classes so the dominant one is explainable. Exit/result disagreement always resolves to the less permissive signal (i.e., ERROR for the caller).

## Outcome classes

| Class | Members | Exit | Decision |
|---|---|---|---|
| `ERROR-invalid-input` | bad request schema, unsupported api_version is separate (40), missing/invalid subject or package, path traversal, normalization collision, input mutation during evaluation | 30 | ERROR |
| `ERROR-policy` | policy resolution failure, untrusted policy/context, anti-rollback rejection, **overlay that weakens central policy (disable required / lower severity / unapproved evaluator / capability grant / unknown severity)**, malformed policy or overlay | 31 | ERROR |
| `ERROR-execution` | evaluator crash, limit exhaustion, incomplete ledger, dependency-blocked required assertion | 32 | ERROR |
| `ERROR-evidence` | evidence sealing failure, attestation/signing failure, verification failure on tamper | 33 | ERROR |
| `ERROR-protocol` | unsupported `api_version` | 40 | ERROR |
| `FAIL` | ≥1 enforced assertion VIOLATED or UNRESOLVED (evaluation completed cleanly), expired-exception on required assertion | 20 | FAIL |
| `ADVISORY` | ≥1 assertion VIOLATED/UNRESOLVED but current stage does not block | 10 | ADVISORY |
| `PASS` | all required assertions SATISFIED; advisory findings only where policy permits | 0 | PASS |

## Stage interplay

| Stage | Violated (enforced) | Violated (advisory) | Unresolved (enforced) | Any ERROR-class |
|---|---|---|---|---|
| 0 Inventory | records finding; no release decision changed | ADVISORY | records; no authorization | ERROR, blocks authorization report |
| 1 Advisory | ADVISORY | ADVISORY | ADVISORY | ERROR |
| 2 Ratchet | FAIL if new/not-in-baseline; ADVISORY if named baseline | ADVISORY | FAIL | ERROR |
| 3 Enforced core | FAIL | ADVISORY | FAIL | ERROR |
| 4 Enforced full | FAIL | FAIL (no advisory class remains) | FAIL | ERROR |

Stage 0 ERROR never produces a coherence authorization — it records the failure for inventory only.

## Tie-breaking rules

1. Multiple ERROR-class conditions → lowest exit code wins (30 < 31 < 32 < 33 < 40); all classes recorded in the error envelope's `error.class` history is NOT required — the envelope names the dominant class and `stage`; the full ledger records each affected assertion's reason code.
2. ERROR + FAIL together → ERROR dominates; result still records the VIOLATED ledger entries.
3. FAIL + ADVISORY → FAIL.
4. Expired exception on a required assertion → FAIL (not ERROR); exception expiry is a policy outcome evaluated against context `evaluation_time`.
5. Skipped required assertion → never PASS; recorded UNRESOLVED with reason `skipped`, treated per stage as FAIL (enforced) or ADVISORY.

## Caller contract

- Use both exit code and parsed result; never either alone.
- Missing or malformed result with any exit code → ERROR for the caller.
- Exit/result disagreement → ERROR for the caller.
- A promotion consumer promotes only on decision `PASS` (or `ADVISORY` where policy accepts it for the stage) AND a parseable canonical result AND a verifying detached attestation (from Stage 2 onward).
