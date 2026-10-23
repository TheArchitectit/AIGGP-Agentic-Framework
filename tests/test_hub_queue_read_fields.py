"""The request-set read as a queue consumes it (mon-tc-02, S5 hub-side).

`test_hub_toolchain_requests_wire.py` proved the route records and lists; what
lives here is the *shape* a consumer forbidden its own copy must be able to
render and act from — lane-describing fields and version — because Mission
Control's queue proved to have nothing to render them from (FINDINGS-2026-10-23,
repo-brainstorming).

The unit half calls the projector directly and can therefore construct the
cases a live fleet cannot produce on cue (a lane with no runner record at all,
a repository published as an empty string). The wire half runs the real route
and asserts the fields arrive over HTTP, and that a read stays a read.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_queue_read_fields.py`
runs them too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import toolchain_queue_read, toolchain_store  # noqa: E402
from hub.registry import Registry  # noqa: E402
from tests.test_hub_enroll_heartbeat import HubFixture  # noqa: E402

REPO = "TheArchitectit/AIGGP-Agentic-Framework"


class _FakeRegistry:
    """Only `.runners()` — the projector's entire dependency surface.

    A hand-rolled double rather than the real Registry, because the projector's
    contract is that it reads *only* this: a test that handed it a real Registry
    would still pass if the projector reached for something else.
    """

    def __init__(self, runners):
        self._runners = runners

    def runners(self):
        return self._runners


def test_a_known_lane_contributes_its_repo_host_and_coverage():
    rows = [{"id": "r1", "lane": "lane-a", "tool": "cargo"}]
    reg = _FakeRegistry([{"name": "lane-a", "repo": REPO, "host_alias": "host-1",
                          "coverage": "reported", "last_gap_report_at": None}])
    out = toolchain_queue_read.annotate_requests(rows, reg)[0]
    assert out["repository"] == REPO
    assert out["host_alias"] == "host-1"
    # coverage "reported" with an unreadable stamp: effective_coverage treats an
    # unparseable time as ancient, so the lane is stale — the projector must
    # carry the derivation, not the stored flag.
    assert out["coverage_state"] == "stale"


def test_a_lane_the_hub_has_no_record_for_yields_nulls_not_blanks():
    """A blank cell reads as "lane with no repo"; null reads as "hub does not
    know". Those are different sentences and mon-tc-06's vocabulary is built on
    not collapsing them."""
    out = toolchain_queue_read.annotate_requests(
        [{"id": "r1", "lane": "ghost", "tool": "cargo"}], _FakeRegistry([]))[0]
    assert out["repository"] is None
    assert out["host_alias"] is None
    assert out["coverage_state"] is None


def test_an_unpublished_repository_is_null_not_empty_string():
    out = toolchain_queue_read.annotate_requests(
        [{"id": "r1", "lane": "lane-a", "tool": "cargo"}],
        _FakeRegistry([{"name": "lane-a", "repo": "", "host_alias": ""}]))[0]
    assert out["repository"] is None
    assert out["host_alias"] is None


def test_the_projection_never_mutates_the_rows_it_reads():
    row = {"id": "r1", "lane": "lane-a", "tool": "cargo"}
    toolchain_queue_read.annotate_requests([row], _FakeRegistry(
        [{"name": "lane-a", "repo": REPO, "host_alias": "h"}]))
    assert "repository" not in row and "coverage_state" not in row


def _lane_hub(tmp_path, name="lane-a"):
    """Live hub + enrolled lane + a gap reported **over the heartbeat route**.

    The gap goes through `/heartbeat`, not `record_gap_report` directly, because
    coverage is written by the heartbeat path (`note_gap_coverage`), and a fixture
    that called the store directly would leave coverage `never-reported` and turn
    the assertion below into a test of the fixture rather than of the read.
    """
    hub = HubFixture(tmp_path)
    status, enrolled = hub.post("/enroll", {
        "runner_name": name, "repo": REPO,
        "enrollment_token": "test-enroll-token-PLACEHOLDER",
        "labels": ["rust"], "host_alias": "host-1"})
    assert status == 200, enrolled
    with hub.state._lock:
        hub.state.registry.set_lane_profile(name, "rust")
        hub.state.registry.save()
    status, spoken = hub.post("/heartbeat", {
        "runner_name": name, "heartbeat_token": enrolled["heartbeat_token"],
        "missing_tools": ["cargo"]})
    assert status == 200, spoken
    return hub


def _row(hub, lane="lane-a"):
    status, body = hub.get("/toolchain/requests")
    assert status == 200, body
    return next(r for r in body["requests"] if r["lane"] == lane)


def test_the_read_carries_every_field_the_declared_contract_names(tmp_path):
    """The contract is one visible list (QUEUE_FIELDS), and this asserts that
    list — not a spot-check of two fields a reader happened to remember."""
    hub = _lane_hub(tmp_path)
    row = _row(hub)
    for field in toolchain_queue_read.QUEUE_FIELDS:
        assert field in row, f"{field} missing from the live read"
    assert row["repository"] == REPO
    assert row["host_alias"] == "host-1"
    # mon-tc-06's derivation, carried: the lane just made an accepted report.
    assert row["coverage_state"] == "reported"
    # mon-tc-04's CAS is unimplementable by a consumer that cannot read this.
    assert row["version"] == 1


def test_a_row_naming_a_lane_the_hub_has_no_record_for_is_still_exposed(tmp_path):
    """Over HTTP: the projector's null branch has to survive json round-tripping,
    which is where a defaulted `coverage_state` would hide (a lane with no record
    would render "never-reported", a verdict the hub never earned).

    How a registry reaches this state is unusual — today the hub never removes a
    runner record (`revoke` marks `enrolled=False`, `hub/registry.py:417`), so it
    is written directly rather than reached through a lifecycle the hub does not
    have. The case is a row naming a lane with no runner behind it, and the
    guarantee is the response shape, not the path that produced the state.
    """
    hub = _lane_hub(tmp_path)
    with hub.state._lock:
        other = dict(toolchain_store.new_request_row(
            "lane-gone", "go", None, "2026-10-23T00:00:00Z", "req-gone-1"))
        hub.state.registry.toolchain_requests().append(other)
        hub.state.registry.save()
    row = _row(hub, lane="lane-gone")
    assert row["tool"] == "go"
    assert row["repository"] is None
    assert row["coverage_state"] is None
    assert row["host_alias"] is None
    # A lane the hub does know still renders normally beside it — the missing
    # lane must not degrade the whole read. Two assertions, not one `and`: a
    # compound assert names neither half when it fails, which cost me a minute
    # guessing which of these two was wrong.
    known = _row(hub)
    assert known["repository"] == REPO
    assert known["coverage_state"] == "reported"


def main():
    import inspect
    import tempfile
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        with tempfile.TemporaryDirectory() as td:
            try:
                if "tmp_path" in inspect.signature(fn).parameters:
                    fn(Path(td))
                else:
                    fn()
            except Exception as exc:  # noqa: BLE001 — runner reports, does not fix
                failures += 1
                print(f"FAIL {name}: {exc}")
            else:
                print(f"ok   {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
