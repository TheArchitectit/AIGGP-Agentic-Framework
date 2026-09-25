#!/usr/bin/env python3
"""Mutation battery for the fleet view of a host's scan state (secret-scan-07).

The subject is a sentence an operator reads, and every mutation here makes that
sentence wrong in a way a dashboard cannot show — the failure this slice exists
to prevent, which is not "the state is missing" but "the state is missing and
the view says fine":

  * the renderer stops asking whether the state is USABLE at all (V1), which
    folds an unreadable report into a silent, empty fleet,
  * the unreadable report's own reason is dropped (V6), so "fix what the host
    reported" becomes "provision the host,
  * a broken-shape report loses the field that is actually wrong (V7),
  * silence stops being a whitelist on `clean` (V3), so the first unrecognised
    word from a future sweep reads as a pass — the requirement's exact failure
    with a new spelling,
  * `unscannable` falls out of the no-verdict pair (V4), showing a scanner fault
    as clean for any fleet whose scanner never ran,
  * the reason the sweep gave is dropped (V5),
  * a real leak loses its check_class (V2) or its repository name (V8) — an
    operator gets "something, somewhere" or "unknown" for the one state that
    must never be summarised away,
  * two readings on one host collapse to one alert (V9),
  * host-supplied input stops being type-checked (V10), turning a hostile or
    buggy spoke into a dashboard that raises instead of reporting,
  * a finding loses the count that says whether it is already allowlisted
    (V11) and a verdict-less repository with no recorded cause renders none
    (V12) — both found by an adversarial audit of this diff, not by the author,
  * and the wiring itself: the poll loop stops dispatching (M1), drops the
    runner's name (M2) — leaving the two hosts indistinguishable — renders
    only the first host in the fleet (M3), or lets a call that can raise run
    BEFORE the checks that read only the registry (M4), which silences them
    for the length of a network outage.

Every Python edit is compiled before it is run, so no verdict here comes from a
syntax error, and every anchor is counted before it is replaced, so a drifted
anchor is reported as stale rather than silently skipped.

The kills span two suites, which is the honest shape of the change: the
sentences are one module's, and the dispatch and the attribution are the poll
loop's.

The harness does NOT first check that the named test passes unmutated (see
`NEGATIVE_CONTROLS` below, and task 23 in the ledger), so a suite that was
already failing would have every mutation naming it credited as a kill. One
control per suite is what makes that visible here.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

VIEW = "hub/scan_view.py"
MON = "hub/monitor.py"

T_VIEW = "tests/test_hub_scan_view.py"
T_MON = "tests/test_hub_monitor.py"

MUTATIONS = [
    # --- hub/scan_view.py: the sentences ------------------------------------

    # V1 — the renderer stops asking the predicate and asks a narrower question
    # instead. A host that reported an unreadable report still HAS a state, so
    # its `repos` (an empty list) renders as a clean fleet: the leak the
    # requirement is about, produced by the view rather than by the sweep.
    ("V1: the renderer stops asking whether the state is usable",
     [(VIEW, "    if registry.scan_state_unknown(runner):",
             "    if runner.get(\"scan_state\") is None:")],
     [T_VIEW], {}),

    # V2 — a leak loses its check_class. The alert still arrives, as an unknown
    # one, which an operator triaging "which of my repositories leaked" cannot
    # tell from "which hosts have not been swept".
    ("V2: a finding is rendered as the catch-all unknown class",
     [(VIEW, "        if state == _FINDINGS:", "        if False:")],
     [T_VIEW], {}),

    # V3 — silence becomes a blacklist on the states this file knows, instead of
    # a whitelist on `clean`. Every unrecognised word reads as a pass.
    ("V3: silence is a blacklist on the known bad states, not a whitelist on clean",
     [(VIEW, "        elif state != _CLEAN:", "        elif state in _NO_VERDICT:")],
     [T_VIEW], {}),

    # V4 — the no-verdict pair loses its other half: a scanner that could not
    # run is no longer a no-verdict state, and the reason goes with it.
    ("V4: `unscannable` is not a no-verdict state",
     [(VIEW, '_NO_VERDICT = ("unfetchable", "unscannable")',
             '_NO_VERDICT = ("unfetchable",)')],
     [T_VIEW], {}),

    # V5 — the reason the sweep gave is replaced by a placeholder. The alert
    # still fires; the operator just cannot tell a deleted repository from a
    # broken scanner.
    ("V5: the reason a repository could not be scanned is dropped",
     [(VIEW, '            why = reason or "no reason recorded"',
             '            why = "no reason recorded"')],
     [T_VIEW], {}),

    # V6 — the unreadable branch is dropped, so a report that parsed as nothing
    # is rendered as a host that reported nothing.
    ("V6: an unreadable report is rendered as a host that has not reported",
     [(VIEW, '        if reason:\n'
             '            detail = f"its scan report could not be read: {reason}"\n'
             '        elif isinstance(state, dict):',
             '        if False:\n'
             '            detail = f"its scan report could not be read: {reason}"\n'
             '        elif isinstance(state, dict):')],
     [T_VIEW], {}),

    # V7 — a report whose shape is wrong loses the sentence naming WHAT is
    # wrong, and falls through to "has not reported" — sending an operator to
    # provision a host that is already reporting.
    ("V7: a broken-shape report is rendered as a host that has not reported",
     [(VIEW, "        elif isinstance(state, dict):", "        elif False:")],
     [T_VIEW], {}),

    # V8 — the finding loses the repository it is in. Names and counts are all
    # the fleet view has (the locations stay on the host), so this is the whole
    # detail.
    ("V8: a finding no longer names the repository it is in",
     [(VIEW, '        parts.append(f"{_name_of(record)} ({uncovered} uncovered of {total} finding(s))")',
             '        parts.append(f"({uncovered} uncovered of {total} finding(s))")')],
     [T_VIEW], {}),

    # V9 — a host that both leaked and failed to scan reports only the leak.
    # Which of the two survives is then an accident of the guard's shape rather
    # than a decision, and the other is invisible.
    ("V9: only the leak is reported when a host also failed to scan",
     [(VIEW, "    if unknown:\n        alerts.append((\"runner_scan_unknown\", _unknown_detail(unknown)))",
             "    if unknown and not found:\n        alerts.append((\"runner_scan_unknown\", _unknown_detail(unknown)))")],
     [T_VIEW], {}),

    # V10 — host-supplied input stops being type-checked. `repos` is a list of
    # whatever a spoke posted, and the predicate guarantees the list, not its
    # contents: the renderer raises on the first entry that is not a record,
    # which takes the dashboard down instead of reporting an unknown.
    ("V10: a report entry that is not a record raises instead of rendering unknown",
     [(VIEW, '        state = record.get("state") if isinstance(record, dict) else None',
             '        state = record.get("state")')],
     [T_VIEW], {}),

    # --- hub/monitor.py: the dispatch and the attribution --------------------

    # M1 — the poll loop stops dispatching the check. Every clause of the
    # rendering can be perfect and no operator ever sees a sentence.
    ("M1: the poll loop stops dispatching the scan-state check",
     [(MON, "        self._check_scan_state(repo, runners)", "        pass  # mutated away")],
     [T_MON], {}),

    # M2 — the alert loses the host it is about. Both readings share
    # `runner_scan_unknown`, so the name is the only thing telling two hosts
    # apart on a fleet dashboard.
    ("M2: the alert no longer names the host it is about",
     [(MON, '                self._raise_alert(repo, check_class, runner["name"], detail)',
             '                self._raise_alert(repo, check_class, "?", detail)')],
     [T_MON], {}),

    # V11 — the findings detail loses the `uncovered` count and keeps only the
    # total. The sentence still names the repository and still says an uncovered
    # secret exists, so it reads as a working alert while sending an operator to
    # hunt a leak that a disposition already covers.
    ("V11: the findings detail drops the uncovered count",
     [(VIEW, '        parts.append(f"{_name_of(record)} ({uncovered} uncovered of {total} finding(s))")',
             '        parts.append(f"{_name_of(record)} ({total} finding(s))")')],
     [T_VIEW], {}),

    # V12 — the null-reason fallback is deleted, so a spoke that posted a
    # verdict-less record with no cause renders "None" into the sentence. V5
    # does not cover this: it replaces the whole expression, which the
    # truthy-reason test kills, leaving this operand untested until the audit
    # found it.
    ("V12: a no-verdict record with a null reason renders no cause at all",
     [(VIEW, '            why = reason or "no reason recorded"',
             '            why = reason')],
     [T_VIEW], {}),

    # M3 — only the first host in a repo's group is rendered. The fleet is not
    # one host, and which one is read is the registry's ordering.
    ("M3: only the first host of a repository's group is rendered",
     [(MON, "        for runner in runners:\n"
             "            for check_class, detail in scan_alerts(runner):",
             "        for runner in runners[:1]:\n"
             "            for check_class, detail in scan_alerts(runners[0]):")],
     [T_MON], {}),

    # M4 — a network call is put ahead of the registry-only checks. This is the
    # ordering defect an adversarial audit found by measurement, not by reading:
    # the client catches HTTPError but NOT URLError, so a refused connection
    # raises out of `_check_runner_status` into poll_cycle's per-repo handler
    # and aborts the checks after it. The dispatch is untouched and every
    # sentence is perfect; the alert is simply never reached.
    ("M4: a network call runs before the registry-only checks",
     [(MON, '        (Measured — placed last, a closed port silences both.)\n'
            '        """\n'
            '        owner = repo.split("/")[0]\n',
            '        (Measured — placed last, a closed port silences both.)\n'
            '        """\n'
            '        owner = repo.split("/")[0]\n'
            '        self._check_runner_status(repo, runners)  # mutated: a call that can raise\n')],
     [T_MON], {}),
]

# Must SURVIVE: one reworded comment per suite the kills come from, saying
# exactly the same thing and read by nothing. Each one proves its suite passes
# UNMUTATED and that the guards read behaviour rather than the prose around it —
# the two ways a battery can credit a kill it did not earn (the harness does not
# check the unmutated baseline itself; see task 23).
NEGATIVE_CONTROLS = [
    ("N1: a scan_view comment reworded, saying exactly the same thing",
     [(VIEW, "# The sweep's vocabulary (scripts/secret-scan-fleet.sh: clean, findings,",
             "# The sweep's own vocabulary (scripts/secret-scan-fleet.sh: clean, findings,")],
     [T_VIEW], {}),
    ("N2: a monitor comment reworded, saying exactly the same thing",
     [(MON, "# --- 3.6 Fleet scan state (secret-scan-07)",
            "# --- 3.6 The fleet sweep's scan state (secret-scan-07)")],
     [T_MON], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "these two MUST survive — one per suite the kills come from, proving "
        "each suite passes unmutated and reads the rendering rather than the "
        "comments beside it"))
