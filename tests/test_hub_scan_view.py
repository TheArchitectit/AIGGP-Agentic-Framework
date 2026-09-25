"""Tests for hub/scan_view.py — the fleet view of what a host's sweep found.

secret-scan-07's rendering half. 5.3a stored the state and shipped it; this is
where it becomes something an operator reads, and the requirement it serves is
one sentence: a repository with no recorded scan state SHALL be rendered as
unknown, never as healthy.

Pure functions over a runner dict, so the four ways a host can be non-clean are
each testable without a hub, an API, or a timer:

  * never reported — the host's helper predates the transport (every host
    enrolled before 5.3a is in this state),
  * reported but unreadable — the report exists and will not parse,
  * reported, readable, and holding an uncovered secret,
  * reported, readable, and holding a repository the sweep could not fetch.

The fifth case is the one that must stay quiet: everything clean.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_scan_view.py`
runs them too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.scan_view import scan_alerts  # noqa: E402


def _repo(name, state, **over) -> dict:
    """One repository record, shaped as 5.3a ships it."""
    base = {"name": name, "state": state, "reason": None, "scope": "all",
            "scanned_at": "2026-09-25T00:00:00Z", "findings": 0, "uncovered": 0}
    base.update(over)
    return base


def _state(*repos, unreadable=None) -> dict:
    return {"repos": list(repos), "unreadable": unreadable}


def test_a_host_that_never_reported_renders_unknown():
    """Not silence, and not clean. A helper that predates the transport reports
    nothing about scanning, and `None` is what the hub stores for that — the
    whole already-enrolled fleet, on the day this ships."""
    for runner in ({"name": "r1"}, {"name": "r1", "scan_state": None}):
        alerts = scan_alerts(runner)
        assert len(alerts) == 1, (runner, alerts)
        check_class, detail = alerts[0]
        assert check_class == "runner_scan_unknown", check_class
        assert "has not reported" in detail, detail


def test_an_unreadable_report_says_so_and_is_not_unknown_silence():
    """The sentence has to differ from the never-reported one, not just a
    trailing parenthetical: "provision the host" and "fix what it reported" are
    different actions, and an operator skimming the fleet reads the first
    clause. Same split as the image check's unknown-vs-cannot-serve."""
    alerts = scan_alerts({"name": "r1", "scan_state": _state(
        unreadable="JSONDecodeError: Expecting value: line 1 column 1")})
    assert len(alerts) == 1, alerts
    check_class, detail = alerts[0]
    assert check_class == "runner_scan_unknown", check_class
    assert "could not be read" in detail, detail
    assert "JSONDecodeError" in detail, "the host's own reason is dropped"
    assert "has not reported" not in detail, (
        "an unreadable report is rendered as if the host said nothing: "
        f"{detail}")


def test_an_unreadable_report_with_no_reason_still_says_what_is_wrong():
    """`{"repos": {}}` is unreadable with no reason string — the shape is wrong
    and nothing recorded why. Falling back to an empty detail would render a
    fault as a blank.

    The field is asserted with its QUOTES, and the never-reported sentence with
    an explicit absence. A bare `"repos" in detail` is satisfied by the fallback
    sentence's own word "repositories": this mutation survived the first run of
    the battery (V7) on exactly that, while the report rendered as a host that
    had said nothing at all.
    """
    alerts = scan_alerts({"name": "r1", "scan_state": {"repos": {}}})
    assert len(alerts) == 1, alerts
    check_class, detail = alerts[0]
    assert check_class == "runner_scan_unknown", check_class
    assert detail.strip(), "an unreadable report rendered as an empty detail"
    assert "could not be read" in detail, detail
    assert "'repos'" in detail, f"the detail does not name the field: {detail}"
    assert "has not reported" not in detail, (
        f"a broken-shape report is rendered as if the host said nothing: {detail}")


def test_a_clean_fleet_is_silent():
    """The mirror case, or this check is an alert on every healthy host and the
    real ones stop being read."""
    runner = {"name": "r1", "scan_state": _state(
        _repo("alpha", "clean"), _repo("beta", "clean"))}
    assert scan_alerts(runner) == []


def test_an_uncovered_finding_names_the_repository_and_the_count():
    """A finding is the one state that must never be summarised away. The
    locations deliberately do NOT ride along — they are not shipped off the host
    (5.3a) — so the repository name and the count are all the fleet view has,
    and both have to be here or the alert says only 'something, somewhere'."""
    runner = {"name": "r1", "scan_state": _state(
        _repo("alpha", "findings", findings=3, uncovered=2),
        _repo("beta", "clean"))}
    alerts = scan_alerts(runner)
    assert len(alerts) == 1, alerts
    check_class, detail = alerts[0]
    assert check_class == "runner_scan_findings", check_class
    assert "alpha" in detail, detail
    assert "beta" not in detail, (
        f"a clean repository is named in a findings alert: {detail}")
    # BOTH counts, in one substring. `"3" in detail or "2" in detail` was here
    # first and could not fail for the second count: a renderer printing only
    # the total satisfies the `or`, which is the sentence the docstring above
    # says sends an operator hunting for a leak that is already allowlisted.
    assert "(2 uncovered of 3 finding(s))" in detail, (
        f"the detail does not carry both counts: {detail}")


