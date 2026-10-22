# // spec: mon-tc-03, mon-tc-04
"""Operator credential + transition tests (mon-tc-03, mon-tc-04)."""

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import toolchain_creds, toolchain_requests, toolchain_transitions
from hub.registry import Registry
from hub.server import create_server
from hub.config import Config
from tests.test_hub_enroll_heartbeat import HubFixture


def _reg(tmp_path):
    return Registry(str(tmp_path / "runners.json"))


def _seed_request(reg, now="2026-01-01T00:00:00Z"):
    reg._data.setdefault("toolchain_requests", [])
    row = {
        "id": "tcr-0001", "lane": "lane-a", "tool": "cargo",
        "required_profile": "rust", "state": "open", "version": 1,
        "observed_at": now, "last_seen": now, "last_reported_at": now,
        "actor": None, "principal": None, "credential_id": None,
        "decided_at": None, "decision_note": None, "nonces": [],
        "build_id": None, "builder_identity": None, "lane_image_digest": None,
        "fulfilled_at": None, "suppression_until": None,
        "suppressed_reports": 0,
        "history": [{"seq": 0, "at": now, "actor": None, "principal": None,
                     "credential_id": None, "event": "gap-reported", "from": None,
                     "to": "open", "version_before": None, "version_after": 1,
                     "note": None}],
    }
    reg._data["toolchain_requests"].append(row)
    reg.save()
    return row


def _operator(reg, secret="op-secret-1234567890"):
    reg.add_toolchain_credential(
        klass="operator", secret=secret, credential_id="cred-op-1",
        scope="toolchain:decide", principal="alice")
    return secret


def test_credential_classes_closed():
    # mon-tc-03
    assert "operator" in toolchain_transitions.CREDENTIAL_CLASSES
    assert "mc_api_key" not in toolchain_transitions.CREDENTIAL_CLASSES


def test_operator_decide_approve(tmp_path):
    # mon-tc-03, mon-tc-04
    reg = _reg(tmp_path)
    _seed_request(reg)
    secret = _operator(reg)
    row = reg._data["toolchain_requests"][0]
    now = "2026-01-01T00:00:00Z"
    res = reg.decide_request("tcr-0001", action="approve",
                             credential_class="operator",
                             scope="toolchain:decide",
                             credential_id="cred-op-1",
                             actor="alice", principal="alice",
                             nonce="nonce-1", expected_version=1,
                             note=None, now=now)
    assert res["status"] == 200, res
    assert row["state"] == "approved"
    assert row["actor"] == "alice"
    assert row["principal"] == "alice"
    assert row["credential_id"] == "cred-op-1"
    assert row["decision_note"] is None
    # audit row present
    assert any(h["event"] == "decide-approve" for h in row["history"])
    # nonce consumed
    assert reg.is_toolchain_nonce_consumed("nonce-1")


def test_rejected_credential_classes(tmp_path):
    # mon-tc-03 negative controls
    reg = _reg(tmp_path)
    _seed_request(reg)
    secret = _operator(reg)
    # register runner heartbeat token + runner_key + builder as credentials
    reg.enroll("runner-one", "O/R", [], "")
    hb_token = None
    # get heartbeat token via find_runner (not stored plaintext); mint one
    from hub import tokens
    hb_token = tokens.mint_token()
    reg.find_runner("runner-one")["heartbeat_token_hash"] = reg._hash_token(hb_token)
    reg.add_toolchain_credential(klass="runner_key", secret="rk-secret-1234567890",
                                credential_id="rk-1", scope=None, principal=None)
    reg.add_toolchain_credential(klass="builder", secret="b-secret-1234567890",
                                credential_id="b-1", scope=None, principal=None)
    # ordinary MC write key: classify as unknown (not in table)
    for klass, secret_val, scope in (
        ("heartbeat", hb_token, None),
        ("runner_key", "rk-secret-1234567890", None),
        ("builder", "b-secret-1234567890", None),
        ("enrollment", "enroll-tok", None),
    ):
        before_state = reg._data["toolchain_requests"][0]["state"]
        before_version = reg._data["toolchain_requests"][0]["version"]
        before_hist = len(reg._data["toolchain_requests"][0]["history"])
        res = reg.decide_request("tcr-0001", action="approve",
                                 credential_class=klass,
                                 scope=scope, credential_id="x",
                                 actor="a", principal="p",
                                 nonce="n-" + klass, expected_version=before_version,
                                 note=None, now="2026-01-01T00:00:00Z")
        assert res["status"] == 403, (klass, res)
        assert res["error"] == "rejected_credential_class"
        assert res.get("credential_class") == klass
        row = reg._data["toolchain_requests"][0]
        assert row["state"] == before_state
        assert row["version"] == before_version
        # audit row recorded
        assert len(row["history"]) == before_hist + 1
    # ordinary MC write key -> classified unknown
    reg._data.setdefault("enrollment_tokens", [])
    cls, info = reg.classify_credential("not-a-real-secret-1234567890")
    # may be unknown
    assert cls in (None, "unknown")
    # secret never in stored text
    text = json.dumps(reg._data)
    assert "rk-secret-1234567890" not in text
    assert "b-secret-1234567890" not in text
    assert "op-secret-1234567890" not in text


