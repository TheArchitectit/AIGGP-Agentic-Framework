#!/usr/bin/env python3
"""Mutation battery for the publish job's trigger (img-cycle-06).

The subject is a condition and the comment describing it. The guards that read
it EVALUATE the condition against event payloads rather than matching its text,
because the previous package learned what prose assertions cost: four mutants
survived a suite whose assertions were string comparisons on a step body, since
an `if false;` edit leaves the asserted string exactly where it was.

So what is mutated here is meaning, not wording:

  * the condition's policy (who publishes),
  * the input it reads (declared, typed, defaulted),
  * the comment's claim, which has to keep agreeing with the condition.

The comment mutation is deliberately in the battery: `test_the_comment_and_the_
condition_agree` is the only guard that can see it, and a battery that skipped
it would leave the requirement's own scenario — "a comment claiming manual
dispatch while its `if:` fires only on push" — unpinned.

The artifacts are YAML, whose well-formedness the shared harness checks: a
mutation that breaks the file makes every test fail at collection, and a harness
reading only the exit code would report that as a kill.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

CI = ".github/workflows/ci.yml"
T_TRIGGER = "tests/test_publish_trigger.py"

DELIBERATE = "if: github.event_name == 'workflow_dispatch' && inputs.publish"
PUSH_ONLY = "if: github.event_name == 'push' && github.ref == 'refs/heads/main'"

INPUT_DECL = """      publish:
        description: "Build and push the evaluator image to GHCR"
        type: boolean
        default: false"""
INPUT_STRING = """      publish:
        description: "Build and push the evaluator image to GHCR"
        type: string
        default: "false\""""

COMMENT_DELIBERATE = "Publishes ONLY on manual dispatch with inputs.publish=true"
COMMENT_PUSH = "Publishes ONLY on main pushes and manual dispatch with publish=true"

MUTATIONS = [
    # P1 — the policy itself, reverted. The whole point of the change: a merge
    # to main publishing again is the drift the proposal measured.
    ("P1: the condition goes back to publishing on every push to main",
     [(CI, DELIBERATE, PUSH_ONLY)], [T_TRIGGER], {}),

    # P2 — the deliberate half dropped. Dispatch publishes whatever the input
    # says, which is the unticked default.
    ("P2: the publish input is dropped from the condition",
     [(CI, DELIBERATE, "if: github.event_name == 'workflow_dispatch'")],
     [T_TRIGGER], {}),

    # P3 — the event half weakened from && to ||. Dispatch-without-the-input
    # publishes, and so does anything whose event_name matches.
    ("P3: the condition's `&&` weakens to `||`",
     [(CI, DELIBERATE, "if: github.event_name == 'workflow_dispatch' || inputs.publish")],
     [T_TRIGGER], {}),

    # P4 — the input deleted. The condition then references an undeclared
    # input, evaluates to null, and the job never runs again — silently, with
    # no error from GitHub. This is the mutation the file is named for.
    ("P4: the publish input is no longer declared",
     [(CI, INPUT_DECL, "      publish_moved: {}")], [T_TRIGGER], {}),

    # P5 — the input declared as a string. "false" is a non-empty string, and a
    # non-empty string is truthy, so the gate publishes on every dispatch
    # including the default one.
    ("P5: the publish input is typed as a string, so \"false\" is truthy",
     [(CI, INPUT_DECL, INPUT_STRING)], [T_TRIGGER], {}),

    # P6 — the default inverted. Every dispatch publishes, ticked or not.
    ("P6: the publish input defaults to true",
     [(CI, INPUT_DECL, INPUT_DECL.replace("default: false", "default: true"))],
     [T_TRIGGER], {}),

    # P7 — the comment's claim, restored to the one that did not exist. Pairs
    # with P1 only in the direction that matters: here the condition is
    # correct and the DOCUMENTATION is false, which is the requirement's own
    # scenario and the state this change started from.
    ("P7: the comment claims a trigger the condition does not have",
     [(CI, COMMENT_DELIBERATE, COMMENT_PUSH)], [T_TRIGGER], {}),
]

# Must SURVIVE. The comment reworded to say the same thing: the guard that
# reads it resolves claims to event payloads, so a rewording that keeps the
# claim cannot fail — and a battery whose comment mutation killed THIS too
# would be pinning prose rather than meaning, which is the defect the sibling
# battery was written to stop repeating.
NEGATIVE_CONTROLS = [
    ("N1: the comment reworded, claiming exactly the same trigger",
     [(CI, COMMENT_DELIBERATE,
       "publishes ONLY when dispatched by hand with inputs.publish=true")],
     [T_TRIGGER], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it proves the comment guard reads meaning, not wording"))
