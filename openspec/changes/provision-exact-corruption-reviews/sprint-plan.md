# Sprint plan — provision exact corruption transition reviews

Use the [sprint dispatch guide](../../SPRINTS.md) with this package's [tasks](tasks.md), [proposal](proposal.md), [design](design.md), and active [reviewed-corruption-transitions delta](specs/reviewed-corruption-transitions/spec.md). The proposal explicitly leaves production controller provisioning, upstream approval and protected-CI rollout pending.

## Roles

- Lead: own the scope, review implementation evidence and decide integration readiness.
- Luna writer: work only on selected evaluator or fixture tasks; do not provision production authority.
- Independent auditor: separately replay exact-match, mismatch, revocation and strict-default controls from pinned inputs.
- Accountable owners: framework maintainer owns evaluator behavior; trusted controller/security owner owns protected catalog and per-run binding provisioning; upstream CI owner accepts protected rollout.

## Operating boundary

`--reviewed-transitions --range BASE..HEAD` is opt-in; ordinary invocations remain strict. This protected per-finding transition mode and the detached complete-range review in the [archived detached-review plan](../archive/2026-11-27-consume-detached-corruption-review/sprint-plan.md) are independent, mutually exclusive trusted alternatives. Neither mode may fall back to the other. A missing, stale, malformed, expired, mismatched, revoked or unreadable protected input fails closed. Catalog withdrawal/change invalidates a binding to the previous raw catalog digest. Matched findings remain visible as `EXCEPTION-ADVISORY`; unmatched findings, full-tree checks, secrets and configured mass-rewrite protections retain their ordinary behavior. No current record authorizes a real exception, and evaluator implementation alone is not production controller acceptance.

## S1 — baseline and acceptance boundary

- Pin the evaluator source, task state and exact test inputs. Map completed tasks 1.1–1.4 and 2.1–2.2 to evidence; keep tasks 2.3 and 3.1–3.3 open pending the independent security review and external owner decisions.
- Confirm fixed protected catalog/binding paths, immutable repository identity, exact full range, validity window and raw catalog digest from the active design. Record the authoritative owner and intended protected CI lane.
- Keep synthetic fixture authority separate from production credentials, repositories and deployment claims.
- Exit when a disposable fixture can express exact match, nearby mismatch, withdrawal/revocation and strict-default cases.

## S2 — evaluator and fixture evidence

- Replay task 2.2 against disposable Git objects and protected-store fixtures. Capture exact finding identity, ordered before/after blob IDs, line, advisory output and exit status.
- Exercise strict default, subject-supplied authority rejection, checkout/repository/range mismatch, missing/malformed/expired catalog or binding, digest change after issuance, and unmatched blocking finding.
- Demonstrate independent secret, full-tree and configured mass-rewrite behavior. The rootless CI smoke is fixture evidence only; it does not prove root-owned production provisioning or protected CI adoption.
- Keep tasks 2.3 and 3.x unchecked until their named independent review and owners supply evidence.

## S3 — independent qualification

- Auditor obtains the candidate and fixture receipts separately, verifies source and raw catalog digest, and reproduces positive and rejection outcomes.
- Confirm catalog withdrawal invalidates the old binding, current inputs are re-read before disposition, and the ordinary strict invocation stays strict.
- Inspect the focused suite and rootless smoke for meaningful assertions, then classify security review, production provisioning, upstream approval and rollout as passed only with their own receipts; otherwise report `NOT_RUN` or pending.
- Return a per-requirement verdict without treating synthetic fixture success as a real approval.

## S4 — integration and handoff

- Lead reconciles the audit and current tasks. Do not mark external tasks complete based only on the candidate implementation or rootless smoke.
- Handoff exact source/test SHA, catalog and binding fixture digests, positive and rejection receipts, independent verdict, CI job identity and outstanding controller/upstream decisions.
- Enable operational use or release a subject cleanup only after tasks 2.3 and 3.1–3.3 meet their stated owner and protected-CI conditions. Archive only through the OpenSpec ceremony.
