"""scan_view.py — what the fleet view says about the sweep's per-repo verdicts.

The rendering half of secret-scan-07. 5.3a ships the state (the sweep writes a
report per host, the heartbeat reduces it and posts it, the registry stores it);
this turns a stored runner into the sentences an operator reads. The requirement
it serves is one line: a repository with no recorded scan state SHALL be
rendered as unknown, never as healthy.

Kept out of hub/monitor.py deliberately. The monitor is at 433 of DevGate's own
500-line hard limit and the rendering is ~60 lines of it; more to the point, the
monitor is a timer, a GitHub client and a registry reader, and none of those are
needed to decide what a verdict should SAY. `scan_alerts` is a pure function of
one runner dict, so every case below is a unit test with no fixture — which is
the only reason the four non-clean cases can each be pinned separately.

WHO DECIDES WHAT. `registry.scan_state_unknown` decides whether there is a
usable reading at all; this module decides which sentence that reading earns. The
split matters because that predicate is also the heartbeat's contract on the
spoke side and the thing a future dashboard keys on — a renderer that made its
own "is this usable" judgement would be the second reader of one fact, which is
this repository's recurring failure. So `scan_state_unknown` is imported, never
re-implemented.

The two buckets it collapses are told apart here without disagreeing with it:
"could not be read" is derived from the state's own `unreadable` field or from
its broken shape, and everything else is "has not reported". Both are unknown,
both alert, and both say which fix is needed.

SILENCE IS A WHITELIST. The only repository state rendered as quiet is `clean`.
`findings` alerts. `unfetchable` and `unscannable` alert. Any other word —
including one a future sweep invents, or nonsense from a compromised spoke —
alerts as unknown. Written as a whitelist on the silent case on purpose: the
`state` field is host-supplied and stored unvalidated, so a blacklist would read
the first unrecognised word as a pass, which is the requirement's exact failure
wearing a new spelling.
"""

from __future__ import annotations

from . import registry

# // spec: secret-scan-07 — the rendering half: a repository with no recorded
# scan state renders as unknown, never as healthy.

# The sweep's vocabulary (scripts/secret-scan-fleet.sh: clean, findings,
# unfetchable, unscannable). `clean` is the ONLY silent one.
_CLEAN = "clean"
_FINDINGS = "findings"
_NO_VERDICT = ("unfetchable", "unscannable")


def _name_of(record) -> str:
    """A repository's name for the alert detail, however damaged the record.

    `repos` is guaranteed to be a list by the predicate, but NOT to contain
    dicts — a hostile or buggy spoke can post `["x"]` — so the element type is
    checked rather than assumed. An unnamed record still gets rendered: dropping
    it would turn "one repository I cannot describe" into a shorter list, which
    is how a fleet reads clean while blind.
    """
    if isinstance(record, dict):
        name = record.get("name")
        if isinstance(name, str) and name:
            return name
    return "<unnamed repository>"


def _findings_detail(bad: list) -> str:
    """Name every repository holding an uncovered secret, with its counts.

    The locations deliberately do NOT ride along (the heartbeat ships the fact,
    not every finding's path), so the name and the counts are everything the
    fleet view has. Both counts are given because they answer different
    questions and the sweep keeps them apart: `uncovered` is what an operator
    has to fix, `findings` is everything the scanner matched including what a
    disposition already covers. A sentence carrying only the total would send
    someone hunting for a leak that is already allowlisted.
    """
    parts = []
    for record in bad:
        uncovered = record.get("uncovered", 0)
        total = record.get("findings", 0)
        parts.append(f"{_name_of(record)} ({uncovered} uncovered of {total} finding(s))")
    return ("uncovered secret(s) in " + ", ".join(parts))


def _unknown_detail(bad: list) -> str:
    """Name every repository with no verdict, and why there is none.

    One sentence for three causes — the sweep could not fetch it, could not
    scan it, or used a word this view does not know — because the reading is
    the same in all three: no verdict. The cause is carried so the operator can
    act (a deleted repository and a broken scanner are different tickets).
    """
    parts = []
    for record in bad:
        if not isinstance(record, dict):
            parts.append(f"{_name_of(record)} (the record is not a repository "
                         f"entry at all)")
            continue
        state = record.get("state")
        reason = record.get("reason")
        if state in _NO_VERDICT:
            why = reason or "no reason recorded"
            parts.append(f"{_name_of(record)} ({state}: {why})")
        else:
            parts.append(f"{_name_of(record)} (reports state {state!r}, which "
                         f"this view has no verdict for)")
    return "no verdict for " + ", ".join(parts)


def scan_alerts(runner: dict) -> list[tuple[str, str]]:
    """The alerts one runner's stored scan state earns, most urgent first.

    Returns (check_class, detail) pairs; empty when every repository is clean,
    or when the host reported a well-formed empty report. `runner` is the
    registry dict, not the state alone, so the absent/null distinction stays
    where `scan_state_unknown` makes it.

    Two alerts are returned when a host both leaked and failed to scan. One
    would hide the other, and which one survived would be an accident of
    iteration order; the leak is the more urgent of the two, so it leads.
    """
    if registry.scan_state_unknown(runner):
        state = runner.get("scan_state")
        reason = state.get("unreadable") if isinstance(state, dict) else None
        if reason:
            detail = f"its scan report could not be read: {reason}"
        elif isinstance(state, dict):
            # The only other way to be unusable with a dict in hand is a `repos`
            # that is not a list — which is not an empty fleet, and saying so is
            # the point. This names the field because "could not be read" alone
            # sends an operator looking for a parse error that is not there.
            detail = ("its scan report could not be read: it names no "
                      "repositories at all (no 'repos' list), which is not the "
                      "same as a fleet with nothing in it")
        else:
            detail = ("this host has not reported a fleet scan report, so none "
                      "of its repositories can be counted clean")
        return [("runner_scan_unknown", detail)]

    # One walk, each record into exactly one bucket. Not two comprehensions
    # filtered against each other: `r not in found` compares dicts by EQUALITY,
    # so two identical records — same name, same state — would have the second
    # one dropped from the unknown list as though it were a duplicate.
    found: list = []
    unknown: list = []
    for record in runner["scan_state"]["repos"]:
        state = record.get("state") if isinstance(record, dict) else None
        if state == _FINDINGS:
            found.append(record)
        elif state != _CLEAN:
            unknown.append(record)

    alerts = []
    if found:
        alerts.append(("runner_scan_findings", _findings_detail(found)))
    if unknown:
        alerts.append(("runner_scan_unknown", _unknown_detail(unknown)))
    return alerts
