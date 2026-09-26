"""The fleet sweep's report reaches the hub on the heartbeat (secret-scan-07).

Split from `test_runner_enroll_sweep.py` for room rather than for a limit: that
file is 497 lines, and a test file's hard limit is 600, not 500 — the 500
applies to SOURCE files (`TEST_HARD` in scripts/regression_sizes.py; the
mutation batteries, which are not `test_`-prefixed, are classified as source and
do answer to 500). The earlier docstring in that file says "at the hard limit"
and is wrong; the reason for this file is the ordinary one, that a new subject
wants its own home instead of making one long file of two.

The sweep writes a REPORT FILE on the runner; the heartbeat is a POST BODY. So
the state travels the way the image state does — a field on the heartbeat — and
the interesting question is not the field, it is the path: TWO processes now
read one file on two different timers, and the sweep and the heartbeat decide
that path independently unless something stops them.

What this file pins is that nothing stops them by accident:

  * the path is computed ONCE, by enrollment, and reaches both carriers — the
    sweep unit's `--report` argument and the env file the heartbeat reads — and
    a test asserts the two agree rather than trusting that they were written
    from the same variable;
  * the heartbeat never derives the path itself. It cannot: the unit names the
    file with `$SLUG` (sanitized) and the heartbeat knows `$RUNNER_NAME` (not
    sanitized), so a runner named `prod/web 1` would have the heartbeat looking
    at a different filename than the sweep writes. That is the two-readers-one-
    fact divergence this repository has already been bitten by twice;
  * absence is a POSITIVE report. No report file is `scan_state: null`, not an
    omitted key and not an empty-but-clean fleet, and the tick still exits 0 —
    a heartbeat that dies blinds the whole fleet;
  * a report that will not parse is `unreadable`, never a clean fleet. The
    sweep rewrites this file on its own timer, so a reader racing a writer is a
    live case and not a hypothetical one.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_scan_report.py`
runs them too.
"""
import json
import re
import sys
from pathlib import Path

# Only so `tests.fixtures` imports in the standalone run (`python3
# tests/test_runner_scan_report.py`, whose sys.path[0] is tests/ and not the
# repo root); pytest resolves it either way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures.runner_spoke import Spoke  # noqa: E402
# The fleet's own harness, for the one test that joins the two halves: the
# sweep's report is the input the heartbeat reads, and a report this file wrote
# itself would be asserting the contract against itself.
from tests.test_secret_scan_fleet import Fleet  # noqa: E402
import pytest

# Requires Unix tooling (bash/chmod/fcntl/systemctl/podman): these tests
# shell out to things that do not exist on Windows, so they cannot run there.
# A test that cannot run must SKIP, not fail -- failing here is indistinguishable
# from real breakage.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires Unix tooling")


# --- the report the sweep writes, in its own shape ---------------------------
#
# Two repositories on purpose: one scanned clean and one that could not be
# fetched. The second is the whole point of the requirement — a repository the
# sweep could not reach must arrive with its reason, not be dropped, because a
# fleet view that shows only what it managed to scan reads clean exactly when
# it is most blind.
def _report():
    return {
        "declared": 2,
        "scanned": 1,
        "states": {"clean": 1, "findings": 0, "unfetchable": 1, "unscannable": 0},
        "repos": [
            {"name": "alpha", "url": "https://example.test/alpha.git",
             "state": "clean", "reason": None, "scope": "all",
             "scanned_at": "2026-09-24T00:00:00Z", "findings": 0, "uncovered": 0,
             "locations": []},
            {"name": "beta", "url": "https://example.test/beta.git",
             "state": "unfetchable", "reason": "clone failed: not found",
             "scope": None, "scanned_at": None, "findings": 0, "uncovered": 0,
             "locations": []},
        ],
    }


def _last_heartbeat_body(s):
    posts = s.requests("/heartbeat")
    assert posts, "no heartbeat was POSTed"
    return json.loads(posts[-1]["data"])


def _env_value(s, runner, key):
    """The value the unit's EnvironmentFile gives for one key, as systemd
    would read it — the file is the carrier, so it is read the way systemd
    reads it and not through an exporter of the script's own."""
    for line in s.env_file(runner).read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None