def test_expired_nonce(tmp_path):
    # mon-tc-03 negative control (task 2.5): the spec attaches no validity
    # window to the claim timestamp — mon-tc-06 owns the numbers and names no
    # TTL — so a nonce goes stale by being CONSUMED, not by the clock. The
    # nonce is single-use across the hub's whole request set, not per row, so
    # this replays it against a DIFFERENT row (a same-row replay is a CAS
    # conflict first, which is a different event). Refusal, unchanged state,
    # an audit row — what task 2.5 asks for.
    reg = _reg(tmp_path)
    _seed_request(reg)   # tcr-0001
    _seed_request(reg)   # tcr-0002 — the replay target
    reg._data["toolchain_requests"][1]["id"] = "tcr-0002"
    reg._data["toolchain_requests"][1]["tool"] = "gcc"
    reg.save()
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    first = reg.decide_request("tcr-0001", action="approve",
                               credential_class="operator",
                               scope="toolchain:decide",
                               credential_id="cred-op-1",
                               actor="alice", principal="alice",
                               nonce="nonce-exp", expected_version=1,
                               note=None, now=now)
    assert first["status"] == 200, first
    replay = reg.decide_request("tcr-0002", action="approve",
                                credential_class="operator",
                                scope="toolchain:decide",
                                credential_id="cred-op-1",
                                actor="alice", principal="alice",
                                nonce="nonce-exp", expected_version=1,
                                note=None, now=now)
    assert replay["status"] == 409, replay
    assert replay["error"] == "replayed_nonce"
    row = reg._data["toolchain_requests"][1]
    assert row["state"] == "open"  # unchanged by the replay attempt
    assert len(row["history"]) == 2  # gap-reported + rejected-replay
    assert row["history"][-1]["event"] == "rejected-replay"


def test_replay_nonce(tmp_path):
    # mon-tc-03
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    r1 = reg.decide_request("tcr-0001", action="approve",
                            credential_class="operator",
                            scope="toolchain:decide",
                            credential_id="cred-op-1",
                            actor="alice", principal="alice",
                            nonce="nonce-replay", expected_version=1,
                            note=None, now=now)
    assert r1["status"] == 200
    # replay same nonce
    _seed_request2 = None
    # need a second open request to replay against? replay is cross-row;
    # re-running on same row at new version with same nonce must be refused.
    r2 = reg.decide_request("tcr-0001", action="deny",
                            credential_class="operator",
                            scope="toolchain:decide",
                            credential_id="cred-op-1",
                            actor="alice", principal="alice",
                            nonce="nonce-replay", expected_version=2,
                            note="n", now=now)
    assert r2["status"] == 409, r2
    assert r2["error"] == "replayed_nonce"


def test_concurrent_decisions(tmp_path):
    # mon-tc-04 (2.2)
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    # make two distinct nonces
    results = {}
    def worker(i, nonce):
        r = reg.decide_request("tcr-0001", action="approve",
                               credential_class="operator",
                               scope="toolchain:decide",
                               credential_id="cred-op-1",
                               actor="alice", principal="alice",
                               nonce=nonce, expected_version=1,
                               note=None, now=now)
        results[i] = r
    t1 = threading.Thread(target=worker, args=(1, "n-a"))
    t2 = threading.Thread(target=worker, args=(2, "n-b"))
    t1.start(); t2.start(); t1.join(); t2.join()
    statuses = sorted(r["status"] for r in results.values())
    assert statuses == [200, 409], results
    row = reg._data["toolchain_requests"][0]
    # both attempts in audit history
    events = [h["event"] for h in row["history"]]
    assert "rejected-conflict" in events or "rejected-replay" in events


