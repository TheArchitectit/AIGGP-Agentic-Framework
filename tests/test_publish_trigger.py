"""The publish job's stated trigger must be the trigger it has (img-cycle-06).

`container-publish` carried a comment promising it "Publishes ONLY on main
pushes and manual dispatch with publish=true" over an `if:` of
`github.event_name == 'push' && github.ref == 'refs/heads/main'`. Manual
dispatch never published. `workflow_dispatch:` IS a declared trigger of the
workflow, so the operator's reading of that comment is not a typo they will
notice — they dispatch, the job is skipped, and the run is green.

Two hazards, and the second is the one that bites silently:

  * A comment describing a condition the job does not have is false
    documentation in a release path, which is a defect whichever policy is
    chosen (`add-runner-image-cycling` design D6).
  * An `if:` that reads `inputs.publish` when no such input is declared
    evaluates the reference to null, the condition is false on every event, and
    **the job never runs again** — with no error from GitHub, because an
    undeclared input is not a malformed expression. That is the shape this file
    exists to catch, and it is why the input's declaration is asserted rather
    than assumed.

These tests EVALUATE the condition against event payloads rather than matching
its text. The previous package learned the difference the hard way: prose
assertions survived an `if false;` mutation because the asserted string was
still where it was. An evaluator is only worth having if it is itself
exercised, so `test_the_evaluator_agrees_with_a_condition_whose_meaning_is_known`
pins it against the old condition, whose truth table is not in question.

The file is read by `tests/workflow_read.py`, not PyYAML — and that is a
finding, not a preference. The first push of this guard imported yaml, and the
hosted lane installs only pytest, so collection aborted and all 906 tests died
with it: one module-level import took the whole suite down, exactly the failure
`add-secret-scanning` tasks 6.3 already records. Nothing in this repository
depends on PyYAML. The reader is guarded by `test_workflow_read.py`.

Deliberately carries no `// spec:` marker: img-cycle-06 lives in the
`add-runner-image-cycling` package and is not published yet, and marking this
file against it would manufacture the coverage the marker is meant to measure.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_read as wr  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"

# Event payloads, as `github` sees them. A `type: boolean` dispatch input
# arrives as a boolean; a `type: string` one would arrive as the string
# "false", and a non-empty string is TRUTHY in a GitHub expression — so a
# string-typed input defaulting to "false" publishes on every dispatch. That
# is why the declared type is asserted below rather than assumed.
MAIN_PUSH = {"event_name": "push", "ref": "refs/heads/main"}
BRANCH_PUSH = {"event_name": "push", "ref": "refs/heads/dev"}
TAG_PUSH = {"event_name": "push", "ref": "refs/tags/v1.2.3"}
PULL_REQUEST = {"event_name": "pull_request", "ref": "refs/pull/7/merge"}
DISPATCH_NO = {"event_name": "workflow_dispatch", "inputs": {"publish": False}}
DISPATCH_YES = {"event_name": "workflow_dispatch", "inputs": {"publish": True}}
STRINGINPUT_NO = {"event_name": "workflow_dispatch", "inputs": {"publish": "false"}}


def _translate(expr):
    """GitHub expression syntax -> Python, for the subset an `if:` uses here.

    Deliberately minimal: `github.foo` becomes `g("foo")`, `&&`/`||`/`!` become
    their Python operators, and nothing else is rewritten. Anything outside that
    subset raises at eval time rather than being silently dropped — a condition
    this evaluator cannot read must fail the test, not pass it.
    """
    # Only outside single-quoted literals: a `'...'` here is a value being
    # compared, not a reference to resolve.
    parts = re.split(r"('[^']*')", expr)
    for i, part in enumerate(parts):
        if part.startswith("'"):
            continue
        part = re.sub(r"\bgithub\.([A-Za-z_][A-Za-z0-9_.]*)", r'g("\1")', part)
        # A bare `inputs.publish` is valid in an `if:` and is how the publish
        # condition reads its input — the reference GitHub resolves to null
        # when the input is undeclared.
        part = re.sub(r"\binputs\.([A-Za-z_][A-Za-z0-9_.]*)", r'g("inputs.\1")', part)
        parts[i] = part
    out = "".join(parts)
    out = out.replace("&&", " and ").replace("||", " or ")
    out = re.sub(r"!(?!=)", " not ", out)
    return out


def evaluate(expr, event):
    """Does this `if:` fire for this event? Raises if it cannot be read."""
    def g(path):
        cur = event
        for part in path.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                # GitHub treats a reference to a missing property as null, and
                # a null in a comparison is false rather than an error. This is
                # exactly how an undeclared `inputs.publish` disables a job.
                return None
        return cur

    return bool(eval(_translate(expr), {"g": g, "__builtins__": {}}))  # noqa: S307


@pytest.fixture(scope="module")
def workflow():
    return wr.read_workflow(CI.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def condition(workflow):
    """The publish job's `if:`, or a failure naming what is missing.

    `job_if` raises for an absent job, an absent condition, and a block scalar
    rather than returning "" — a guard handed an empty condition would evaluate
    it as false and report the publish job as deliberately quiet.
    """
    assert "container-publish" in workflow.jobs, \
        "the publish job is gone — this guard would be vacuous"
    return workflow.job_if("container-publish")


@pytest.fixture(scope="module")
def comment():
    """The prose block immediately above `container-publish:`, which is where
    the trigger is described."""
    lines = CI.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("  container-publish:"))
    block = []
    for line in reversed(lines[:start]):
        if line.strip().startswith("#"):
            block.append(line.strip().lstrip("#").strip())
        elif line.strip():
            break
    return " ".join(reversed(block))


# --- the evaluator itself ---------------------------------------------------

def test_the_evaluator_agrees_with_a_condition_whose_meaning_is_known():
    """Without this, a broken evaluator would make every claim below vacuous.

    The condition here is the one the job had before this change (push to main
    only), whose truth table is not in question."""
    old = "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert evaluate(old, MAIN_PUSH) is True
    assert evaluate(old, DISPATCH_YES) is False
    assert evaluate(old, BRANCH_PUSH) is False
    assert evaluate(old, TAG_PUSH) is False


def test_the_evaluator_reads_a_missing_property_as_null_not_an_error():
    """The undeclared-input shape. `inputs.publish` on a payload with no
    `inputs` is null, and null makes the condition false."""
    assert evaluate("github.event_name == 'workflow_dispatch' && inputs.publish",
                    DISPATCH_YES) is True
    assert evaluate("github.event_name == 'workflow_dispatch' && inputs.publish",
                    MAIN_PUSH) is False


def test_the_evaluator_refuses_a_condition_it_cannot_read():
    with pytest.raises(Exception):
        evaluate("github.event_name =~ 'push'", MAIN_PUSH)


# --- the condition ----------------------------------------------------------

def test_publishing_is_deliberate(condition):
    """The requirement's own word: publish ONLY on a deliberate trigger. A push
    to main is not one — every merge is a publish, which is how the `:main` tag
    advanced past the recorded identity on consecutive runs with nothing to
    notice it (add-runner-image-cycling, proposal)."""
    assert evaluate(condition, MAIN_PUSH) is False, \
        "a push to main still publishes — the tag advances past the record on every merge"
    assert evaluate(condition, DISPATCH_YES) is True, \
        "manual dispatch with publish=true does not publish — the comment promises it does"


def test_nothing_else_publishes(condition):
    for name, event in (("a dispatch without the input", DISPATCH_NO),
                        ("a branch push", BRANCH_PUSH),
                        ("a tag push", TAG_PUSH),
                        ("a pull request", PULL_REQUEST)):
        assert evaluate(condition, event) is False, f"{name} publishes"


def test_a_string_typed_input_would_publish_on_every_dispatch():
    """The reason `type: boolean` is asserted rather than left to taste. This is
    the trap a well-meaning edit walks into: change the type to `string` and the
    default to "false", and `inputs.publish` is the non-empty string "false" —
    truthy — so the gate publishes on every dispatch, default included."""
    assert evaluate("inputs.publish", STRINGINPUT_NO) is True


def test_the_publish_input_is_declared(workflow):
    """An `if:` reading an input nobody declared never fires again, and GitHub
    reports no error — the job is silently a no-op. This is the guard for the
    silence, not for the condition."""
    assert "workflow_dispatch" in workflow.triggers, \
        "workflow_dispatch is not a trigger of this workflow"
    spec = workflow.dispatch_input("publish")
    assert spec.get("type") == "boolean", \
        f"publish input is typed {spec.get('type')!r}, not boolean — a string " \
        f"input defaulting to \"false\" is truthy and publishes every dispatch"
    # The reader returns the scalar as written (unquoted), so this pins the
    # literal. `true`, `yes`, `1` and any other spelling of a true default all
    # fail here, which is the property that matters: a default of true
    # publishes on every dispatch, ticked or not.
    assert spec.get("default", "").strip().lower() == "false", \
        f"the publish input defaults to {spec.get('default')!r}, not false — " \
        f"an unticked dispatch would publish"


# --- the documentation ------------------------------------------------------

def test_the_comment_and_the_condition_agree(comment, condition):
    """The requirement's scenario: a comment claiming manual dispatch while the
    condition fires only on push. Each trigger the comment NAMES must actually
    behave the way the comment says, so the claim is checked behaviourally
    rather than by reading well."""
    named = {
        "main push": (r"main push", MAIN_PUSH),
        "manual dispatch": (r"dispatch", DISPATCH_YES),
    }
    lowered = comment.lower()
    checked = 0
    for label, (pattern, event) in named.items():
        if re.search(pattern, lowered):
            checked += 1
            assert evaluate(condition, event) is True, (
                f"the comment names a {label} as a trigger and the condition "
                f"does not fire for one: {condition}")
    assert checked, f"the comment names no trigger at all: {comment!r}"


def test_the_comment_names_the_deliberate_trigger(comment, condition):
    """img-cycle-06's second half: the documentation SHALL name the trigger
    exactly. Silence about the trigger is how the previous comment came to
    describe one that did not exist."""
    assert re.search(r"dispatch", comment.lower()), \
        f"the comment does not name manual dispatch: {comment!r}"
    assert re.search(r"inputs?\.publish|publish\s*=\s*true|publish:\s*true", comment.lower()), \
        f"the comment does not name the publish input: {comment!r}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
