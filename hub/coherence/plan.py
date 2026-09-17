# // spec: coh-eval-02, coh-assert-01, coh-assert-04, coh-pol-01
"""Assertion graph planning: schema completeness, duplicates, cycles, undeclared
inputs, planning-time traceability, complete-outcome accounting. Runs before
any evaluator.
"""


class PlanError(ValueError):
    """Planning failure (exit-30/31 class)."""


def _check_assertion(a: dict) -> None:
    required = ("id", "version", "requirement_refs", "owner", "requirement",
                "subjects", "evaluator", "severity", "dependencies", "evidence")
    for field in required:
        if field not in a:
            raise PlanError(f"assertion {a.get('id', '?')!r} missing {field!r}")
    if not a["requirement_refs"]:
        raise PlanError(f"assertion {a['id']!r} has no requirement_refs")


def check_traceability(assertions: list, requirements: dict) -> None:
    """Planning-time traceability (coh-assert-04), before any evaluator runs.

    Every assertion must reference requirements that actually exist in the
    package; every requirement marked testable must be claimed by at least one
    assertion. This is structural — it does not depend on evidence that would
    only exist after execution (that is the separate post-seal completeness
    check).
    """
    known = set(requirements or {})
    claimed = set()
    for a in assertions:
        for ref in a.get("requirement_refs", []):
            if known and ref not in known:
                raise PlanError(
                    f"assertion {a['id']!r} references unknown requirement {ref!r}")
            claimed.add(ref)
    for rid, meta in (requirements or {}).items():
        if meta.get("testable") and rid not in claimed:
            raise PlanError(
                f"testable requirement {rid!r} has no assertion (orphan)")


def plan(assertions: list, central_required: list, requirements: dict = None) -> list:
    """Validate and order the assertion graph. Returns planned assertions.

    central_required are assertion IDs central policy requires; a repository
    cannot omit them (coh-pol-01). When `requirements` is supplied, the
    planning-time traceability check runs first (coh-assert-04).
    """
    for a in assertions:
        _check_assertion(a)
    if requirements is not None:
        check_traceability(assertions, requirements)

    ids = [a["id"] for a in assertions]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise PlanError(f"duplicate assertion ids: {sorted(dupes)}")

    by_id = {a["id"]: a for a in assertions}
    # Central policy cannot be weakened by omission.
    for req in central_required:
        if req not in by_id:
            raise PlanError(
                f"centrally required assertion omitted from package: {req!r}")

    # Dependency resolution and cycle detection.
    planned = []
    state = {}  # id -> 0 unvisited, 1 in-progress, 2 done

    def visit(aid: str, stack: list) -> None:
        s = state.get(aid, 0)
        if s == 2:
            return
        if s == 1:
            raise PlanError(f"dependency cycle: {' -> '.join(stack + [aid])}")
        if aid not in by_id:
            raise PlanError(f"dependency on unknown assertion: {aid!r}")
        state[aid] = 1
        for dep in by_id[aid]["dependencies"]:
            visit(dep, stack + [aid])
        state[aid] = 2
        planned.append(by_id[aid])

    for a in assertions:
        visit(a["id"], [])

    return planned
