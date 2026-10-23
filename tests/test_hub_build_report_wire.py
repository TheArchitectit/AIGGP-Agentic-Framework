"""Wire tests for build evidence and convergence (mon-tc-05, S3).

The engine lives in `test_hub_toolchain_evidence.py`; what lives here is what
only exists once bytes travel: that `/toolchain/build-report` classifies the
presented secret over HTTP and refuses the wrong class by the wire, that the
heartbeat's `lane_image_digest` reaches convergence through `server.py`'s
presence-aware read, and that a body field that is neither a string nor null is
refused with 400 rather than coerced by the engine.

Split for the same reason the two request-wire files are split from their unit
file: a live fixture (hub on an ephemeral port, an enroll round-trip, an HTTP
POST per case) is a different cost and a different class of failure. A unit
failure means a rule is wrong; a wire failure can also mean the route, the
presence-aware read, or the response shape broke.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_build_report_wire.py`
runs them too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_hub_enroll_heartbeat import HubFixture  # noqa: E402

DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


def _hub_with_lane(tmp_path, profile="rust"):
    """Live hub + one enrolled lane whose reviewed profile is set. -> (hub, token)."""
    hub = HubFixture(tmp_path)
    status, body = hub.post("/enroll", {
        "runner_name": "lane-a",
        "repo": "TheArchitectit/AIGGP-Agentic-Framework",
        "enrollment_token": "test-enroll-token-PLACEHOLDER",
        "labels": ["rust"], "host_alias": "lane-a"})
    assert status == 200, body
    with hub.state._lock:
        hub.state.registry.set_lane_profile("lane-a", profile)
    return hub, body["heartbeat_token"]


def _open_row(hub, tool="cargo"):
    with hub.state._lock:
        hub.state.registry.record_gap_report("lane-a", [tool], "rust")
        hub.state.registry.save()
        return hub.state.registry.toolchain_requests()[-1]["id"]


def _approve(hub, row_id, secret="op-wire-secret-1234567890"):
    with hub.state._lock:
        hub.state.registry.add_toolchain_credential(
            klass="operator", secret=secret, credential_id="cred-op-1",
            scope="toolchain:decide", principal="alice")
        hub.state.registry.save()
    status, body = hub.post("/toolchain/decide", {
        "request_id": row_id, "action": "approve", "credential": secret,
        "actor": "alice@corp", "principal": "alice", "nonce": "n-wire-1",
        "expected_version": 1})
    assert status == 200, body


def _add_builder(hub, secret="bld-wire-secret-1234567890"):
    with hub.state._lock:
        hub.state.registry.add_toolchain_credential(
            klass="builder", secret=secret, credential_id="cred-b-1",
            builder_identity="ci-image-builder")
        hub.state.registry.save()
    return secret


def _row(hub, row_id):
    status, body = hub.get("/toolchain/requests")
    assert status == 200
    return next(r for r in body["requests"] if r["id"] == row_id)


def test_build_report_over_http_moves_approved_to_built(tmp_path):
    """3.1 end-to-end: a builder POST lands the triple and flips the row."""
    hub, _ = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    secret = _add_builder(hub)
    status, body = hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": secret, "profile_id": "rust",
        "build_id": "b-9", "digest": DIGEST, "expected_version": 2})
    assert status == 200, body
    assert body["state"] == "built"
    row = _row(hub, row_id)
    assert row["lane_image_digest"] == DIGEST
    assert row["build_id"] == "b-9"


def test_build_report_refuses_operator_credential_over_the_wire(tmp_path):
    """3.3: the class check is on the route, not a client-side courtesy."""
    hub, _ = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    # op-wire-secret is an operator, not a builder
    status, body = hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": "op-wire-secret-1234567890",
        "profile_id": "rust", "build_id": "b-9", "digest": DIGEST,
        "expected_version": 2})
    assert status == 403, body
    assert body["error"] == "rejected_credential_class"
    assert _row(hub, row_id)["state"] == "approved"


def test_build_report_is_absent_from_get(tmp_path):
    """Only the POST surface accepts it; a GET must 404, not list or act."""
    hub, _ = _hub_with_lane(tmp_path)
    status, _ = hub.get("/toolchain/build-report")
    assert status == 404


def test_missing_digest_key_is_refused_not_read_as_failure(tmp_path):
    """Omitting digest is ambiguous; only an explicit null means failed build."""
    hub, _ = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    secret = _add_builder(hub)
    status, body = hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": secret, "profile_id": "rust",
        "build_id": "b-9", "expected_version": 2})
    assert status == 400, body
    assert "digest" in body.get("detail", "")


def test_non_string_digest_is_refused_before_the_engine(tmp_path):
    hub, _ = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    secret = _add_builder(hub)
    status, body = hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": secret, "profile_id": "rust",
        "build_id": "b-9", "digest": {"sha": "x"}, "expected_version": 2})
    assert status == 400, body
    assert _row(hub, row_id)["state"] == "approved"


def test_heartbeat_digest_and_clean_probe_fulfills_over_http(tmp_path):
    """The lane's side of mon-tc-05, through server.py's presence-aware read."""
    hub, token = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    secret = _add_builder(hub)
    hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": secret, "profile_id": "rust",
        "build_id": "b-9", "digest": DIGEST, "expected_version": 2})
    status, _ = hub.post("/heartbeat", {
        "runner_name": "lane-a", "heartbeat_token": token,
        "missing_tools": [], "missing_tools_probe_complete": True,
        "lane_image_digest": DIGEST})
    assert status == 200
    assert _row(hub, row_id)["state"] == "fulfilled"


def test_heartbeat_without_digest_key_keeps_a_stored_one(tmp_path):
    """Presence-not-truth on the wire: omitting lane_image_digest must NOT
    clear a digest the lane reported earlier, or convergence would race an
    older helper into wiping its own evidence."""
    hub, token = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    secret = _add_builder(hub)
    hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": secret, "profile_id": "rust",
        "build_id": "b-9", "digest": DIGEST, "expected_version": 2})
    hub.post("/heartbeat", {"runner_name": "lane-a", "heartbeat_token": token,
                            "missing_tools": [], "missing_tools_probe_complete":
                            True, "lane_image_digest": DIGEST})
    assert _row(hub, row_id)["state"] == "fulfilled"


def test_heartbeat_oversized_digest_is_refused_400(tmp_path):
    """A lane's image digest is free text from an untrusted host and is capped
    like the evaluator's: an unbounded field that takes part in a byte-for-byte
    comparison is a storage problem waiting to be noticed."""
    hub, token = _hub_with_lane(tmp_path)
    status, body = hub.post("/heartbeat", {
        "runner_name": "lane-a", "heartbeat_token": token,
        "lane_image_digest": "sha256:" + "z" * 2000})
    assert status == 400, body


def test_a_wrong_digest_clears_the_wait_over_http(tmp_path):
    hub, token = _hub_with_lane(tmp_path)
    row_id = _open_row(hub)
    _approve(hub, row_id)
    secret = _add_builder(hub)
    hub.post("/toolchain/build-report", {
        "request_id": row_id, "credential": secret, "profile_id": "rust",
        "build_id": "b-9", "digest": DIGEST, "expected_version": 2})
    hub.post("/heartbeat", {"runner_name": "lane-a", "heartbeat_token": token,
                            "lane_image_digest": OTHER})
    row = _row(hub, row_id)
    assert row["state"] == "built"
    assert row["lane_image_digest"] is None
    assert row["awaiting_cleared"] == OTHER


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
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
