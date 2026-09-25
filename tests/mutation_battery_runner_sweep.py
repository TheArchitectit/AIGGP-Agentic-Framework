#!/usr/bin/env python3
"""Mutation battery for the fleet sweep's place on a runner host (Sprint 5.2).

What is mutated here is everything between "a declaration exists in the env
file" and "a timer that scans the fleet is running" — the whole path a silent
failure travels to look like success:

  * the escaping of the declaration in the unit's ExecStart, which is the
    difference between systemd expanding it from the EnvironmentFile and
    enroll's own shell expanding it to nothing,
  * the second helper installation, without which the sweep's only sibling is
    missing at run time,
  * the provisioning gate itself, both directions: enabling without a
    declaration and refusing to enable with one,
  * the file-existence half of that gate, which is `-s` rather than `-n`,
  * the anchor on the key lookup, which is what separates a live declaration
    from a commented-out one,
  * which of a duplicated declaration is read, since systemd takes the last,
  * the revoke path, which must not leave a sweep running under a token the
    operator believes is gone.

Every mutation leaves both shell files valid, which is the point: `bash -n`
cannot see any of them, and no assertion here reads a message — the tests read
the generated unit files and the recorded systemctl calls.

The artifacts are shell, whose well-formedness the shared harness checks with
`bash -n`.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

LIB = "scripts/lib/runner-units.sh"
ENROLL = "scripts/runner-enroll.sh"
T = "tests/test_runner_enroll_sweep.py"

MUTATIONS = [
    # F1 — the dollar is unescaped, so enroll's shell expands it. The variable
    # is unset at that point (it lives in the file being written), so the unit
    # goes out as `--declared` with no argument and every tick exits 3 while
    # enrollment reports success. Incident #1's shape, one heredoc over.
    ("F1: the declaration is expanded by enroll's shell instead of systemd's",
     [(LIB, 'ExecStart=$FLEET_HELPER --declared "\\$SECRET_SCAN_DECLARED"',
       'ExecStart=$FLEET_HELPER --declared "$SECRET_SCAN_DECLARED"')], [T], {}),

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
    # F3 and F4 mutate the SAME line on purpose, in the two ways it can be
    # wrong, and each is killed by a different named test. An earlier draft had
    # the unset case in a separate `-z` branch; F3 survived then, because
    # `[ -s "" ]` is already false and the second branch caught it — a guard
    # nothing depended on. The branches were collapsed into this one condition.
    ("F3: the sweep timer is enabled without any declaration",
     [(LIB, '    if [[ ! -s "$declared" ]]; then\n', "    if false; then\n")],
     [T], {}),

    # F4 — a declaration naming a file that does not exist is treated as
    # provisioning. The key being set is not the same as the sweep being able
    # to run.
    ("F4: a declaration naming a missing file enables the timer",
     [(LIB, '    if [[ ! -s "$declared" ]]; then\n',
            '    if [[ ! -n "$declared" ]]; then\n')], [T], {}),

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
    ("F9: the gate is installed under a name the sweep does not resolve",
     [(ENROLL, 'GATE_HELPER="$ENV_DIR/secret-scan.sh"',
               'GATE_HELPER="$ENV_DIR/devgate-secret-scan.sh"')], [T], {}),

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
