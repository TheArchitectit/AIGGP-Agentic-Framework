"""The publish job's stated trigger must be the trigger it has (img-cycle-06).

`container-publish` carries a comment promising it "Publishes ONLY on main
pushes and manual dispatch with publish=true" and an `if:` of
`github.event_name == 'push' && github.ref == 'refs/heads/main'`. Manual
dispatch never publishes. `workflow_dispatch:` IS a declared trigger of the
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

Deliberately carries no `// spec:` marker: img-cycle-06 lives in the
`add-runner-image-cycling` package and is not published yet, and marking this
file against it would manufacture the coverage the marker is meant to measure.
"""
import re
import sys
from pathlib import Path

import pytest
import yaml

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


def _triggers(workflow):
    """The `on:` mapping.

    YAML 1.1 reads a bare `on` as the boolean True, so `workflow["on"]` is a
    KeyError and `workflow.get("on")` is None — a fixture that got this wrong
    would report "workflow_dispatch is not a trigger" for a workflow that
    declares it, which is a false alarm about the safety of the publish path.
    Both spellings are accepted so the guard reads the file rather than the
    parser's opinion of it.
    """
    for key in ("on", True):
        if key in workflow:
            return workflow[key] or {}
    return {}


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def publish(workflow):
    job = workflow["jobs"].get("container-publish")
    assert job is not None, "the publish job is gone — this guard would be vacuous"
    assert "if" in job, "the publish job has no condition to check"
    return job


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

def test_publishing_is_deliberate(publish):
    """The requirement's own word: publish ONLY on a deliberate trigger. A push
    to main is not one — every merge is a publish, which is how the `:main` tag
    advanced past the recorded identity on consecutive runs with nothing to
    notice it (add-runner-image-cycling, proposal)."""
    cond = publish["if"]
    assert evaluate(cond, MAIN_PUSH) is False, \
        "a push to main still publishes — the tag advances past the record on every merge"
    assert evaluate(cond, DISPATCH_YES) is True, \
        "manual dispatch with publish=true does not publish — the comment promises it does"


def test_nothing_else_publishes(publish):
    cond = publish["if"]
    for name, event in (("a dispatch without the input", DISPATCH_NO),
                        ("a branch push", BRANCH_PUSH),
                        ("a tag push", TAG_PUSH),
                        ("a pull request", PULL_REQUEST)):
        assert evaluate(cond, event) is False, f"{name} publishes"


def test_a_string_typed_input_would_publish_on_every_dispatch():
    """The reason `type: boolean` is asserted rather than left to taste. This is
    the trap a well-meaning edit walks into: change the type to `string` and the
    default to "false", and `inputs.publish` is the non-empty string "false" —
    truthy — so the gate publishes on every dispatch, default included."""
    assert evaluate("inputs.publish", STRINGINPUT_NO) is True


def test_the_publish_input_is_declared(workflow, publish):
    """An `if:` reading an input nobody declared never fires again, and GitHub
    reports no error — the job is silently a no-op. This is the guard for the
    silence, not for the condition."""
    dispatch = _triggers(workflow).get("workflow_dispatch")
    assert dispatch is not None, "workflow_dispatch is not a trigger of this workflow"
    inputs = (dispatch or {}).get("inputs", {})
    assert "publish" in inputs, \
        "the condition reads inputs.publish but the workflow declares no such input"
    spec = inputs["publish"]
    assert spec.get("type") == "boolean", f"publish input is {spec.get('type')}, not boolean"
    assert spec.get("default") in (False, "false"), \
        "an input defaulting to true publishes on every dispatch"


# --- the documentation ------------------------------------------------------

def test_the_comment_and_the_condition_agree(comment, publish):
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
            assert evaluate(publish["if"], event) is True, (
                f"the comment names a {label} as a trigger and the condition "
                f"does not fire for one: {publish['if']}")
    assert checked, f"the comment names no trigger at all: {comment!r}"


def test_the_comment_names_the_deliberate_trigger(comment, publish):
    """img-cycle-06's second half: the documentation SHALL name the trigger
    exactly. Silence about the trigger is how the previous comment came to
    describe one that did not exist."""
    assert re.search(r"dispatch", comment.lower()), \
        f"the comment does not name manual dispatch: {comment!r}"
    assert re.search(r"inputs?\.publish|publish\s*=\s*true|publish:\s*true", comment.lower()), \
        f"the comment does not name the publish input: {comment!r}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
