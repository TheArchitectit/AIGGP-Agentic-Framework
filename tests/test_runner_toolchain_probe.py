"""The runner spoke's toolchain probe (mon-tc-01, spoke side).

What this covers is the part of the capability that only exists once a real tick
runs: the hub echoes what a lane's reviewed profile requires, the tick caches that
echo, the NEXT tick probes exactly those names inside its own PATH and posts the
difference back — plus the run-outcome flag that is the hub's only way to learn
`probe-failed` (mon-tc-06). No hub process is involved: the curl stub answers with
the same field the real handler now sends.

The three shapes this suite exists to keep distinct, because collapsing any two of
them is the defect class this capability was designed against:

  * **no cache** (a fresh host) → the tick sends NEITHER gap field. Absent means
    "no evidence", and a tick that posted `[]` before probing anything would
    report a provisioned lane out of thin air;
  * **a requirement list** → probe it, and report what is missing under the bound;
  * **null from the hub** (no reviewed profile) → not an empty list. Caching it as
    one would render `profile-unassigned` as "my image has everything", which is
    exactly the absence-reported-as-health the spec names.

Also asserted here: the probe can never fail the tick. A heartbeat that dies blinds
the whole fleet, which is worse than a toolchain field that reads unknown — so a
missing library, a torn cache and a probe that hangs all end as absent fields and
exit 0, the same shape the evaluator-image probe above it uses.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_toolchain_probe.py`
runs them too.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures.runner_spoke import Spoke  # noqa: E402
from tests.platform_caps import require_symlink  # noqa: E402

# One parent up is the checkout, and this is the same anchor the Spoke fixture
# refuses to trust unchecked: get it wrong and the suite silently loads a probe
# from somewhere else, or from nowhere at all. Checked rather than assumed.
PROBE_LIB = Path(__file__).resolve().parents[1] / "scripts" / "lib" / "toolchain_probe.py"
if not PROBE_LIB.is_file():
    raise RuntimeError(
        f"no probe library at {PROBE_LIB} — either it moved or this file has, "
        "and the parent-count above needs adjusting")

# The hub's own required list, as it arrives in the response body. `rust` per the
# spec's profile table (cargo, gcc, make); a test that wants a different profile
# passes its own list to the fixture knob instead of editing this.
REQUIRED = '["cargo", "gcc", "make"]'


def _body(s):
    posts = s.requests("/heartbeat")
    assert posts, "no heartbeat was POSTed"
    return json.loads(posts[-1]["data"])


def _stub_bin(tmp_path, names, slow=()):
    """A directory of stub programs, used as RUNNER_PROBE_PATH.

    Deliberately NOT the suite's PATH: the probe is supposed to observe the
    runner image, and the knob that says so is the same one the containerised
    runner will use. Pointing it at a directory the test built is the only way to
    make "the image lacks cargo" a fact rather than an opinion about the machine
    running the suite.

    `slow` names programs that outlive the probe bound, which is how `unknown`
    gets produced on purpose. Everything written here is executable, and the one
    test that needs a NON-executable file writes it itself rather than through
    this helper: a knob no caller passes is a branch nothing measures.
    """
    d = tmp_path / "imagebin"
    d.mkdir(exist_ok=True)
    for name in names:
        p = d / name
        p.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        p.chmod(0o755)
    for name in slow:
        p = d / name
        p.write_text("#!/usr/bin/env sh\nsleep 5\n", encoding="utf-8")
        p.chmod(0o755)
    return d


def _enrolled(tmp_path, runner="alpha"):
    s = Spoke(tmp_path)
    assert s.enroll(runner).returncode == 0
    return s


# --- the round trip: echo -> cache -> probe -> report -------------------------


def test_enrollment_installs_the_probe_the_heartbeat_resolves(tmp_path):
    """An installed copy must be present AND runnable, not merely intended.

    The F2/F9 lineage in mutation_battery_runner_sweep.py exists because a helper
    that was installed under a name its resolver did not use passed every
    presence test that suite had. This asserts the two things that were actually
    wrong there: the file is there, under the name the sibling lookup uses, and it
    imports.
    """
    s = _enrolled(tmp_path)
    lib = s.probe_lib()
    assert lib.is_file(), f"the probe was never installed: {lib}"
    assert (tmp_path / "home" / ".config" / "containers" / "toolchain_probe.py").samefile(lib)
    spec = importlib.util.spec_from_file_location("installed_probe", str(lib))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "probe_required"), "installed copy is not the probe library"


def test_the_first_tick_after_enrollment_sends_no_gap_fields(tmp_path):
    """Absence, not an empty list (mon-tc-06).

    A fresh host has never been told what its lane requires, so it has no
    opinion. Reporting `[]` would be the hub reading "this image has everything
    the lane requires" from a spoke that never looked.
    """
    s = _enrolled(tmp_path)
    res = s.run_helper("alpha")
    assert res.returncode == 0, res.stderr
    body = _body(s)
    assert "missing_tools" not in body, body
    assert "missing_tools_probe_complete" not in body, body


def test_the_hubs_echo_seeds_the_next_tick(tmp_path):
    """The capability is only reachable at all if the echo seeds the NEXT tick.

    Gating the echo on an incoming gap field would deadlock it: no cache means no
    gap field, no gap field means no echo. Two real ticks are run here rather than
    one plus a hand-written cache, because the seam between the two — response
    written by tick 1, read by tick 2 — is where that deadlock would appear.
    """
    s = _enrolled(tmp_path)
    # gcc and make are in the image; cargo is not.
    stub = _stub_bin(tmp_path, ["gcc", "make"])

    first = s.run_helper("alpha", STUB_SERVED_REQUIRED=REQUIRED)
    assert first.returncode == 0, first.stderr
    assert s.read_required("alpha") == ["cargo", "gcc", "make"], \
        "the tick did not cache the hub's requirement list"

    second = s.run_helper("alpha", RUNNER_PROBE_PATH=str(stub))
    assert second.returncode == 0, second.stderr
    body = _body(s)
    assert body["missing_tools"] == ["cargo"], body
    # A complete run says so: the flag travels with the list, never alone.
    assert body["missing_tools_probe_complete"] is True, body


def test_a_lane_with_no_reviewed_profile_is_never_asked_to_be_empty(tmp_path):
    """null is `profile-unassigned`, and caching it as `[]` is the bug.

    The hub sends null when nobody has reviewed the lane. A tick that turned that
    into an empty requirement would post an empty gap list, and mon-tc-06 makes an
    empty list a POSITIVE report — so the unreviewed lane would render as a
    provisioned one, which is the exact shape the spec's scenarios were written
    against.
    """
    s = _enrolled(tmp_path)
    stub = _stub_bin(tmp_path, ["gcc", "make", "cargo"])
    res = s.run_helper("alpha", RUNNER_PROBE_PATH=str(stub),
                       STUB_SERVED_REQUIRED="null")
    assert res.returncode == 0, res.stderr
    assert s.read_required("alpha") is None, \
        "null was cached as a requirement, and the next tick will report a verdict"
    assert "missing_tools" not in _body(s)


def test_a_retracted_requirement_stops_being_reported_on_the_next_tick(tmp_path):
    """A cached list the hub no longer stands behind has to go, and this proves it went.

    The mirror image of the test above, catching the other mistake: an
    implementation that only ever WRITES the cache would keep a stale list forever,
    so a lane whose profile was narrowed back to none would go on reporting a gap
    the hub's own record no longer requires — forever, and correctly-looking.

    Asserted across TWO ticks because the lag is inherent, not a bug to be tested
    away: the tick reads its cache, probes, posts, and only then learns from the
    response that the requirement was retracted. So the retraction is visible in
    the cache at the end of tick 1 while tick 1's own report still names the old
    gap. Second-guessing that would mean withholding a report the hub asked for on
    the strength of a message that has not arrived yet. What is NOT acceptable, and
    is what tick 2 asserts, is a third tick still reporting it.
    """
    s = _enrolled(tmp_path)
    s.seed_required("alpha", ["cargo"])
    stub = _stub_bin(tmp_path, ["gcc", "make"])

    first = s.run_helper("alpha", RUNNER_PROBE_PATH=str(stub), STUB_SERVED_REQUIRED="null")
    assert first.returncode == 0, first.stderr
    assert s.read_required("alpha") is None, "a retracted list survived in the cache"

    second = s.run_helper("alpha", RUNNER_PROBE_PATH=str(stub), STUB_SERVED_REQUIRED="null")
    assert second.returncode == 0, second.stderr
    assert "missing_tools" not in _body(s), \
        "the retracted requirement is still being reported one tick on"


def test_a_lane_that_has_everything_reports_the_empty_list(tmp_path):
    """mon-tc-01: required equals observed is `[]`, never the vocabulary's remainder.

    The mistake this pins is the natural one — a spoke that computes its gap as
    "vocabulary minus what I have", which on a healthy lane posts the 14 tools the
    lane was never supposed to carry, and on this spec's all-or-nothing rule would
    open a request per tool nobody asked for. It is the same assertion seen from
    the other side of test_the_hubs_echo_seeds_the_next_tick: there a gap is a
    list, here the absence of one is still a report, and mon-tc-06 makes [] the
    positive answer "my image has everything this lane requires".
    """
    s = _enrolled(tmp_path)
    stub = _stub_bin(tmp_path, ["cargo", "gcc", "make"])
    s.seed_required("alpha", ["cargo", "gcc", "make"])
    res = s.run_helper("alpha", RUNNER_PROBE_PATH=str(stub))
    assert res.returncode == 0, res.stderr
    body = _body(s)
    assert body["missing_tools"] == [], \
        f"a provisioned lane must report [], got {body['missing_tools']!r}"
    assert body["missing_tools_probe_complete"] is True


def test_a_probe_that_outlives_its_bound_is_unknown_not_absent(tmp_path):
    """mon-tc-01/mon-tc-06: `unknown` is the only honest answer, and it is loud.

    A tool that hangs is the case the whole three-state rule exists for. Two
    assertions, and the second is the reason the first is not enough: a missing
    list that excludes the unknown tool must still say the run was incomplete, or
    the hub sees an empty gap list and reads a provisioned lane. This is the only
    place `probe-failed` can ever originate.
    """
    s = _enrolled(tmp_path)
    # Named `mvn`, not `maven`: mon-tc-01 fixes maven's probe as `mvn -version`
    # (a maven binary alone is not present without a working JDK), so the program
    # that has to hang is the one that rule actually executes. A stub named
    # `maven` would be an unrelated file the probe never looks at.
    stub = _stub_bin(tmp_path, ["gcc"], slow=["mvn"])
    s.seed_required("alpha", ["maven", "gcc"])
    res = s.run_helper("alpha", RUNNER_PROBE_PATH=str(stub),
                       TOOL_PROBE_TIMEOUT_S="0.2")
    assert res.returncode == 0, res.stderr
    body = _body(s)
    assert body["missing_tools"] == [], \
        f"a timed-out probe must not be reported as absent: {body}"
    assert body["missing_tools_probe_complete"] is False, \
        "an incomplete run reported as complete is absence reported as health"


# --- the probe cannot break a tick -------------------------------------------


def test_a_host_without_the_probe_library_still_heartbeats(tmp_path):
    """The honest degradation: stop talking about toolchain, keep ticking.

    Built by removing the installed copy after enrolling, which is what a host
    whose install predates the probe looks like — not a synthetic checkout. The
    run-state fields go absent and the tick still exits 0, because the fleet needs
    the heartbeat more than it needs this field.
    """
    s = _enrolled(tmp_path)
    lib = s.probe_lib()
    lib.unlink()
    s.seed_required("alpha", ["cargo"])
    res = s.run_helper("alpha", RUNNER_PROBE_PATH=str(_stub_bin(tmp_path, [])))
    assert res.returncode == 0, f"a missing probe must not fail the tick: {res.stderr}"
    body = _body(s)
    assert "missing_tools" not in body
    assert "disk_ok" in body, "the rest of the heartbeat still went out"


def test_a_torn_cache_produces_no_opinion(tmp_path):
    """A hand-edited or half-written cache yields absence, never a partial probe.

    Written with the shell's own scratch path so this is the real file the tick
    reads. `[]` would be a verdict; the tick is not allowed to infer one from
    bytes it cannot trust.
    """
    s = _enrolled(tmp_path)
    cache = s.seed_required("alpha", ["cargo"])
    cache.write_text('{"required_tools": ["car', encoding="utf-8")  # torn JSON
    res = s.run_helper("alpha", RUNNER_PROBE_PATH=str(_stub_bin(tmp_path, [])))
    assert res.returncode == 0, res.stderr
    assert "missing_tools" not in _body(s)


def test_an_empty_probe_path_still_answers_for_every_required_tool(tmp_path):
    """An empty PATH is "every tool is absent", which is a real report.

    A probe that reported nothing here would be indistinguishable from a lane with
    nothing required. Note this is NOT the no-cache case: the requirement list
    came from the hub, so the spoke does have an opinion, and it is a negative one.
    """
    s = _enrolled(tmp_path)
    s.seed_required("alpha", ["cargo", "gcc"])
    empty = tmp_path / "emptybin"
    empty.mkdir()
    res = s.run_helper("alpha", RUNNER_PROBE_PATH=str(empty))
    assert res.returncode == 0, res.stderr
    body = _body(s)
    assert body["missing_tools"] == ["cargo", "gcc"], body
    assert body["missing_tools_probe_complete"] is True


# --- the probe library's own rules (mon-tc-01, fixed probes) ------------------


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_under_test", str(PROBE_LIB))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_python_is_python3_and_pip_is_the_module_not_the_binary():
    """The two fixed rules most easily got wrong by writing the obvious probe.

    `pip` present because a `pip` binary exists is wrong twice over: the spec says
    `python3 -m pip`, and a python3 without the module is `absent` — so a stub
    interpreter that fails the module invocation must produce absent, which an
    existence check cannot see.
    """
    require_symlink("the pip probe is exercised against a stub python3")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        py = d / "python3"
        py.write_text("#!/usr/bin/env sh\nexit 1\n", encoding="utf-8")
        py.chmod(0o755)
        mod = _load_probe()
        dirs = [str(d)]
        assert mod.probe_tool("python", dirs, 5) == mod.PRESENT
        assert mod.probe_tool("pip", dirs, 5) == mod.ABSENT, \
            "a python3 with no pip module is absent, never present"


def test_gpp_is_never_inferred_from_gcc():
    """The spec names this explicitly because it is the obvious shortcut."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "gcc").write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        (d / "gcc").chmod(0o755)
        mod = _load_probe()
        dirs = [str(d)]
        assert mod.probe_tool("gcc", dirs, 5) == mod.PRESENT
        assert mod.probe_tool("g++", dirs, 5) == mod.ABSENT


