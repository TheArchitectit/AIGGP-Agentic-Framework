"""The stored toolchain record's shape, and what the hub makes visible from it.

Split out of `test_hub_toolchain_requests.py` by DevGate's own 600-line hard limit
for test files, the same way `test_hub_toolchain_requests_wire.py` was split out
before it and `test_runner_heartbeat_image.py` before that: the honest response to
the limit in this repository has been to move the tests to where their subject is,
never to widen the limit or to drop a case. What moved is the group whose subject
is the RUNNER RECORD and the derived operator-facing answers, rather than the
vocabulary rules that stayed:

  * enroll's defaults, which must be null and never a clean-looking value;
  * the reviewed-profile guard on the operator-side setter;
  * the evaluator-image fields, whose only risk is a refactor that merges them
    with the lane's toolchain-image fields (task 1.6);
  * `outstanding_reason`/staleness, i.e. mon-tc-06's promise that an undecided
    request ages into VISIBLE rather than into invisible.

Helpers come from the module they belong to rather than being copied, the way
`test_hub_toolchain_requests_wire.py` takes `HubFixture` from
`test_hub_enroll_heartbeat.py`. A copied `_enrolled` would be a second fixture to
keep honest, and the whole point of that helper is that it sets a lane's profile
through the guarded path.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_toolchain_record.py`
runs them too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import toolchain_requests as tcr  # noqa: E402
from tests.test_hub_toolchain_requests import _enrolled, _registry  # noqa: E402


def test_enrolled_runner_carries_the_new_fields_as_none(tmp_path):
    """0.3: enroll sets the identity fields to None, not to a clean-looking value.

    A default of "none" for toolchain_profile_id would make every freshly enrolled
    lane report itself provisioned, which is the absence-reported-as-health shape.
    """
    reg = _registry(tmp_path)
    runner, _ = reg.enroll("fresh", "TheArchitectit/AIGGP-Agentic-Framework",
                           ["rust"], "fresh")
    for field in ("lane_image_ref", "lane_image_digest", "toolchain_profile_id",
                  "coverage", "last_gap_report_at"):
        assert runner[field] is None, field
    assert runner["toolchain_rejections"] == []
    assert tcr.effective_coverage(runner) == "never-reported"


def test_set_lane_profile_refuses_an_unreviewed_id(tmp_path):
    """A typo in a profile id would produce a permanently clean lane (mon-tc-01)."""
    reg = _registry(tmp_path)
    reg.enroll("lane", "a/b", [], "lane")
    assert reg.set_lane_profile("lane", "rus") is False
    assert reg.find_runner("lane")["toolchain_profile_id"] is None
    assert reg.set_lane_profile("lane", "none") is True


def test_evaluator_image_fields_are_untouched_by_the_gap_path(tmp_path):
    """1.6: the toolchain fields must not disturb the evaluator-image fields.

    `image_digest`/`image_reason`/`image_pin_divergence` are the evaluator image;
    `lane_image_*` are the lane's toolchain image. Two different things, and the
    real risk of this change is a refactor that merges them. Asserted through the
    gap path specifically, since that is the new code that could touch them.
    """
    reg = _enrolled(tmp_path)
    reg.heartbeat("runner-one", None, None, None,
                  image_digest="sha256:eval-abc", image_reason="pinned",
                  image_pin_divergence=None)
    reg.heartbeat("runner-one", None, None, None, missing_tools=["cargo"])
    runner = reg.find_runner("runner-one")
    assert runner["image_digest"] == "sha256:eval-abc"
    assert runner["image_reason"] == "pinned"
    assert runner["lane_image_digest"] is None, "the gap path must not write lane_image_digest"
    # An omitted evaluator digest still preserves it (hub/registry.py:309 idiom).
    reg.heartbeat("runner-one", None, None, None, missing_tools=[])
    assert reg.find_runner("runner-one")["image_digest"] == "sha256:eval-abc"


def test_gap_report_does_not_create_requests_for_a_profile_that_does_not_need_it():
    """mon-tc-01's direction: the SPOKE computes required-minus-observed.

    Recorded here so the reviewer sees the deliberate asymmetry: a lane reporting
    `dotnet` under the `rust` profile is stored, because the lane is reporting a
    fact about its own image and its profile may be stale. Deciding whether it
    *should* have wanted dotnet is the operator's call (mon-tc-04), not a reason
    to discard an observation.
    """
    assert tcr.gap_for_profile("rust", ["cargo", "gcc", "make", "dotnet"]) == []


def test_outstanding_reason_names_the_window_it_used(tmp_path):
    """mon-tc-06: an approved request with no build report is a visible question.

    The sentence carries the window it compared against, because a number with no
    unit next to it is how "is this stuck?" turns into an argument.
    """
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    row = reg.toolchain_requests()[0]
    assert tcr.is_visible(row), "an open request must be in the operator's set"
    assert tcr.outstanding_reason(row) is None, "open is waiting, not stuck"
    row["state"] = "approved"
    row["decided_at"] = "2020-01-01T00:00:00+00:00"
    reason = tcr.outstanding_reason(row)
    assert reason is not None, "an approved request past the window is overdue"
    assert "24h" in reason, f"the sentence must name its window: {reason!r}"
    assert "ago" in reason, f"mon-tc-06 says report it with its age: {reason!r}"
    row["decided_at"] = None
    broken = tcr.outstanding_reason(row)
    assert broken is not None and "inf" not in broken, \
        "a missing timestamp must not format as an infinite age"
    assert "timestamp" in broken, broken
    row["state"] = "fulfilled"
    assert tcr.outstanding_reason(row) is None and not tcr.is_visible(row)


def test_stale_request_is_not_reported_as_healthy(tmp_path):
    """A request nobody has decided on must not age into invisible (mon-tc-06)."""
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    row = reg.toolchain_requests()[0]
    row["observed_at"] = "2020-01-01T00:00:00+00:00"
    assert tcr._age_seconds(row["observed_at"]) > tcr.TOOL_REQUEST_STALE_AFTER_S


if __name__ == "__main__":
    import inspect
    import tempfile
    failures = 0
    ran = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        ran += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(Path(tmp)) if inspect.signature(fn).parameters else fn()
            except Exception as exc:  # noqa: BLE001 — reporting, not handling
                failures += 1
                print(f"FAIL {name}: {exc!r}")
            else:
                print(f"ok   {name}")
    print(f"{ran - failures} passed, {failures} failed")
    sys.exit(1 if failures else 0)
