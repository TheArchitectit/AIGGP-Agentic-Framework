"""Every CI job is guarded before a runner is assigned (R19-13 for AIGGP).

This repository's CI runs on the UCS03 fleet. Same-repository pull requests run
there too — the owner's routing decision — which means the one thing that must
never happen is contributor code from a FORK executing on the private pool.

A job-level `if:` is evaluated by GitHub *before* it picks a runner, so a job
carrying

    github.event_name != 'pull_request' ||
    github.event.pull_request.head.repo.full_name == github.repository

is skipped for a fork PR rather than dispatched. The guard has to be on EVERY
job of a workflow that declares `pull_request`: one unguarded job is enough to
put untrusted code on the host. `pull_request_target` is not acceptable as an
alternative — it runs the base repository's workflow against a PR-controlled
checkout with a writable token.

The tests read the file with `tests/workflow_read.py` (no PyYAML dependency in
this repository) and EVALUATE the condition against event payloads, because a
string comparison on an `if:` cannot tell a guard from its inversion: swapping
`||` for `&&` leaves every token in place and skips every push run.

Non-vacuity: the job list must be non-empty and `ci.yml` must really declare
`pull_request`, or the per-job loop would pass over nothing.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_read as wr  # noqa: E402
from test_publish_trigger import evaluate  # noqa: E402  (one evaluator, not two)

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"

FORK_GUARD = ("github.event_name != 'pull_request' || "
              "github.event.pull_request.head.repo.full_name == github.repository")

REPOSITORY = "TheArchitectit/DevGate-Agentic-Framework"

PUSH = {"event_name": "push", "repository": REPOSITORY}
DISPATCH = {"event_name": "workflow_dispatch", "repository": REPOSITORY, "inputs": {}}
SAME_REPO_PR = {
    "event_name": "pull_request",
    "repository": REPOSITORY,
    "event": {"pull_request": {"head": {"repo": {"full_name": REPOSITORY}}}},
}
FORK_PR = {
    "event_name": "pull_request",
    "repository": REPOSITORY,
    "event": {"pull_request": {"head": {"repo": {"full_name": "someone/fork"}}}},
}


def _normalise(expr):
    return " ".join(str(expr or "").split())


@pytest.fixture(scope="module")
def workflow():
    return wr.read_workflow(CI.read_text(encoding="utf-8"))


def test_this_workflow_really_declares_pull_request(workflow):
    """The premise. Without it the per-job loop would be a scan of nothing."""
    assert "pull_request" in workflow.triggers, \
        "ci.yml does not declare `pull_request` — the fork-guard rule has nothing to guard"


def test_pull_request_target_is_not_used(workflow):
    """Base-repo workflow + PR-controlled checkout + writable token. There is no
    safe use of it here, so the trigger is refused outright."""
    assert "pull_request_target" not in workflow.triggers, \
        "ci.yml declares `pull_request_target` — that runs base-repo code against PR code"


def test_every_job_carries_the_canonical_fork_guard(workflow):
    jobs = workflow.jobs
    assert jobs, "ci.yml declares no jobs — the guard loop is vacuous"
    missing = []
    for job in sorted(jobs):
        try:
            condition = workflow.job_if(job)
        except wr.WorkflowReadError:
            missing.append(f"{job} (no `if:` at all)")
            continue
        if _normalise(FORK_GUARD) not in _normalise(condition):
            missing.append(f"{job} (`if: {condition}`)")
    assert not missing, (
        "these jobs of a pull_request workflow lack the fork guard, so a fork "
        "PR's jobs would be dispatched to the private runner: " + "; ".join(missing))


def test_the_guard_skips_a_fork_pull_request():
    assert evaluate(FORK_GUARD, FORK_PR) is False, \
        "a fork PR would match the guard and run on the private runner"


def test_the_guard_admits_a_same_repository_pull_request():
    assert evaluate(FORK_GUARD, SAME_REPO_PR) is True, \
        "a same-repository PR is skipped — same-repo PRs are meant to run on the fleet"


def test_the_guard_admits_pushes_and_dispatches():
    assert evaluate(FORK_GUARD, PUSH) is True, "a push is skipped by the guard"
    assert evaluate(FORK_GUARD, DISPATCH) is True, "a dispatch is skipped by the guard"


def test_the_inverted_operator_is_not_the_guard():
    """`&&` in place of `||` leaves every token where it was and inverts the
    meaning: every push run would be skipped. Prose comparison cannot see it;
    evaluation can."""
    inverted = FORK_GUARD.replace("||", "&&")
    assert evaluate(inverted, PUSH) is False
    assert _normalise(inverted) != _normalise(FORK_GUARD)


def test_the_guard_is_the_first_condition_of_each_job(workflow):
    """`(guard) && (job's own condition)` is the required shape. A job whose own
    condition comes first still evaluates correctly, but a later edit that
    appends to the condition is more likely to drop the guard; the canonical
    string must appear as the leading clause."""
    for job in sorted(workflow.jobs):
        condition = _normalise(workflow.job_if(job)).lstrip("(")
        assert condition.startswith(_normalise(FORK_GUARD)), \
            f"{job} does not lead with the fork guard: `if: {condition}`"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