def test_a_repository_the_sweep_could_not_scan_renders_unknown_not_clean():
    """The requirement's first scenario, at the rendering end: the sweep reported
    the reason rather than dropping the repository, and the fleet view must not
    promote the omission back into a pass."""
    runner = {"name": "r1", "scan_state": _state(
        _repo("gone", "unfetchable", reason="could not fetch: repository not found"),
        _repo("alpha", "clean"))}
    alerts = scan_alerts(runner)
    assert len(alerts) == 1, alerts
    check_class, detail = alerts[0]
    assert check_class == "runner_scan_unknown", check_class
    assert "gone" in detail, detail
    assert "could not fetch: repository not found" in detail, (
        f"the reason the sweep gave is dropped: {detail}")
    assert "alpha" not in detail, f"a clean repository is named: {detail}"


def test_an_unscannable_repository_is_reported_the_same_way_as_an_unfetchable_one():
    """`unscannable` is the other half of the sweep's could-not-scan pair (the
    scanner was unusable, or the gate refused the repository). Both mean no
    verdict, and a renderer that knows only `unfetchable` would show the
    scanner-fault case as clean."""
    runner = {"name": "r1", "scan_state": _state(
        _repo("alpha", "unscannable", reason="scanner unusable: gitleaks missing"))}
    alerts = scan_alerts(runner)
    assert len(alerts) == 1, alerts
    assert alerts[0][0] == "runner_scan_unknown", alerts[0]
    assert "gitleaks missing" in alerts[0][1], alerts[0][1]


def test_a_no_verdict_repository_with_no_reason_says_so_rather_than_nothing():
    """`why = reason or "no reason recorded"` — the ONE branch in the module that
    no test reached, found by an adversarial audit. The shipped sweep always
    records a reason for these two states, so this is only reachable from a
    spoke that posted a null one, which is exactly the input this module exists
    to render: host-supplied and stored unvalidated. Deleting the right operand
    (`why = reason`) left the whole suite green, because the reason-dropping
    mutation replaces the entire expression and is killed by the truthy case.
    """
    runner = {"name": "r1", "scan_state": _state(_repo("gone", "unfetchable"))}
    alerts = scan_alerts(runner)
    assert len(alerts) == 1, alerts
    assert alerts[0][0] == "runner_scan_unknown", alerts[0]
    assert "gone" in alerts[0][1], alerts[0][1]
    assert "no reason recorded" in alerts[0][1], (
        f"a no-verdict repository with a null reason renders as if the sweep "
        f"gave a cause, or as if there were none: {alerts[0][1]}")


def test_a_host_that_both_leaked_and_failed_to_scan_reports_both():
    """One tuple would hide one of them, and which one is hidden is an accident
    of iteration order. The leak is the more urgent of the two, so it comes
    first."""
    runner = {"name": "r1", "scan_state": _state(
        _repo("alpha", "findings", findings=1, uncovered=1),
        _repo("gone", "unfetchable", reason="could not fetch: timeout"))}
    alerts = scan_alerts(runner)
    assert [a[0] for a in alerts] == ["runner_scan_findings", "runner_scan_unknown"], alerts
    assert "alpha" in alerts[0][1] and "gone" in alerts[1][1], alerts


def test_a_state_the_renderer_does_not_know_renders_unknown_not_clean():
    """Silence has to be a WHITELIST on `clean`, never a blacklist on the states
    this file happens to know. `state` is host-supplied and stored unvalidated
    (the predicate's docstring spells out what a spoke can put there), so a sweep
    that grows a fifth state — or a spoke that reports nonsense — arrives here as
    a word this renderer has never seen. Treating it as its own category would
    print "everything else is fine" over the one repository nobody has a verdict
    for, which is the requirement's exact failure with a new spelling."""
    runner = {"name": "r1", "scan_state": _state(
        _repo("alpha", "partially-scanned"), _repo("beta", "clean"))}
    alerts = scan_alerts(runner)
    assert len(alerts) == 1, alerts
    assert alerts[0][0] == "runner_scan_unknown", alerts[0]
    assert "alpha" in alerts[0][1] and "partially-scanned" in alerts[0][1], alerts[0][1]


def test_a_report_whose_entries_are_not_records_renders_unknown_without_dying():
    """`repos` is a list of anything a spoke posted. The predicate guarantees the
    LIST, not what is in it, and this is the fleet view reading host-supplied
    input: an entry that is not a record must render as a repository with no
    verdict — not raise, and not vanish. A renderer that reached in with `.get()`
    would take the whole dashboard down, which is worse than the unknown it was
    trying to report; a renderer that skipped it would shorten the list, which
    is how a fleet reads clean while blind.
    """
    runner = {"name": "r1", "scan_state": _state(
        "alpha-is-not-a-record", {}, _repo("beta", "clean"))}
    alerts = scan_alerts(runner)
    assert len(alerts) == 1, alerts
    check_class, detail = alerts[0]
    assert check_class == "runner_scan_unknown", check_class
    assert detail.count("<unnamed repository>") == 2, (
        f"an unnameable entry is not rendered once per entry: {detail}")
    assert "beta" not in detail, f"the clean repository is named: {detail}"


def test_an_empty_but_well_formed_report_is_a_real_reading_not_an_alert():
    """The sweep refuses to run on an empty declaration, so a parsed report
    always lists what it was asked to scan — an empty list here is odd but it is
    a reading, and it is NOT unknown. Pinned because the opposite choice is
    tempting and would make `scan_state_unknown` and this renderer disagree
    about the same dict."""
    assert scan_alerts({"name": "r1", "scan_state": _state()}) == []


def main() -> int:
    import inspect
    import tempfile
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            with tempfile.TemporaryDirectory() as td:
                if "tmp_path" in inspect.signature(fn).parameters:
                    fn(Path(td))
                else:
                    fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