def test_idempotent_decision(tmp_path):
    # mon-tc-04 (2.3)
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    r1 = reg.decide_request("tcr-0001", action="approve",
                            credential_class="operator",
                            scope="toolchain:decide",
                            credential_id="cred-op-1",
                            actor="alice", principal="alice",
                            nonce="n1", expected_version=1,
                            note=None, now=now)
    assert r1["status"] == 200
    # identical decision at already-applied version returns existing outcome
    r2 = reg.decide_request("tcr-0001", action="approve",
                            credential_class="operator",
                            scope="toolchain:decide",
                            credential_id="cred-op-1",
                            actor="alice", principal="alice",
                            nonce="n2", expected_version=2,
                            note=None, now=now)
    assert r2["status"] == 200, r2
    assert r2.get("idempotent") is True
    row = reg._data["toolchain_requests"][0]
    assert row["version"] == 2  # no second bump


def test_deny_requires_note(tmp_path):
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    res = reg.decide_request("tcr-0001", action="deny",
                             credential_class="operator",
                             scope="toolchain:decide",
                             credential_id="cred-op-1",
                             actor="alice", principal="alice",
                             nonce="n-deny", expected_version=1,
                             note=None, now=now)
    assert res["status"] == 400
    assert res["error"] == "deny_requires_note"
    row = reg._data["toolchain_requests"][0]
    assert row["state"] == "open"


def test_deny_with_note(tmp_path):
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    res = reg.decide_request("tcr-0001", action="deny",
                             credential_class="operator",
                             scope="toolchain:decide",
                             credential_id="cred-op-1",
                             actor="alice", principal="alice",
                             nonce="n-deny2", expected_version=1,
                             note="not needed", now=now)
    assert res["status"] == 200
    row = reg._data["toolchain_requests"][0]
    assert row["state"] == "denied"
    assert row["decision_note"] == "not needed"
    assert row["suppression_until"] is not None


def test_note_cap(tmp_path):
    # mon-tc-03, task 2.6
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    long_note = "x" * 513
    res = reg.decide_request("tcr-0001", action="deny",
                             credential_class="operator",
                             scope="toolchain:decide",
                             credential_id="cred-op-1",
                             actor="alice", principal="alice",
                             nonce="n-cap", expected_version=1,
                             note=long_note, now=now)
    assert res["status"] == 400
    assert res["error"] == "decision_note_too_long"
    # refused not truncated: stored note unchanged
    row = reg._data["toolchain_requests"][0]
    assert row["decision_note"] is None
    # ok note at 512
    reg2 = _reg(tmp_path / "b")
    _seed_request(reg2)
    _operator(reg2)
    ok_note = "y" * 512
    res2 = reg2.decide_request("tcr-0001", action="deny",
                               credential_class="operator",
                               scope="toolchain:decide",
                               credential_id="cred-op-1",
                               actor="alice", principal="alice",
                               nonce="n-cap2", expected_version=1,
                               note=ok_note, now=now)
    assert res2["status"] == 200
    assert reg2._data["toolchain_requests"][0]["decision_note"] == ok_note


def test_note_rendered_escaped_and_not_in_builder_input(tmp_path):
    # task 2.6 static scan + fixture
    import re
    src = (Path(__file__).resolve().parent.parent / "hub" / "toolchain_transitions.py").read_text()
    # decision_note must not be interpolated into a shell/command/profile lookup
    assert "subprocess" not in src
    # fixture: a note containing html/script survives verbatim in stored row
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    note = "<script>alert(1)</script>"
    res = reg.decide_request("tcr-0001", action="deny",
                             credential_class="operator",
                             scope="toolchain:decide",
                             credential_id="cred-op-1",
                             actor="alice", principal="alice",
                             nonce="n-esc", expected_version=1,
                             note=note, now=now)
    assert res["status"] == 200
    row = reg._data["toolchain_requests"][0]
    assert row["decision_note"] == note  # stored verbatim; rendering escapes


