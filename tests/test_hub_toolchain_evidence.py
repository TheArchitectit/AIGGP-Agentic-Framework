"""Build evidence and convergence — mon-tc-05's fulfillment chain (S3).

The chain this file walks is the one mon-tc-05 fixes: report → approve
(operator) → report-built (builder) → converge (the lane's own later heartbeat).
S2 shipped the credential classes and the CAS machinery; S2's own file stopped
at `approved` because everything past it needed build evidence that did not
exist yet. These tests are why S3 exists rather than being filed as a follow-up.

Split discipline: helpers come from `test_hub_toolchain_requests` rather than
being copied, the way `test_hub_toolchain_record.py` and
`test_hub_toolchain_requests_wire.py` do. The wire route lives in
`test_hub_build_report_wire.py` next to its siblings; what lives here is the
engine and the heartbeat seam, both reachable without a port.

The two assertions this file treats as load-bearing, because they are the ones
a convenient implementation would fail:

  * a REFUSED gap list must not read as "this tool is present". An operator
    watching a row flip to fulfilled because a hostile heartbeat arrived
    malformed is absence reported as health with a green check on it.
  * the lane's own digest report may CLEAR an awaiting digest but never SATISFY
    one. The lane provides "and it is running"; only the builder provided
    "I built this for this request", and collapsing the two lets the requester
    grade its own homework.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_toolchain_evidence.py`
runs them too.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import toolchain_evidence as te  # noqa: E402
from hub import toolchain_requests as tcr  # noqa: E402
from tests.test_hub_toolchain_requests import _enrolled, _registry  # noqa: E402

BUILDER_SECRET = "builder-secret-1234567890"
OPERATOR_SECRET = "op-secret-1234567890"
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
NOW = "2026-10-22T12:00:00Z"


def _iso(seconds_ago: float) -> str:
    stamp = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _builder(reg, secret=BUILDER_SECRET):
    """A builder credential carrying an identity, through the real store."""
    reg.add_toolchain_credential(klass="builder", secret=secret,
                                 credential_id="cred-build-1",
                                 builder_identity="ci-image-builder")
    return secret


def _operator(reg, secret=OPERATOR_SECRET):
    reg.add_toolchain_credential(klass="operator", secret=secret,
                                 credential_id="cred-op-1",
                                 scope="toolchain:decide", principal="alice")
    return secret


def _approve(reg, secret, version=1, nonce="n-approve-1", *, tool="cargo",
             lane=None):
    """Approve a row, named by (tool, lane) rather than a hand-carried id.

    The id is looked up, not passed around, so a test cannot approve lane-f and
    then report against lane-g by a stale variable — the mistake that made the
    first draft of the cross-lane test approve the wrong lane and 409.
    """
    result = reg.decide_request(
        _row(reg, tool, lane)["id"], action="approve", credential_class="operator",
        scope="toolchain:decide", credential_id="cred-op-1", actor="alice@corp",
        principal="alice", nonce=nonce, expected_version=version, note=None,
        now=NOW)
    assert result["status"] == 200, result
    return result


def _report(reg, secret, *, digest=DIGEST, profile="rust", build_id="b-77",
            version=2, note=None, tool="cargo", lane=None):
    result = reg.report_build(
        _row(reg, tool, lane)["id"], credential=secret, profile_id=profile,
        build_id=build_id, digest=digest, note=note, expected_version=version,
        now=NOW)
    return result


def _built_lane(tmp_path, profile="rust", tool="cargo"):
    """A lane in `built` with one row approved against the builder's digest.

    Everything upstream of mon-tc-05 runs through the real paths on purpose: a
    row fabricated straight into `built` would test the engine while letting a
    broken approval path ship unnoticed, and the fulfillment chain is only as
    honest as its weakest link.
    """
    reg = _enrolled(tmp_path, "lane-f", profile)
    reg.record_gap_report("lane-f", [tool], profile)
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    _builder(reg)
    report = _report(reg, BUILDER_SECRET)
    assert report["status"] == 200, report
    return reg


def _row(reg, tool="cargo", lane=None):
    rows = [r for r in reg.toolchain_requests() if r["tool"] == tool]
    if lane is not None:
        rows = [r for r in rows if r["lane"] == lane]
    assert rows, f"no row for {lane or 'any lane'}/{tool}"
    return rows[0]


# --- 3.1: built requires the full evidence set --------------------------------


def test_build_evidence_moves_approved_to_built_and_stores_the_triple(tmp_path):
    """The profile id, build id and digest all land on the row (mon-tc-05)."""
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    _builder(reg)
    result = _report(reg, BUILDER_SECRET)
    assert result["status"] == 200 and result["state"] == "built"
    row = _row(reg)
    assert row["build_id"] == "b-77"
    assert row["lane_image_digest"] == DIGEST
    assert row["builder_identity"] == "ci-image-builder"
    # audit attribution: the identity came FROM the credential, not the body
    assert row["history"][-1]["credential_id"] == "cred-build-1"
    assert row["history"][-1]["event"] == "report-built"


def test_mismatched_profile_is_refused_and_changes_nothing(tmp_path):
    """3.1: 'matching the approved profile' means the BUILDER cannot pick one."""
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["node"], "node")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET, tool="node")
    _builder(reg)
    result = _report(reg, BUILDER_SECRET, profile="rust", tool="node")
    assert result["status"] == 409 and result["error"] == "profile_mismatch"
    row = _row(reg, "node")
    assert row["state"] == "approved", "a refused report must not move the row"
    assert row["version"] == 2, "a refused report must not bump the version"


def test_a_profile_less_lane_never_matches_a_builders_profile(tmp_path):
    """Strict equality means None != "rust", not "missing matches anything".

    A row whose assignment was cleared after approval is exactly the case where
    a loose comparison would let any build converge anything — and mon-tc-01
    refuses to call a profile-less lane healthy.
    """
    reg = _registry(tmp_path)
    reg.enroll("lane-u", "a/b", [], "lane-u")
    reg.record_gap_report("lane-u", ["cargo"], None)  # unassigned lane
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    _builder(reg)
    result = _report(reg, BUILDER_SECRET, profile="rust")
    assert result["status"] == 409 and result["error"] == "profile_mismatch"
    assert _row(reg)["state"] == "approved"


def test_each_missing_evidence_field_is_refused_by_name(tmp_path):
    """3.1: a partial evidence set is refused, naming every field it lacks."""
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    _builder(reg)
    for field, kwargs in {
        "build_id": {"build_id": ""},
        "profile_id": {"profile": None},
    }.items():
        args = {"build_id": "b-77", "profile": "rust"}
        args.update(kwargs)
        result = _report(reg, BUILDER_SECRET, **args)
        assert result["status"] == 400, field
        assert result["error"] == "build_evidence_incomplete"
        assert field in result["fields"], (field, result["fields"])
    assert _row(reg)["state"] == "approved"
    # the refused evidence must not linger on the row (mon-tc-01: a rejected
    # value is never stored) — nor anywhere in the audit trail
    trail = str(reg.toolchain_requests()[0]["history"])
    assert "b-77" not in trail, "refused evidence must not reach the audit trail"


# --- 3.3: a digest under the wrong credential class is refused ----------------


def _refusal(reg, secret, *, klass_check):
    result = _report(reg, secret)
    assert result["status"] == 403, result
    assert result["error"] == "rejected_credential_class"
    return klass_check(result)


def test_digest_under_the_operator_credential_is_refused(tmp_path):
    """3.3: the credential that APPROVES must not be able to BUILD (mon-tc-05).

    Otherwise one leaked operator key walks a row all the way to `built` with no
    build at all, and the audit row would name alice as a builder.
    """
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    result = _report(reg, OPERATOR_SECRET)
    assert result["status"] == 403
    assert result["error"] == "rejected_credential_class"
    assert result["credential_class"] == "operator"
    assert _row(reg)["state"] == "approved"


def test_digest_under_a_heartbeat_token_is_refused(tmp_path):
    """3.3: a lane cannot report its own image built over its heartbeat."""
    # enroll returns the lane's token; capture it HERE so the presented secret
    # really is a heartbeat token and not some string that merely classifies as
    # unknown (both are refused — only this one proves 3.3's runner clause)
    reg = _registry(tmp_path)
    _runner, token = reg.enroll("lane-f", "a/b", ["rust"], "lane-f")
    reg.set_lane_profile("lane-f", "rust")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    result = _report(reg, token)
    assert result["status"] == 403
    assert result["error"] == "rejected_credential_class"
    assert result["credential_class"] == "heartbeat"
    assert _row(reg)["state"] == "approved"


def test_an_unpresented_credential_is_401_not_403(tmp_path):
    """Nothing presented is unauthenticated, not merely the wrong class."""
    reg = _built_lane(tmp_path)
    result = _report(reg, None)
    assert result["status"] == 401 and result["error"] == "unknown_credential"


def test_a_builder_credential_without_an_identity_is_refused(tmp_path):
    """Attribution comes from the credential; a nameless builder is refused."""
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    reg.add_toolchain_credential(klass="builder", secret="b-nameless-1234567890",
                                 credential_id="cred-build-nameless")
    result = _report(reg, "b-nameless-1234567890")
    assert result["status"] == 403 and result["error"] == "builder_identity_missing"
    assert _row(reg)["state"] == "approved"


# --- 3.4: approval alone never reaches fulfilled ------------------------------


def test_approved_never_converges_no_matter_what_the_lane_reports(tmp_path):
    """3.4: convergence lives on `built`; the table has no (approved, converge).

    The tempting shortcut — a lane heartbeats the digest the operator approved
    and the row fulfills — skips the builder entirely. This test is the whole
    of 3.4 and the reason the awaited digest lives on the builder's report and
    not on the approval.
    """
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    _operator(reg)
    _approve(reg, OPERATOR_SECRET)
    runner = reg.find_runner("lane-f")
    runner["lane_image_digest"] = DIGEST  # the lane "runs" the approved image
    row = _row(reg)
    row["lane_image_digest"] = DIGEST     # ... and the approval named it
    changed = te.note_lane_evidence(runner, reg._data, DIGEST, [], NOW)
    assert changed == 0
    assert row["state"] == "approved", "approval is not half of fulfillment"


# --- duplicate protection: CAS on the build route ------------------------------


def test_a_retried_build_report_is_a_conflict_not_a_second_transition(tmp_path):
    """CI retries are the normal case; CAS is what makes them safe here.

    mon-tc-05 asks no nonce of a build report (unlike an operator decision), so
    the version check is the ONLY duplicate defence on this route — which is
    why `expected_version` is refused as missing rather than defaulted.
    """
    reg = _built_lane(tmp_path)
    stale = _report(reg, BUILDER_SECRET, version=2)  # row already at 3
    assert stale["status"] == 409 and stale["error"] == "version_conflict"
    assert _row(reg)["state"] == "built"
    assert _row(reg)["version"] == 3


def test_a_build_report_with_no_expected_version_is_refused(tmp_path):
    reg = _built_lane(tmp_path)
    result = _report(reg, BUILDER_SECRET, version=None)
    assert result["status"] == 400
    assert result["error"] == "expected_version_required"


# --- build-failed ---------------------------------------------------------------


def test_a_null_digest_reports_failure_and_clears_the_failed_evidence(tmp_path):
    """An absent digest is a different report, not a malformed one: mon-tc-04's
    `build-failed` event, guarded "builder credential, note present". A digest
    from a FAILED build must not linger as something a lane could converge onto.
    """
    reg = _built_lane(tmp_path)
    result = _report(reg, BUILDER_SECRET, digest=None, version=3,
                     note="toolchain layer failed to compile")
    assert result["status"] == 200 and result["state"] == "open"
    row = _row(reg)
    assert row["build_id"] is None and row["lane_image_digest"] is None
    assert row["history"][-1]["event"] == "build-failed"


def test_a_build_failure_without_a_note_is_refused(tmp_path):
    reg = _built_lane(tmp_path)
    result = _report(reg, BUILDER_SECRET, digest=None, version=3)
    assert result["status"] == 400 and result["error"] == "build_failure_requires_note"
    assert _row(reg)["state"] == "built"


def test_a_second_build_on_an_open_row_is_refused_as_out_of_table(tmp_path):
    """After build-failed reopened the row, report-built has no rule from open."""
    reg = _built_lane(tmp_path)
    _report(reg, BUILDER_SECRET, digest=None, version=3, note="boom")
    result = _report(reg, BUILDER_SECRET, version=4)
    assert result["status"] == 409 and result["error"] == "transition_not_in_table"


# --- convergence: the lane's side of mon-tc-05 ----------------------------------


def test_digest_plus_clean_probe_fulfills(tmp_path):
    """The scenario itself: same digest, probe passes, later heartbeat."""
    reg = _built_lane(tmp_path)
    ok = reg.heartbeat("lane-f", None, None, None, missing_tools=[],
                       lane_image_digest=DIGEST)
    assert ok is True
    row = _row(reg)
    assert row["state"] == "fulfilled"
    assert row["fulfilled_at"] == row["history"][-1]["at"]
    assert row["history"][-1]["event"] == "converge"
    assert row["version"] == 4


def test_digest_with_the_tool_still_missing_stays_built(tmp_path):
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, missing_tools=["cargo"],
                  lane_image_digest=DIGEST)
    assert _row(reg)["state"] == "built", "a passing probe is half the rule"


def test_a_refused_gap_list_never_reads_as_a_passing_probe(tmp_path):
    """The one this file exists to keep honest.

    A hostile or buggy heartbeat can send a rejected gap list. It counts as
    "the lane spoke" for coverage (mon-tc-06) and must count as NOTHING about
    tool presence — if "cargo not in the refused list" passed the probe, a
    single malformed body would fulfill requests fleet-wide.
    """
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, missing_tools=[123],
                  lane_image_digest=DIGEST)
    assert _row(reg)["state"] == "built"


def test_no_gap_field_and_no_prior_report_never_converges(tmp_path):
    """An old spoke predating the probe field is believed, never converged.

    Presence-not-truth says absence is "no opinion" — which protects an old
    spoke from looking unhealthy, and here protects fulfillment from an opinion
    that was never given. Absence converges nothing.
    """
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, lane_image_digest=DIGEST)
    assert _row(reg)["state"] == "built"


def test_a_stale_lane_does_not_converge_on_its_last_good_report(tmp_path):
    """coverage=stale means "stopped telling us anything" — not "still clean"."""
    reg = _built_lane(tmp_path)
    runner = reg.find_runner("lane-f")
    runner["coverage"] = "reported"
    runner["last_gap_report_at"] = _iso(tcr.TOOL_REQUEST_STALE_AFTER_S + 60)
    te.note_lane_evidence(runner, reg._data, DIGEST, None, NOW)
    assert tcr.effective_coverage(runner) == "stale"
    assert _row(reg)["state"] == "built"


def test_probe_failed_coverage_never_converges(tmp_path):
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, missing_tools=[],
                  probe_complete=False)
    assert tcr.effective_coverage(reg.find_runner("lane-f")) == "probe-failed"
    te.note_lane_evidence(reg.find_runner("lane-f"), reg._data, DIGEST, None,
                          NOW)
    assert _row(reg)["state"] == "built"


# --- the lane's digest may clear an awaited digest, never satisfy one -----------


def test_an_unmatched_digest_clears_the_dead_wait_once_and_stays_visible(tmp_path):
    """The lane moved on; that build will never converge. Carrying the dead
    wait forward makes a permanent alarm — but the row also must NOT reopen or
    fulfill: `build-failed` names a builder credential, and the lane did not
    fail the build. mon-tc-06 keeps it visible.
    """
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, lane_image_digest=OTHER_DIGEST,
                  missing_tools=[])
    row = _row(reg)
    assert row["state"] == "built"
    assert row["lane_image_digest"] is None, "the dead wait is dropped"
    assert row["awaiting_cleared"] == OTHER_DIGEST
    events = [h["event"] for h in row["history"]]
    assert events.count(te.E_AWAITING_CLEARED) == 1
    # a second tick with the same unmatched digest must not re-log it
    reg.heartbeat("lane-f", None, None, None, lane_image_digest=OTHER_DIGEST)
    events = [h["event"] for h in row["history"]]
    assert events.count(te.E_AWAITING_CLEARED) == 1, "audit spam every 300s"


def test_a_cleared_row_can_be_rebuilt_to_a_new_digest(tmp_path):
    """Clearing the wait is not the end of the row — a fresh build can aim it."""
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, lane_image_digest=OTHER_DIGEST,
                  missing_tools=[])
    result = _report(reg, BUILDER_SECRET, digest=DIGEST, version=3)
    assert result["status"] == 409  # state is built, not approved: out of table
    assert _row(reg)["state"] == "built"


def test_the_lanes_digest_alone_can_satisfy_nothing(tmp_path):
    """With no builder report on the row, any digest the lane reports converges
    zero rows — the lane supplies "it is running", never "it was built for this".
    """
    reg = _enrolled(tmp_path, "lane-f")
    reg.record_gap_report("lane-f", ["cargo"], "rust")
    changed = te.note_lane_evidence(reg.find_runner("lane-f"), reg._data,
                                    DIGEST, [], NOW)
    assert changed == 0
    assert _row(reg)["state"] == "open"


# --- regression: fulfilled is not forever ---------------------------------------


def test_a_reappearing_gap_reopens_the_row_and_clears_its_evidence(tmp_path):
    """mon-tc-04's gap-regressed, plus the evidence hygiene behind it: an image
    that regressed must not leave a digest a later tick could "converge" onto.
    """
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, missing_tools=[],
                  lane_image_digest=DIGEST)
    assert _row(reg)["state"] == "fulfilled"
    reg.heartbeat("lane-f", None, None, None, missing_tools=["cargo"])
    row = _row(reg)
    assert row["state"] == "open"
    assert row["fulfilled_at"] is None
    assert row["build_id"] is None and row["lane_image_digest"] is None
    assert row["history"][-1]["event"] == "gap-regressed"


def test_regression_needs_the_tool_named_not_merely_a_report(tmp_path):
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, missing_tools=[],
                  lane_image_digest=DIGEST)
    reg.heartbeat("lane-f", None, None, None, missing_tools=[])
    assert _row(reg)["state"] == "fulfilled", "a clean report keeps it settled"


# --- the runner-record write itself ----------------------------------------------


def test_the_lanes_digest_lands_on_its_runner_record(tmp_path):
    """Q6: the hub owns observed lane-image evidence, fed by the spoke."""
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, lane_image_digest=OTHER_DIGEST)
    assert reg.find_runner("lane-f")["lane_image_digest"] == OTHER_DIGEST


def test_a_non_string_digest_is_dropped_not_coerced(tmp_path):
    """str(12345) is digest-shaped enough to converge something if it reaches a
    comparison; an untrusted host gets its field dropped, whole."""
    reg = _built_lane(tmp_path)
    runner = reg.find_runner("lane-f")
    before = runner.get("lane_image_digest")
    te.note_lane_evidence(runner, reg._data, {"sha": "x"}, [], NOW)
    assert runner.get("lane_image_digest", before) in (None, before)
    te.note_lane_evidence(runner, reg._data, 12345, [], NOW)
    assert runner.get("lane_image_digest", before) in (None, before)


def test_said_nothing_about_the_digest_still_converges_the_stored_one(tmp_path):
    """UNREPORTED skips the WRITE, not the row: a lane that heartbeats a clean
    probe after reporting its digest converges even with no digest in THIS tick.
    """
    reg = _built_lane(tmp_path)
    reg.heartbeat("lane-f", None, None, None, lane_image_digest=DIGEST)
    assert _row(reg)["state"] == "built"  # no probe opinion yet
    reg.heartbeat("lane-f", None, None, None, missing_tools=[])
    assert _row(reg)["state"] == "fulfilled"


def test_heartbeat_never_touches_another_lanes_rows(tmp_path):
    """Lane-scoped even when the digests match across lanes."""
    reg = _built_lane(tmp_path)
    reg.enroll("lane-g", "a/b", ["rust"], "lane-g")
    reg.set_lane_profile("lane-g", "rust")
    reg.record_gap_report("lane-g", ["cargo"], "rust")
    _approve(reg, OPERATOR_SECRET, nonce="n-approve-2", lane="lane-g")
    _report(reg, BUILDER_SECRET, version=2, lane="lane-g")
    before = _row(reg, "cargo", lane="lane-f")["state"]
    reg.heartbeat("lane-f", None, None, None, missing_tools=[],
                  lane_image_digest=DIGEST)
    rows = [(r["lane"], r["state"]) for r in reg.toolchain_requests()]
    assert rows.count(("lane-f", "fulfilled")) == 1, rows
    assert ("lane-g", "built") in rows, "another lane's row must stay untouched"
    assert before == "built"


if __name__ == "__main__":
    import inspect
    import tempfile

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                if "tmp_path" in inspect.signature(fn).parameters:
                    fn(Path(tmp))
                else:
                    fn()
                passed += 1
            except Exception as exc:  # noqa: BLE001 — the runner's whole purpose
                failed += 1
                print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
