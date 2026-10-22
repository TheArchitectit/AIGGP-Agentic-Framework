"""Wire-level tests for runner toolchain requests (mon-tc-02).

Split from `tests/test_hub_toolchain_requests.py` for the same reason that file is
split from `test_hub_registry.py`: a live fixture (a hub on an ephemeral port, an
enroll round-trip, an HTTP POST per case) is a different cost and a different kind
of failure. A unit failure means a rule is wrong; a wire failure can also mean the
handler, the presence-aware read, or the response shape broke, and paying a port
bind per case to find out the first kind is not worth it.

Kept here are the cases that only exist once bytes travel: that a rejected value is
not echoed back, that `g++` survives POST-to-disk, that 20 threads still yield one
row, and that a request row carries no credential.
"""
import json
import sys
import threading
import urllib  # noqa: F401  (HubFixture surfaces urllib.error; import kept explicit)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import toolchain_requests as tcr  # noqa: E402
from tests.test_hub_enroll_heartbeat import HubFixture  # noqa: E402

def _stored_text(hub) -> str:
    return (Path(hub.config.data_dir) / "runners.json").read_text()
def _heartbeat_fixture(tmp_path):
    """Live hub fixture with one enrolled lane. Returns (hub, token, name)."""
    hub = HubFixture(tmp_path)
    status, body = hub.post("/enroll", {
        "runner_name": "lane-gpp",
        "repo": "TheArchitectit/AIGGP-Agentic-Framework",
        "enrollment_token": "test-enroll-token-PLACEHOLDER",
        "labels": ["g++"],
        "host_alias": "lane-gpp",
    })
    assert status == 200, body
    token = body["heartbeat_token"]
    with hub.state._lock:
        hub.state.registry.set_lane_profile("lane-gpp", "rust")
    return hub, token, "lane-gpp"

def test_gap_report_is_not_a_credential_carrier(tmp_path):
    """mon-tc-01: the request body carries tool names, nothing else.

    A heartbeat token that leaks into a stored request would be a second place the
    secret lives, and mon-sec-02 says the registry read at rest yields no usable
    token. The gap path never sees the token — this asserts the write path does
    not accidentally forward the whole body.
    """
    hub, token, name = _heartbeat_fixture(tmp_path)
    with hub.state._lock:
        verifier = hub.state.registry.find_runner(name)["heartbeat_token_hash"]
    status, body = hub.post("/heartbeat", {"runner_name": name,
                                           "heartbeat_token": token,
                                           "missing_tools": ["g++"]})
    assert status == 200, body
    rows = [r for r in json.loads(_stored_text(hub))["toolchain_requests"]
            if r["lane"] == name]
    assert rows, "the report should have landed"
    for row in rows:
        blob = json.dumps(row)
        # The stored verifier AND the plaintext the spoke presented: neither is a
        # thing a request row has a use for, and mon-sec-02 is about the registry
        # read at rest yielding nothing usable.
        assert verifier not in blob, "a request row leaked the stored verifier"
        assert token not in blob, "a request row leaked the presented token"
    hub.close()