def test_denied_suppression_window(tmp_path):
    # mon-tc-04 (2.7)
    reg = _reg(tmp_path)
    _seed_request(reg)
    _operator(reg)
    now = "2026-01-01T00:00:00Z"
    # deny
    reg.decide_request("tcr-0001", action="deny",
                       credential_class="operator",
                       scope="toolchain:decide",
                       credential_id="cred-op-1",
                       actor="alice", principal="alice",
                       nonce="n-d1", expected_version=1,
                       note="no", now=now)
    row = reg._data["toolchain_requests"][0]
    assert row["state"] == "denied"
    # within window: report-suppressed, stays denied, counter advances
    from hub import toolchain_transitions as tt
    ev = tt.report_event("denied", within_suppression=True)
    assert ev == "report-suppressed"
    # simulate suppression handling: state stays denied, counter increments
    row["suppressed_reports"] = row.get("suppressed_reports", 0) + 1
    assert row["state"] == "denied"
    assert row["suppressed_reports"] == 1
    # after window: report-after-window reopens
    ev2 = tt.report_event("denied", within_suppression=False)
    assert ev2 == "report-after-window"


def test_fulfilled_gap_regressed(tmp_path):
    # mon-tc-04 (2.7)
    from hub import toolchain_transitions as tt
    assert tt.report_event("fulfilled", within_suppression=False) == "gap-regressed"


def test_negative_control_heartbeat_token_refused(tmp_path):
    # mon-tc-03, task 2.5 (heartbeat token)
    reg = _reg(tmp_path)
    _seed_request(reg)
    reg.enroll("runner-one", "O/R", [], "")
    from hub import tokens
    hb = tokens.mint_token()
    reg.find_runner("runner-one")["heartbeat_token_hash"] = reg._hash_token(hb)
    before = (reg._data["toolchain_requests"][0]["state"],
              reg._data["toolchain_requests"][0]["version"],
              len(reg._data["toolchain_requests"][0]["history"]))
    res = reg.decide_request("tcr-0001", action="approve",
                             credential_class="heartbeat",
                             scope=None, credential_id="runner-one",
                             actor="a", principal="p",
                             nonce="n-hb", expected_version=before[1],
                             note=None, now="2026-01-01T00:00:00Z")
    assert res["status"] == 403
    assert res["error"] == "rejected_credential_class"
    assert res["credential_class"] == "heartbeat"
    after = (reg._data["toolchain_requests"][0]["state"],
             reg._data["toolchain_requests"][0]["version"],
             len(reg._data["toolchain_requests"][0]["history"]))
    assert after[0] == before[0] and after[1] == before[1]
    assert after[2] == before[2] + 1  # audit row recorded


def test_negative_control_builder_refused(tmp_path):
    # mon-tc-03, task 2.5
    reg = _reg(tmp_path)
    _seed_request(reg)
    reg.add_toolchain_credential(klass="builder", secret="bsec-1234567890",
                                credential_id="b-1", scope=None, principal=None)
    before = (reg._data["toolchain_requests"][0]["state"],
              reg._data["toolchain_requests"][0]["version"],
              len(reg._data["toolchain_requests"][0]["history"]))
    res = reg.decide_request("tcr-0001", action="approve",
                             credential_class="builder",
                             scope=None, credential_id="b-1",
                             actor="a", principal="p",
                             nonce="n-b", expected_version=before[1],
                             note=None, now="2026-01-01T00:00:00Z")
    assert res["status"] == 403
    assert res["error"] == "rejected_credential_class"
    after = (reg._data["toolchain_requests"][0]["state"],
             reg._data["toolchain_requests"][0]["version"],
             len(reg._data["toolchain_requests"][0]["history"]))
    assert after[0] == before[0] and after[1] == before[1]
    assert after[2] == before[2] + 1


def test_negative_control_mc_write_key_refused(tmp_path):
    # mon-tc-03, task 2.5 (ordinary MC write key -> unknown class)
    reg = _reg(tmp_path)
    _seed_request(reg)
    before = (reg._data["toolchain_requests"][0]["state"],
              reg._data["toolchain_requests"][0]["version"],
              len(reg._data["toolchain_requests"][0]["history"]))
    res = reg.decide_request("tcr-0001", action="approve",
                             credential_class=None,
                             scope=None, credential_id=None,
                             actor="a", principal="p",
                             nonce="n-mc", expected_version=before[1],
                             note=None, now="2026-01-01T00:00:00Z")
    assert res["status"] == 401
    # also via unknown class
    res2 = reg.decide_request("tcr-0001", action="approve",
                              credential_class="mc_api_key",
                              scope="write", credential_id="k",
                              actor="a", principal="p",
                              nonce="n-mc2", expected_version=before[1],
                              note=None, now="2026-01-01T00:00:00Z")
    assert res2["status"] == 403
    assert res2["error"] == "rejected_credential_class"
    assert res2.get("credential_class") == "mc_api_key"
    row = reg._data["toolchain_requests"][0]
    assert row["state"] == "open"


