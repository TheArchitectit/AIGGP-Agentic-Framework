# // spec: coh-eval-02, coh-assert-01, coh-assert-04, coh-eval-04, coh-pol-01, coh-rt-06
"""Assertion graph planning: schema completeness, duplicates, cycles, undeclared
inputs, planning-time traceability, complete-outcome accounting. Runs before
any evaluator.
"""
from . import evaluators, schemacheck


class PlanError(ValueError):
    """Planning failure (exit-30/31 class)."""


def _check_assertion(a: dict) -> None:
    # Repository-declared package content is untrusted (design.md "Repository
    # boundary"). Every shape rule that makes an assertion usable lives in the
    # frozen assertion.schema.json — so the schema is the check, loaded
    # through the runtime gate instead of a hand-rolled subset of it. A
    # non-dict entry (a specs/*.json that parses to a bare value) is a shape
    # violation, not an AttributeError.
    if not isinstance(a, dict):
        raise PlanError(f"assertion must be an object, got {type(a).__name__}")
    # The schema subsumes the old required-field loop (its `required` list) and
    # the empty-requirement_refs check (its minItems), so neither is repeated.
    errs = schemacheck.validate(a, schemacheck.load("assertion.schema.json"))
    if errs:
        raise PlanError(
            f"assertion {a.get('id', '?')!r} violates assertion.schema.json: "
            + "; ".join(errs[:5]))
    # Built-in allowlist, enforced at the planner (coh-rt-06 scenario: "WHEN
    # the planner resolves evaluators, THEN the reference is rejected").
    # Execution is decided solely by this lookup: the claimed evaluator
    # digest is declaration-only, never authority (mirrors coh-pol-02). The
    # schema validates the evaluator's shape; only this lookup decides whether
    # it may run.
    if a["evaluator"]["id"] not in evaluators.BUILTINS:
        raise PlanError(
            f"unapproved-evaluator:{a['evaluator']['id']} on assertion "
            f"{a['id']!r}: repository-supplied or unknown evaluators cannot "
            f"execute; only deterministic built-ins bundled in the pinned "
            f"image may run")



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
