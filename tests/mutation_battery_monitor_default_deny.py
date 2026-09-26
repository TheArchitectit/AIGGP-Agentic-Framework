#!/usr/bin/env python3
"""Mutation battery for the hub monitor's NON-PASS classification (coh-int-05,
fleet half — S6 line: "Adapter default-deny").

The monitor is the fleet ADAPTER for the coherence gate's CI conclusion: it
transports the workflow run's conclusion into an alert class and computes
nothing. Before this slice it classified only `failure` (plus `skipped`, with
its own coh-int-06 class), so a FRESH run concluding timed_out / cancelled /
action_required / neutral / stale fell through to the recency window and read
healthy — adapter default-allow, the state the requirement forbids. The fix is
a membership table, and a membership table fails by losing a member, so each
mutation below DELETES one member and names the test that must notice. Three
structural mutations round it out: reverting a call site to the pre-fix
literal comparison (coherence and drift separately — the same defect class at
different sites must not share one killer), and adding `skipped` to the table
(would fold coh-int-06's distinct class into the failure alert).

The test's own probe list is deliberately NOT imported from production —
test_hub_monitor_default_deny.py writes its members out, so shrinking the
production table fails there rather than shrinking in silence.

Negative control: shrink the TEST's probe list while production's table is
whole — the suite MUST survive (it still tests everything production
promises). A battery that reported this as a kill would be misreading its own
detection.

Run from the repository root.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

MON = "hub/monitor.py"
T = "tests/test_hub_monitor_default_deny.py"
C_TEST = T + "::test_coherence_fresh_nonpassing_conclusion_alerts_never_reads_healthy"
D_TEST = T + "::test_drift_fresh_nonpassing_conclusion_alerts_never_reads_healthy"
G_TEST = T + "::test_gates_nonpassing_check_run_conclusion_alerts"
S_TEST = T + "::test_skipped_keeps_its_own_coherence_class"

TABLE_FULL = ('NON_PASSING_CONCLUSIONS = frozenset(\n'
              '    {"failure", "timed_out", "cancelled", "action_required", "neutral", "stale"})')


def _drop(member):
    """Anchor on the full table, replacement removes one member cleanly."""
    mutated = TABLE_FULL.replace(member + ", ", "").replace(", " + member, "")
    return [(MON, TABLE_FULL, mutated)]


COH_SITE = ('        if latest.get("conclusion") in NON_PASSING_CONCLUSIONS:\n'
            "            # coh-int-05 fleet half")
COH_REVERT = ('        if latest.get("conclusion") == "failure":\n'
              "            # coh-int-05 fleet half")
DRIFT_SITE = ('        if latest.get("conclusion") in NON_PASSING_CONCLUSIONS:\n'
              '            self._raise_alert(\n'
              '                repo, "drift_failed", "?",')
DRIFT_REVERT = ('        if latest.get("conclusion") == "failure":\n'
                '            self._raise_alert(\n'
                '                repo, "drift_failed", "?",')
GATE_SITE = "if conclusion in NON_PASSING_CONCLUSIONS:"
GATE_REVERT = 'if conclusion in ("failure", "timed_out"):'

MUTATIONS = [
    ("M1: `timed_out` dropped — the template's own timeout path un-alerted",
     _drop('"timed_out"'), [C_TEST], {}),
    ("M2: `cancelled` dropped (the most-used non-pass conclusion in the fleet's own history)",
     _drop('"cancelled"'), [C_TEST], {}),
    ("M3: `action_required` dropped",
     _drop('"action_required"'), [C_TEST], {}),
    ("M4: `neutral` dropped",
     _drop('"neutral"'), [C_TEST], {}),
    ("M5: `stale` dropped",
     _drop('"stale"'), [C_TEST], {}),
    ("M6: coherence site reverts to the pre-fix literal `== \"failure\"`",
     [(MON, COH_SITE, COH_REVERT)], [C_TEST], {}),
    ("M7: drift site reverts to the pre-fix literal — the table is whole but unread here",
     [(MON, DRIFT_SITE, DRIFT_REVERT)], [D_TEST], {}),
    ("M8: check-run site reverts to the old two-member tuple",
     [(MON, GATE_SITE, GATE_REVERT)], [G_TEST], {}),
    ("M9: `skipped` folded into the table — coh-int-06's class disappears into failure",
     [(MON, '"neutral", "stale"})', '"neutral", "stale", "skipped"})')],
     [S_TEST], {}),
]

NEGATIVE_CONTROLS = [
    ("N1: shrink the TEST's probe list with production's table whole — must survive",
     [(T, 'NON_PASSING = ("failure", "timed_out", "cancelled", "action_required",\n'
          '               "neutral", "stale")',
       'NON_PASSING = ("failure", "timed_out")')],
     [T], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it pins the battery's own kill detection, "
        "not a fixture property"))