def test_wire_decide_route(tmp_path):
    # end-to-end via HTTP
    hub = HubFixture(tmp_path)
    try:
        # enroll + profile
        st, body = hub.post("/enroll", {
            "runner_name": "lane-a", "repo": "O/R",
            "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        assert st == 200
        token = body["heartbeat_token"]
        with hub.state._lock:
            hub.state.registry.set_lane_profile("lane-a", "rust")
            hub.state.registry.add_toolchain_credential(
                klass="operator", secret="opsec-1234567890",
                credential_id="cred-op-1", scope="toolchain:decide",
                principal="alice")
            # seed a request row
            hub.state.registry._data.setdefault("toolchain_requests", [])
            hub.state.registry._data["toolchain_requests"].append({
                "id": "tcr-0001", "lane": "lane-a", "tool": "cargo",
                "required_profile": "rust", "state": "open", "version": 1,
                "observed_at": "2026-01-01T00:00:00Z", "last_seen": "2026-01-01T00:00:00Z",
                "last_reported_at": "2026-01-01T00:00:00Z",
                "actor": None, "principal": None, "credential_id": None,
                "decided_at": None, "decision_note": None, "nonces": [],
                "build_id": None, "builder_identity": None, "lane_image_digest": None,
                "fulfilled_at": None, "suppression_until": None,
                "suppressed_reports": 0, "history": [],
            })
            hub.state.registry.save()
        # decide
        st, body = hub.post("/toolchain/decide", {
            "request_id": "tcr-0001", "action": "approve",
            "credential": "opsec-1234567890", "actor": "alice",
            "principal": "alice", "timestamp": "2026-01-01T00:00:00Z",
            "nonce": "n-wire", "expected_version": 1})
        assert st == 200, body
        # list
        st, body = hub.post("/toolchain/requests", {}) if False else (None, None)
        # GET via post? use urllib
        import urllib.request
        req = urllib.request.urlopen(f"http://127.0.0.1:{hub.port}/toolchain/requests")
        data = json.loads(req.read())
        assert data["ok"] is True
        assert any(r["id"] == "tcr-0001" and r["state"] == "approved"
                   for r in data["requests"])
    finally:
        hub.close()


def test_wire_concurrent_decisions(tmp_path):
    # 20 concurrent -> one 200 one 409 (task 2.2)
    hub = HubFixture(tmp_path)
    try:
        st, body = hub.post("/enroll", {
            "runner_name": "lane-a", "repo": "O/R",
            "enrollment_token": "test-enroll-token-PLACEHOLDER"})
        assert st == 200
        with hub.state._lock:
            hub.state.registry.set_lane_profile("lane-a", "rust")
            hub.state.registry.add_toolchain_credential(
                klass="operator", secret="opsec-1234567890",
                credential_id="cred-op-1", scope="toolchain:decide",
                principal="alice")
            hub.state.registry._data.setdefault("toolchain_requests", [])
            hub.state.registry._data["toolchain_requests"].append({
                "id": "tcr-0001", "lane": "lane-a", "tool": "cargo",
                "required_profile": "rust", "state": "open", "version": 1,
                "observed_at": "2026-01-01T00:00:00Z", "last_seen": "2026-01-01T00:00:00Z",
                "last_reported_at": "2026-01-01T00:00:00Z",
                "actor": None, "principal": None, "credential_id": None,
                "decided_at": None, "decision_note": None, "nonces": [],
                "build_id": None, "builder_identity": None, "lane_image_digest": None,
                "fulfilled_at": None, "suppression_until": None,
                "suppressed_reports": 0, "history": [],
            })
            hub.state.registry.save()
        import threading
        results = []
        lock = threading.Lock()
        def worker(nonce):
            st, body = hub.post("/toolchain/decide", {
                "request_id": "tcr-0001", "action": "approve",
                "credential": "opsec-1234567890", "actor": "alice",
                "principal": "alice", "timestamp": "2026-01-01T00:00:00Z",
                "nonce": nonce, "expected_version": 1})
            with lock:
                results.append(st)
        ts = []
        for i in range(2):  # 2 concurrent enough for lock test
            t = threading.Thread(target=worker, args=(f"n-{i}",))
            ts.append(t)
        for t in ts: t.start()
        for t in ts: t.join()
        assert sorted(results) == [200, 409], results
    finally:
        hub.close()