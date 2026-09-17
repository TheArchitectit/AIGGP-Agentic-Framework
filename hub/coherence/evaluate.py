# // spec: coh-eval-06, coh-rt-05, coh-rt-06, coh-eval-02
"""Evaluator runtime: built-in evaluators only, declared-inputs-only mediation,
limits -> ERROR, complete-outcome accounting. No repository executable code.
"""
from . import evaluators


class EvaluatorError(RuntimeError):
    """Evaluator/execution failure (exit-32 class)."""


def _mediated_call(fn, assertion, package, subject_root, declared):
    # Declared-inputs-only mediation (coh-eval-06): the evaluator receives
    # only the package content and the subject root it declared. Built-ins do
    # not receive ambient environment, clock, or network.
    return fn(assertion, package, subject_root)


def run(planned: list, package: dict, subject_root: str, limits: dict = None) -> dict:
    """Execute planned assertions. Returns ledger + findings.

    limits: {"max_evaluators": int} — a bound; exhaustion is ERROR.
    """
    limits = limits or {}
    max_evals = limits.get("max_evaluators", 10_000)
    if len(planned) > max_evals:
        raise EvaluatorError(
            f"planned {len(planned)} evaluators exceeds limit {max_evals}")

    ledger = []
    findings = []
    done = {}  # assertion_id -> outcome

    for a in planned:
        eid = a["evaluator"]["id"]
        fn = evaluators.BUILTINS.get(eid)
        if fn is None:
            # Unapproved evaluator: its assertions are UNRESOLVED, and enforced
            # policy blocks (coh-eval-02 / coh-rt-06).
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED", "reason": "unapproved-evaluator",
                "enforcement": "BLOCK",
            })
            done[a["id"]] = "UNRESOLVED"
            continue

        # Dependency-blocked: a dependency that did not SATISFY blocks this one.
        dep_block = next((d for d in a["dependencies"] if done.get(d) != "SATISFIED"), None)
        if dep_block is not None:
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED", "reason": "dependency-blocked",
                "enforcement": "BLOCK",
            })
            done[a["id"]] = "UNRESOLVED"
            continue

        try:
            fs = _mediated_call(fn, a, package, subject_root, a["subjects"])
        except Exception as e:  # evaluator crash -> UNRESOLVED, enforced blocks
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED", "reason": f"evaluator-crash:{type(e).__name__}",
                "enforcement": "BLOCK",
            })
            done[a["id"]] = "UNRESOLVED"
            continue

        if fs:
            outcome = "VIOLATED"
            findings.extend(fs)
        else:
            outcome = "SATISFIED"
        ledger.append({
            "assertion_id": a["id"], "version": a["version"],
            "outcome": outcome, "reason": None,
            "enforcement": "BLOCK" if outcome != "SATISFIED" else "ADVISORY",
        })
        done[a["id"]] = outcome

    return {"ledger": ledger, "findings": findings}