def test_concurrent_identical_reports_yield_one_row(tmp_path):
    """1.4: 20 threads, one physical lane, one row.

    `with_registry` serialises under a lock, which is the mechanism doing the
    work. This test is here for the day someone decides the lock is too coarse:
    the registry call would stay correct and the row count would become 20, and
    the operator would see a backlog of identical requests.
    """
    hub = HubFixture(tmp_path)
    _, body = hub.post("/enroll", {
        "runner_name": "racy", "repo": "TheArchitectit/AIGGP-Agentic-Framework",
        "enrollment_token": "test-enroll-token-PLACEHOLDER", "labels": [],
        "host_alias": "racy"})
    token = body["heartbeat_token"]
    with hub.state._lock:
        hub.state.registry.set_lane_profile("racy", "rust")
    results = []

    def beat():
        status, resp = hub.post("/heartbeat", {"runner_name": "racy",
                                               "heartbeat_token": token,
                                               "missing_tools": ["cargo"]})
        results.append((status, resp))

    threads = [threading.Thread(target=beat) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(status == 200 for status, _ in results), results
    rows = [r for r in json.loads(_stored_text(hub))["toolchain_requests"]
            if r["lane"] == "racy"]
    assert len(rows) == 1, f"{len(rows)} rows for one lane+tool"
    assert rows[0]["version"] == 1
    hub.close()

def test_gpp_byte_for_byte_end_to_end(tmp_path):
    """1.3: `g++` is the value the whole capability must carry byte-for-byte.

    The channels the task names are interesting because `+` behaves differently in
    each — it survives JSON verbatim, means "space" under form-encoded urldecode, is
    a regex quantifier, and is a legal file name. Two of the five the task lists
    **do not exist in this repository**: `hub/` has no CSV export and no HTML
    render. The operator-facing surface is the JSON registry plus
    `hub/scan_view.py`/`hub/coherence_view.py`, which build plain-text sentences,
    not markup — the only `<tr>` in the tree is in `tests/test_regression_sizes.py`.

    A test written against the task as written would have to invent both channels
    and would then be testing the invention rather than the code. What is asserted
    here is the property those channels would each have to preserve, from POST body
    to stored bytes, plus the two failure modes pinned in the abstract so whoever
    builds an export fails here first instead of shipping a silently-rewritten tool
    name. The task text is corrected in tasks.md with this reason.
    """
    hub, token, name = _heartbeat_fixture(tmp_path)
    status, body = hub.post("/heartbeat", {"runner_name": name,
                                           "heartbeat_token": token,
                                           "missing_tools": ["g++", "cargo"]})
    assert status == 200, body
    assert body["toolchain_requests_recorded"] == 2
    rows = {(r["lane"], r["tool"]): r
            for r in json.loads(_stored_text(hub))["toolchain_requests"]}
    assert set(rows) == {(name, "g++"), (name, "cargo")}
    assert json.dumps("g++") == '"g++"', "JSON must not touch the plus"
    # What the two missing channels would break on, pinned so whoever builds them
    # fails here first instead of shipping a silently-rewritten tool name:
    from urllib.parse import quote, unquote
    assert unquote(quote("g++", safe="")) == "g++", "urlencoded path/query must round-trip"
    assert quote("g++") == "g%2B%2B", "a bare + in a path is not a literal +"
    # The regex channel: as a PATTERN `g++` is `g` with a quantifier applied twice
    # (the second `+` makes the first lazy), so it degenerates to matching a bare
    # `g`. A filter written `re.sub(tool, "", line)` would therefore strip every
    # `g` from every line — silently, and from the wrong lines — instead of
    # erroring. Pinned so whoever builds an export escapes the value rather than
    # interpolating it into a pattern.
    import re
    assert re.findall("g++", "g++ gcc g+++") == ["g", "g", "g"], \
        "the metacharacter behaviour this test warns about has changed"
    assert re.findall(re.escape("g++"), "g++ gcc g+++") == ["g++", "g++"]
    # The vocabulary and the test must agree on WHICH name is the awkward one. This
    # failed loudly once, when `g++` was briefly absent from VOCABULARY while this
    # test still asserted it as the canonical value — the drift that matters, because
    # a spec value missing from the whitelist is a permanently refused report.
    assert "g++" in tcr.VOCABULARY, "the canonical value must be whitelisted"

def test_refusal_is_not_echoed_with_the_bad_value(tmp_path):
    """A response is a storage location the attacker gets to read (mon-tc-01)."""
    hub, token, name = _heartbeat_fixture(tmp_path)
    canary = "n0t_a_t00l_ᴬᴷᴵᴸᴸ"
    status, body = hub.post("/heartbeat", {"runner_name": name,
                                           "heartbeat_token": token,
                                           "missing_tools": [canary]})
    assert status == 200
    assert body["toolchain_rejection"] == tcr.REJECT_OUTSIDE_VOCABULARY
    assert body["toolchain_requests_recorded"] == 0
    assert canary not in json.dumps(body)
    hub.close()



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