def _unit_report_path(s, runner):
    """The path the SWEEP UNIT names, read out of the generated unit file.

    Deliberately parsed out of the text systemd will read rather than from the
    shell variable enrollment used to write it: a unit that stopped naming the
    report at all, or named a different one, has to fail here.

    One matching pair of quotes comes off, because systemd unquotes an ExecStart
    argument and a report path is allowed to contain a space. That is the same
    strip enrollment applies to a quoted declaration, for the same reason — and
    asserted here rather than assumed, so a unit written `--report ""` (an
    empty argument, which the sweep would take as "no report") is not read as
    agreement.
    """
    unit = s.fleet_units(runner)[0].read_text(encoding="utf-8")
    match = re.search(r"--report\s+(\S+)", unit)
    assert match, f"the sweep unit names no --report path:\n{unit}"
    value = match.group(1)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _write_report(s, runner, doc):
    """Plant a report where the heartbeat will look for it."""
    path = Path(_env_value(s, runner, "SECRET_SCAN_REPORT"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return path


# --- one path, two carriers, and a test that they agree ----------------------
def test_the_report_path_is_written_to_the_env_file_the_heartbeat_reads(tmp_path):
    """Enrollment decides the path, and the heartbeat reads it. The heartbeat
    knows only `$RUNNER_NAME`; the unit names the file by `$SLUG`, which is the
    sanitized name, so a runner called `prod/web 1` has two different spellings
    of itself and only enrollment knows which one the file uses."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    value = _env_value(s, "alpha", "SECRET_SCAN_REPORT")
    assert value, f"no SECRET_SCAN_REPORT in {s.env_file('alpha')}"
    # The EXACT path, not merely "somewhere plausible": an earlier version of
    # this assertion accepted any path under the sandbox, which $HOME is too,
    # and a mutation that moved the report to ~/.cache walked straight through
    # it because BOTH carriers were built from the same variable and so still
    # agreed with each other. Agreement is the next test's subject; this one is
    # about WHICH directory, and it is pinned rather than left to the
    # implementation because it is a decision with a consequence: the runtime
    # directory is per-session, so a reboot leaves the fleet reading unknown
    # until the next sweep rather than reading a stale clean. That is the
    # behaviour the requirement wants — absence renders unknown, never healthy
    # — and it is worth failing here if someone moves it to a directory that
    # survives, without meaning to change that reading.
    assert value == f"{s.env['XDG_RUNTIME_DIR']}/devgate-secretscan-alpha.json", value


def test_the_sweep_unit_reports_to_the_path_the_heartbeat_reads(tmp_path):
    """THE agreement test. Two carriers, one computation, and nothing but this
    asserts they still match: the sweep writing to a file the heartbeat never
    reads is a fleet that reads unknown forever, silently, on every host."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    assert _unit_report_path(s, "alpha") == \
        _env_value(s, "alpha", "SECRET_SCAN_REPORT")


def test_a_runner_name_needing_a_slug_does_not_split_the_two_carriers(tmp_path):
    """`prod/web 1` sanitizes to `prod-web-1`. The unit names the file by the
    slug; if the heartbeat ever derived the path from RUNNER_NAME instead of
    reading it, this is the name where that divergence becomes a filename that
    does not exist — and the fleet reads unknown for a host that is scanning
    perfectly."""
    s = Spoke(tmp_path)
    assert s.enroll("prod/web 1").returncode == 0

    env_value = _env_value(s, "prod/web 1", "SECRET_SCAN_REPORT")
    assert env_value == \
        f"{s.env['XDG_RUNTIME_DIR']}/devgate-secretscan-prod-web-1.json", env_value
    assert _unit_report_path(s, "prod/web 1") == env_value


def test_a_re_enrollment_does_not_leave_a_second_report_path_behind(tmp_path):
    """The env file is rewritten on every enroll and the report key is one of
    the keys enrollment owns, so a re-enroll must not accumulate a second
    SECRET_SCAN_REPORT line — the heartbeat and any operator reading the file
    would then be looking at whichever line their reader happens to pick."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    assert s.enroll("alpha").returncode == 0

    lines = [l for l in s.env_file("alpha").read_text(encoding="utf-8").splitlines()
             if l.startswith("SECRET_SCAN_REPORT=")]
    assert len(lines) == 1, lines


# --- the state rides the heartbeat -------------------------------------------
def test_a_scanned_repository_rides_the_heartbeat_with_its_scope_and_time(tmp_path):
    """A positive report, per repository, carrying what the requirement asks
    for: the scope that was scanned and when."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    _write_report(s, "alpha", _report())

    res = s.run_helper("alpha")
    assert res.returncode == 0, f"the scan probe must not fail the tick: {res.stderr}"
    state = _last_heartbeat_body(s)["scan_state"]
    assert state is not None, "a report on disk must not arrive as unknown"
    assert state["unreadable"] is None, state

    alpha = next(r for r in state["repos"] if r["name"] == "alpha")
    assert alpha["state"] == "clean", alpha
    assert alpha["scope"] == "all", alpha
    assert alpha["scanned_at"] == "2026-09-24T00:00:00Z", alpha


def test_a_repository_that_could_not_be_scanned_arrives_with_its_reason(tmp_path):
    """The requirement's first scenario. Dropping it would leave a fleet view
    reading clean on the strength of the repositories that happened to work."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    _write_report(s, "alpha", _report())

    res = s.run_helper("alpha")
    assert res.returncode == 0, res.stderr
    repos = _last_heartbeat_body(s)["scan_state"]["repos"]
    beta = next((r for r in repos if r["name"] == "beta"), None)
    assert beta is not None, f"an unscannable repository was omitted: {repos}"
    assert beta["state"] == "unfetchable", beta
    assert beta["reason"] == "clone failed: not found", beta


def test_no_report_at_all_is_a_positive_report_of_unknown(tmp_path):
    """Absence is a fact, and it is not cleanliness. A key that is simply
    missing would mean "this spoke does not report scan state", which the hub
    keeps as its last-known value — a different thing entirely from "this
    spoke has nothing to report", which must clear it to unknown."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    res = s.run_helper("alpha")
    assert res.returncode == 0, res.stderr
    body = _last_heartbeat_body(s)
    assert "scan_state" in body, \
        "the key must be present and null, not omitted — omission clears nothing"
    assert body["scan_state"] is None, body["scan_state"]


def test_a_report_that_will_not_parse_is_unreadable_never_a_clean_fleet(tmp_path):
    """The sweep rewrites this file on its own timer while the heartbeat reads
    it, so a reader meeting a half-written file is a live case. The one answer
    that must never come out of it is "no repositories, therefore clean"."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    path = _write_report(s, "alpha", _report())
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: len(text) // 2], encoding="utf-8")

    res = s.run_helper("alpha")
    assert res.returncode == 0, f"a corrupt report must not fail the tick: {res.stderr}"
    state = _last_heartbeat_body(s)["scan_state"]
    assert state is not None, "a corrupt report is not the same as no report"
    assert state["repos"] == [], state
    assert state["unreadable"], f"the state must say why it is unreadable: {state}"


def test_a_report_whose_repos_is_not_a_list_is_unreadable_never_a_clean_fleet(tmp_path):
    """The guard one line under the parse check, and the one with the quietest
    failure of the whole reader: `doc["repos"]` succeeds for a DICT, so a report
    that is valid JSON, parses cleanly and carries `"repos": {}` would come out
    the other side as `{"repos": [], "unreadable": null}` — zero repositories,
    therefore nothing wrong. That is the sentence a dashboard shows for a clean
    fleet, produced from a report with no repositories in it.

    Nothing else in the tree feeds the reader a non-list `repos`, which is why
    this test exists: without it the `isinstance` check is a guard no mutation
    can kill and no test can notice, and removing it changes nothing observable
    until the day a sweep writes a shape nobody expected."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    for bad in ({}, "clean", 7, [{"name": "alpha"}]):
        path = _write_report(s, "alpha", _report())
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["repos"] = bad
        path.write_text(json.dumps(doc), encoding="utf-8")

        res = s.run_helper("alpha")
        assert res.returncode == 0, res.stderr
        state = _last_heartbeat_body(s)["scan_state"]
        assert state is not None, f"repos={bad!r} was read as no report at all"
        assert state["repos"] == [], f"repos={bad!r} was read as a fleet: {state}"
        assert state["unreadable"], \
            f"repos={bad!r} must be unreadable rather than empty-and-clean: {state}"


def test_an_unset_report_variable_is_unknown_and_not_an_error(tmp_path):
    """The line ABOVE the file check, and the case an old host is actually in:
    a runner enrolled before this feature has no SECRET_SCAN_REPORT key in its
    env file at all, so the variable reaches the reader unset. That must be the
    same positive report of absence as a missing file — null, key present, tick
    still succeeds — because the hub reads "omitted" and "null" differently, and
    a key dropped here would leave a stale verdict in place forever.

    The reader reaches this answer through the FileNotFoundError of `open("")`
    rather than through a branch of its own: a `if not path: return None` guard
    was removed in the audit because it was a second way to say the same thing
    that no test could tell apart from the first."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    envf = s.env_file("alpha")
    kept = [l for l in envf.read_text(encoding="utf-8").splitlines()
            if not l.startswith("SECRET_SCAN_REPORT=")]
    assert len(kept) < len(envf.read_text(encoding="utf-8").splitlines()), "nothing to remove"
    envf.write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert _env_value(s, "alpha", "SECRET_SCAN_REPORT") is None, "key still present"

    res = s.run_helper("alpha")
    assert res.returncode == 0, f"an unset report path must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert "scan_state" in body, "omission clears nothing — the key must be sent"
    assert body["scan_state"] is None, body["scan_state"]


def test_the_runtime_directory_falls_back_when_xdg_is_unset(tmp_path):
    """`runtime_dir()`'s fallback is the half of the path that runs on a host
    nobody configured. XDG_RUNTIME_DIR is set for a login session and NOT for a
    non-login ssh session, which is how a fleet is usually provisioned — and the
    user manager still sets it for the units it starts, so the sweep and the
    heartbeat would name different directories while both looked correct.

    Every other test in this file inherits a pinned XDG_RUNTIME_DIR from the
    sandbox, so without this one the fallback is exercised by nothing and could
    be deleted with the suite still green."""
    s = Spoke(tmp_path)
    s.env.pop("XDG_RUNTIME_DIR")
    assert s.enroll("alpha").returncode == 0, "enroll must not need XDG_RUNTIME_DIR"

    import os
    expected = f"/run/user/{os.getuid()}/devgate-secretscan-alpha.json"
    assert _env_value(s, "alpha", "SECRET_SCAN_REPORT") == expected
    assert _unit_report_path(s, "alpha") == expected, \
        "the two carriers must agree on the fallback as well as on the normal case"


def test_the_report_the_heartbeat_reads_is_the_one_the_sweep_actually_wrote(tmp_path):
    """The seam, joined. Every other test in this file plants a report it wrote
    itself, and every test in `test_secret_scan_fleet.py` checks a report the
    sweep wrote — so the two halves of one contract are each asserted against
    the OTHER half's idea of it. A field renamed on either side leaves both
    suites green and the fleet reading `unreadable` for every host.

    Nothing is faked here. The sweep runs for real over real git origins; it
    writes to the path ENROLLMENT computed, which is the path the heartbeat
    reads, so the plumbing is exercised end to end rather than assembled by the
    test. That the sweep's exit code is non-zero for an unfetchable repository
    is asserted too: the report is written on the failure path as well, which is
    the only path that matters for a fleet that is partly blind.
    """
    (tmp_path / "fleet").mkdir()
    (tmp_path / "spoke").mkdir()
    fleet = Fleet(tmp_path / "fleet")
    fleet.repo("alpha")                       # scannable and clean
    declared = fleet.declare(fleet.url("alpha"),
                             (tmp_path / "gone").as_uri())  # never fetched

    s = Spoke(tmp_path / "spoke")
    assert s.enroll("alpha").returncode == 0
    report = Path(_env_value(s, "alpha", "SECRET_SCAN_REPORT"))
    report.parent.mkdir(parents=True, exist_ok=True)

    swept = fleet.run(declared, "--report", str(report))
    assert report.exists(), f"the sweep wrote no report: {swept.stderr}"
    assert swept.returncode == 4, \
        f"an unfetchable repository is exit 4, not {swept.returncode}"

    res = s.run_helper("alpha")
    assert res.returncode == 0, f"the heartbeat must read what the sweep wrote: {res.stderr}"
    state = _last_heartbeat_body(s)["scan_state"]
    assert state is not None and state["unreadable"] is None, \
        f"the sweep's own report did not parse as the heartbeat expects it: {state}"

    shipped = {r["name"]: r for r in state["repos"]}
    assert set(shipped) == {"alpha", "gone"}, shipped
    assert shipped["alpha"]["state"] == "clean", shipped["alpha"]
    assert shipped["alpha"]["scope"], "a scanned repository carries what was scanned"
    assert shipped["gone"]["state"] == "unfetchable", shipped["gone"]
    assert shipped["gone"]["reason"], "an unfetchable repository carries why"


def test_the_locations_of_a_finding_are_not_shipped_off_the_host(tmp_path):
    """A deliberate reduction, pinned so it cannot quietly reverse: the report
    FILE carries the rule, path, line and commit of every finding so an
    operator on the host can act on it, and the heartbeat ships the per-repo
    STATE instead. A fleet dashboard needs to know that a repository has an
    uncovered secret; it does not need every finding's file path crossing the
    network on every tick, and shipping it would make the heartbeat grow with
    every finding in the fleet."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    doc = _report()
    doc["repos"][0].update(state="findings", findings=1,
                           locations=[{"rule": "aws-access-token",
                                       "path": "src/creds.py", "line": 12,
                                       "commit": "0" * 40}])
    _write_report(s, "alpha", doc)

    res = s.run_helper("alpha")
    assert res.returncode == 0, res.stderr
    alpha = next(r for r in _last_heartbeat_body(s)["scan_state"]["repos"]
                 if r["name"] == "alpha")
    assert alpha["state"] == "findings", alpha
    assert alpha["findings"] == 1, alpha
    assert "locations" not in alpha, alpha
    assert "src/creds.py" not in json.dumps(alpha), alpha


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