def test_a_non_executable_file_is_not_a_tool_present():
    """A stray `cargo` data file must not close a real gap.

    Checked with the exec bit rather than trusting `shutil.which`, which resolves
    through PATH semantics this probe deliberately does not have.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        p = d / "cargo"
        p.write_text("not a binary\n", encoding="utf-8")
        p.chmod(0o644)
        assert not os.access(p, os.X_OK), "the fixture is not testing what it says"
        mod = _load_probe()
        assert mod.probe_tool("cargo", [str(d)], 5) == mod.ABSENT


def test_required_excludes_unknowns_from_missing_and_reports_incomplete():
    """The library-level statement of the rule the tick depends on.

    Kept as a direct call rather than only through a tick so the failure names the
    function: when this rule breaks, the spoke suite's tick-level failure is
    three layers away from the cause.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        stub = _stub_bin(Path(td), ["gcc"], slow=["mvn"])
        os.environ["RUNNER_PROBE_PATH"] = str(stub)
        try:
            mod = _load_probe()
            missing, complete = mod.probe_required(["maven", "gcc", "cargo"], timeout=0.2)
        finally:
            del os.environ["RUNNER_PROBE_PATH"]
        assert missing == ["cargo"], missing
        assert complete is False


def test_the_manifest_the_task_names_required_cargo_gcc_observed_gcc():
    """The literal case task 4.2 states, asserted at the library level.

    Kept as its own test with its own stub directory rather than appended to the
    one above: the dir there holds `cargo` (it has to, to make `mvn` the only
    unknown), so asking the same directory for required-minus-observed of
    [cargo, gcc] yields `[]` and proves nothing about a missing tool. Measured the
    hard way — an earlier draft reused that dir and asserted the opposite.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        stub = _stub_bin(Path(td), ["gcc"])
        os.environ["RUNNER_PROBE_PATH"] = str(stub)
        try:
            mod = _load_probe()
            assert mod.probe_required(["cargo", "gcc"], timeout=5) == (["cargo"], True)
        finally:
            del os.environ["RUNNER_PROBE_PATH"]


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
