#!/usr/bin/env python3
"""Mutation battery for the fleet sweep's place on a runner host (Sprint 5.2).

What is mutated here is everything between "a declaration exists in the env
file" and "a timer that scans the fleet is running" — the whole path a silent
failure travels to look like success:

  * the escaping of the declaration in the unit's ExecStart, which is the
    difference between systemd expanding it from the runner's EnvironmentFile
    and enroll's own shell freezing whatever IT held into the unit (F1),
  * the bare-path rule for ExecStart, without which the body loses its own
    variables (F10, incident #1's shape),
  * the second helper installation, without which the sweep's only sibling is
    missing at run time (F2), and the name it is installed under (F9),
  * the provisioning gate itself, both directions: enabling without a
    declaration and refusing to enable with one (F3/F4),
  * the file-existence half of that gate, which is `-s` rather than `-n` (F4),
  * the reader's parity with systemd's EnvironmentFile, which unquotes a value
    (F11), anchors the key at the start of the line (F5), and takes the last of
    a duplicated key (F6),
  * which env file the service reads (F8),
  * the revoke path, which must not leave a sweep running under a token the
    operator believes is gone (F7).

Every mutation leaves both shell files valid — `bash -n` cannot see any of them.
The verdicts are read from the generated unit files, the installed helper and
the recorded systemctl calls; three tests do additionally assert on a log
substring ("NOT enabled", which is an operator's only signal that the sweep
they think is running is not), and the negative control below is what
distinguishes those from the assertions that read behaviour.

The artifacts are shell, whose well-formedness the shared harness checks with
`bash -n`.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

LIB = "scripts/lib/runner-units.sh"
ENROLL = "scripts/runner-enroll.sh"
T = "tests/test_runner_enroll_sweep.py"

MUTATIONS = [
    # F1 — the dollar is unescaped, so enroll's own shell expands it while the
    # unit is being written, and what lands on disk is a literal path that no
    # later edit of the runner's env file can reach. Incident #1's shape, one
    # heredoc over.
    #
    # The ambient value in extra_env is what makes this evaluate THAT hazard.
    # Measured: with the ambient variable unset, the unescaped form makes enroll
    # abort under `set -u` ("SECRET_SCAN_DECLARED: unbound variable"), nothing is
    # installed, and the mutation is killed by whichever enrolling test runs
    # first — a true kill for a reason that says nothing about escaping, which
    # is how this battery credited F1 to the presence test. Set, enroll succeeds
    # with the ambient path frozen into the unit, and the killer is the test
    # that asserts the unit still carries the systemd token.
    ("F1: the declaration is expanded by enroll's shell instead of systemd's",
     [(LIB, 'ExecStart=$FLEET_HELPER --declared "\\$SECRET_SCAN_DECLARED"',
       'ExecStart=$FLEET_HELPER --declared "$SECRET_SCAN_DECLARED"')], [T],
     {"SECRET_SCAN_DECLARED": "/tmp/ambient-declared.txt"}),

    # F2 — the gate is not installed beside the sweep. The sweep resolves it as
    # $(dirname $0)/secret-scan.sh, so this is a helper that dies at its own
    # precondition on every tick: enrolled, enabled, and scanning nothing.
    ("F2: the gate the sweep runs is not installed",
     [(ENROLL, '    install_helper "Secret-scan gate" \\\n'
               '        "$REPO_ROOT/scripts/secret-scan.sh" "$GATE_HELPER"',
       '    : "Secret-scan gate" \\\n'
       '        "$REPO_ROOT/scripts/secret-scan.sh" "$GATE_HELPER"')], [T], {}),

    # F3 — the timer is enabled unconditionally. An unprovisioned host then
    # carries a unit that fails every tick, which on a dashboard is
    # indistinguishable from a sweep that ran and found nothing.
    #
    # F3, F4 and F12 mutate the SAME line on purpose, in three ways it can be
    # wrong, and each is killed by a different named test. An earlier draft had
    # the unset case in a separate `-z` branch; F3 survived then, because
    # `[ -s "" ]` is already false and the second branch caught it — a guard
    # nothing depended on. That collapsed the branches into one condition, and
    # the condition is now one grep rather than a `-s` test plus a second check
    # for the same reason.
    ("F3: the sweep timer is enabled without any declaration",
     [(LIB, "    if ! grep -qE '^[^#]*[^#[:space:]]' \"$declared\" 2>/dev/null; then\n",
            "    if false; then\n")], [T], {}),

    # F4 — the check is weakened back to "the file exists and is non-empty",
    # which a comments-only declaration satisfies while naming nothing. The
    # sweep exits 3 on that file, so the timer enabled here fails every tick.
    ("F4: a declaration naming no repository is treated as provisioning",
     [(LIB, "    if ! grep -qE '^[^#]*[^#[:space:]]' \"$declared\" 2>/dev/null; then\n",
            '    if [[ ! -s "$declared" ]]; then\n')], [T], {}),

    # F12 — the pattern stops matching the sweep's rule and starts imposing a
    # stricter one: a url that is indented (or has any leading whitespace) is
    # refused here while the sweep reads it and scans the fleet. That is a
    # false NEGATIVE, the direction that leaves a provisioned host believing a
    # working sweep is not provisioned — and it is not hypothetical: this exact
    # pattern was the one-line fix a review proposed.
    ("F12: the pattern refuses an indented url the sweep accepts",
     [(LIB, "'^[^#]*[^#[:space:]]'", "'^[^#[:space:]]'")], [T], {}),

    # F5 — the key lookup is not anchored, so `#SECRET_SCAN_DECLARED=/path`
    # reads as a live declaration. That is how an operator turns the sweep off
    # without losing the path, and systemd ignores the line.
    ("F5: a commented-out declaration is read as a live one",
     [(LIB, "grep -E '^SECRET_SCAN_DECLARED='", "grep -E 'SECRET_SCAN_DECLARED='")],
     [T], {}),

    # F6 — the FIRST duplicate wins instead of the last. systemd's
    # EnvironmentFile is last-assignment-wins, so a host where the operator
    # appended a corrected path would be judged on the stale one.
    ("F6: a duplicated declaration is read from the first line, not the last",
     [(LIB, "| tail -n 1 | cut -d= -f2-", "| head -n 1 | cut -d= -f2-")], [T], {}),

    # F7 — revoke leaves the sweep's units and timer behind. The env file the
    # `--declared` path comes from is deleted in the same breath, so the
    # leftover unit fails forever on a runner the operator believes is gone.
    ("F7: revoke leaves the sweep units on disk",
     [(ENROLL, '          "$CYC_TIMER_UNIT" "$CYC_SERVICE_UNIT" \\\n'
               '          "$FLEET_TIMER_UNIT" "$FLEET_SERVICE_UNIT"',
       '          "$CYC_TIMER_UNIT" "$CYC_SERVICE_UNIT"')], [T], {}),

    # F9 — the gate is installed under the wrong NAME. This is the bug this
    # slice actually shipped and then caught by running the installed helper:
    # `devgate-secret-scan.sh` is co-located with the sweep and byte-identical
    # to the repository's copy, and the sweep still cannot find it, because it
    # resolves the gate by the literal name `secret-scan.sh` in its own
    # directory. A test comparing the two files' presence, parent and bytes
    # passed the whole time — which is why F9's killer runs the helper.
    #
    # Two tests fail under it (the presence assertion and the end-to-end run),
    # and which one the harness credits is whichever pytest prints first rather
    # than the stronger one. Both are honest killers; the credit is not, and
    # the ledger says so rather than implying the end-to-end run is what fired.
    ("F9: the gate is installed under a name the sweep does not resolve",
     [(ENROLL, 'GATE_HELPER="$ENV_DIR/secret-scan.sh"',
               'GATE_HELPER="$ENV_DIR/devgate-secret-scan.sh"')], [T], {}),

    # F10 — the ExecStart is an inline shell body. incident #1's shape
    # (FAIL-6e7b6f84), pinned for the heartbeat and the cycle and now for the
    # sweep. It exists because the `bash -c` assertion this kills had no
    # mutation that could falsify it: an assertion no mutation can reach is a
    # test of the prose around it, which is the disease Sprint 4.3 was written
    # about. The body keeps the helper path and the systemd token, so the only
    # assertion that can see it is the one about the inline body.
    ("F10: the ExecStart is an inline bash -c body (incident #1's shape)",
     [(LIB, 'ExecStart=$FLEET_HELPER --declared "\\$SECRET_SCAN_DECLARED" --report "$SCAN_REPORT"',
            'ExecStart=/bin/bash -c \'exec $FLEET_HELPER --declared "\\$SECRET_SCAN_DECLARED" --report "$SCAN_REPORT"\'')],
     [T], {}),

    # F11 — the reader does not unquote. systemd unquotes an EnvironmentFile
    # value, so `SECRET_SCAN_DECLARED="/tmp/a b/declared.txt"` is a line it runs
    # perfectly; without the strip, enroll resolves the literal including the
    # quotes, finds no such file, and leaves a provisioned sweep disabled —
    # silently, because "not enabled" reads the same as "not provisioned".
    # The `:` keeps the case body valid shell, so `bash -n` sees nothing.
    ("F11: a quoted declaration path is read with its quotes still on it",
     [(LIB, '            declared="${declared:1:${#declared}-2}"',
            '            :')], [T], {}),

    # F8 — the sweep reads the host's env file rather than this runner's. Two
    # runners on one host would then sweep one operator's fleet under the
    # other's name, which is the clobber the per-runner layout prevents.
    ("F8: the sweep service reads the wrong EnvironmentFile",
     [(LIB, "install_fleet_sweep() {\n    cat > \"$FLEET_SERVICE_UNIT\"",
       "install_fleet_sweep() {\n    TICKET_FILE=\"$HOME/.devgate-heartbeat.env\"\n"
       "    cat > \"$FLEET_SERVICE_UNIT\"")], [T], {}),
]

# Must SURVIVE. An operator-guidance line reworded, saying exactly the same
# thing: no test reads it, and the branch it labels did not change. A battery
# whose mutation killed this too would be pinning prose rather than the
# dispositions above.
#
# It deliberately rewords the ADVICE, not the first line: a test does read
# "NOT enabled" there, because that substring is the only signal an operator
# gets that the sweep they think is running is not. Rewording that would be a
# second mutation, not a control.
NEGATIVE_CONTROLS = [
    ("N1: the operator-guidance line reworded, saying exactly the same thing",
     [(LIB, "  Set SECRET_SCAN_DECLARED=/path/to/declared-repos.txt (one repo URL per line) in $TICKET_FILE, then re-run enroll.",
       "  Add SECRET_SCAN_DECLARED= pointing at your repo list to $TICKET_FILE, then re-run enroll.")],
     [T], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it proves the guards read the units and the systemctl calls, not the messages"))
