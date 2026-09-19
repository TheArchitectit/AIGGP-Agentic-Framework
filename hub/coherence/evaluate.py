# // spec: coh-eval-06, coh-rt-05, coh-rt-06, coh-eval-02, coh-rt-03, coh-ctx-04
"""Evaluator runtime: built-in evaluators only, declared-inputs-only mediation,
limits/crash/dependency-block -> ERROR-execution, complete-outcome accounting.
No repository executable code, no network, no secrets.
"""
from . import evaluators


class EvaluatorError(RuntimeError):
    """Evaluator/execution failure (exit-32 class)."""


def _mediated_call(fn, assertion, package, subject_root, facts):
    # Declared-inputs-only mediation (coh-eval-06): the evaluator receives
    # only the package content, the subject root it declared, and the captured
    # facts its subjects declared (digest-verified by the context loader).
    # Built-ins do not receive ambient environment, clock, or network.
    return fn(assertion, package, subject_root, facts)


def run(planned: list, package: dict, subject_root: str, limits: dict = None,
        captured_facts: dict = None) -> dict:
    """Execute planned assertions. Returns ledger + findings.

    limits: {"max_evaluators": int} — a bound; exhaustion is ERROR.
    captured_facts: {fact_id: verified content} from the context loader. Each
    evaluator is exposed ONLY the facts its own subjects declared; a declared
    fact that is not bound is UNRESOLVED, never SATISFIED (coh-rt-03).

    The return carries `error` — set when an ERROR-execution condition
    occurred (frozen matrix: evaluator crash or dependency-blocked required
    assertion). The affected ledger rows stay recorded as UNRESOLVED, but the
    run-level decision is ERROR/32: it dominates any FAIL-class condition in
    the same run (tie-break 2) and is never downgraded to advisory.
    """
    limits = limits or {}
    captured_facts = captured_facts or {}
    max_evals = limits.get("max_evaluators", 10_000)
    if len(planned) > max_evals:
        raise EvaluatorError(
            f"planned {len(planned)} evaluators exceeds limit {max_evals}")

    ledger = []
    findings = []
    done = {}  # assertion_id -> outcome
    error = None  # first ERROR-execution condition, if any (frozen matrix)

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

        # Captured-fact mediation (coh-rt-03): scope exposure to the declared
        # fact ids; an unbound declared fact cannot satisfy.
        declared_facts = [s.get("fact_id") for s in a["subjects"]
                          if isinstance(s, dict)
                          and s.get("kind") == "captured-fact"]
        missing = next((fid for fid in declared_facts
                        if not isinstance(fid, str) or fid not in captured_facts),
                       None)
        if missing is not None:
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED",
                "reason": f"captured-fact-missing:{missing}",
                "enforcement": "BLOCK",
            })
            done[a["id"]] = "UNRESOLVED"
            continue
        facts = {fid: captured_facts[fid] for fid in declared_facts}

        # Dependency-blocked: a dependency that did not SATISFY blocks this
        # one. Frozen matrix: an ERROR-execution condition, not FAIL-class.
        dep_block = next((d for d in a["dependencies"] if done.get(d) != "SATISFIED"), None)
        if dep_block is not None:
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED", "reason": "dependency-blocked",
                "enforcement": "BLOCK",
            })
            if error is None:
                error = {"class": "execution",
                         "reason": f"dependency-blocked:{a['id']}"}
            done[a["id"]] = "UNRESOLVED"
            continue

        try:
            fs = _mediated_call(fn, a, package, subject_root, facts)
        except evaluators.Unresolved as e:
            # Unresolvable input (coh-assert-02) — distinct from a crash:
            # evaluation completed cleanly, so this stays FAIL-class.
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED", "reason": e.reason,
                "enforcement": "BLOCK",
            })
            done[a["id"]] = "UNRESOLVED"
            continue
        except Exception as e:  # evaluator crash -> ERROR-execution (matrix)
            ledger.append({
                "assertion_id": a["id"], "version": a["version"],
                "outcome": "UNRESOLVED", "reason": f"evaluator-crash:{type(e).__name__}",
                "enforcement": "BLOCK",
            })
            if error is None:
                error = {"class": "execution",
                         "reason": f"evaluator-crash:{type(e).__name__}:{a['id']}"}
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

    return {"ledger": ledger, "findings": findings, "error": error}
