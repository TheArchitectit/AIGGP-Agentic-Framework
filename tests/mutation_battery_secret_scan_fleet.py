#!/usr/bin/env python3
"""Mutation battery for the fleet secret sweep (secret-scan-07).

The requirement's whole subject is the difference between "we scanned it and it
was clean" and "we have no idea". So what is mutated here is the sweep's
disposition of each repository — which is the one thing an operator reads:

  * the exit code that carries "at least one repository could not be scanned",
  * the record that keeps an unfetchable repository in the report at all,
  * the branch that refuses to treat a crashed scanner as a clean fleet,
  * the branch that separates "the gate refused this repository" from clean,
  * the scope the gate is asked for, since a sweep that silently ran the tree
    scan alone misses the credential that was committed and then deleted,
  * the empty-declaration refusal, without which a sweep that measured nothing
    exits with the same code as success,
  * the finding state itself,
  * which end of the gate's output the recorded reason is read from.

Every one of these leaves the script syntactically valid, which is the point:
`bash -n` cannot see any of them, and an exit code is not a value a test can
read out of the script's text.

The artifacts are shell, whose well-formedness the shared harness checks with
`bash -n`.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

SCRIPT = "scripts/secret-scan-fleet.sh"
T = "tests/test_secret_scan_fleet.py"

MUTATIONS = [
    # F1 — the unknown exit code collapses to success. The report still carries
    # the unfetchable repository, so only the summary an operator's cron reads
    # is wrong — which is exactly the shape secret-scan-07 exists to stop.
    ("F1: an unscannable fleet exits 0 instead of 4",
     [(SCRIPT, "    exit 4\n", "    exit 0\n")], [T], {}),

    # F2 — the unfetchable repository is dropped from the report instead of
    # recorded. The fleet reads as a shorter, greener list.
    ("F2: an unfetchable repository is omitted from the report",
     [(SCRIPT, '        record "$name" "$url" unfetchable \\\n', "        : unfetchable \\\n")],
     [T], {}),

    # F3 — an empty declaration is allowed through. A sweep that scanned nothing
    # then exits with the code that means "every declared repository was clean".
    ("F3: a declaration naming nothing is accepted",
     [(SCRIPT, 'if [ "${#URLS[@]}" -eq 0 ]; then\n    die',
       'if false; then\n    die')], [T], {}),

    # F4 — a crashed scanner no longer aborts. The gate never ran, so no verdict
    # is trustworthy, and exiting 0 says the opposite.
    ("F4: a crashed scanner no longer aborts the sweep",
     [(SCRIPT, "    exit 2\n", "    exit 0\n")], [T], {}),

    # F5 — the scope narrows to the working tree. The push gate keeps the same
    # scope; a sweep that does too misses the whole reason it is a separate
    # invocation.
    ("F5: the gate is asked for the tree scan instead of the full history",
     [(SCRIPT, 'bash "$GATE" --all --repo "$dir"',
       'bash "$GATE" --tree --repo "$dir"')], [T], {}),

    # F6 — a repository the gate refused is recorded as clean rather than
    # unscannable. Nothing scanned it, so nothing may call it clean.
    ("F6: a repository the gate refused is recorded as clean",
     [(SCRIPT, '            record "$name" "$url" unscannable \\\n'
               '                "the gate refused this repository: ${why:-exit $rc}" "" 0 ""',
       '            record "$name" "$url" clean \\\n'
       '                "" all 0 ""')], [T], {}),

    # F7 — the finding state is never set. A fleet with a live credential
    # reports clean and exits 0.
    ("F7: a repository with a finding is recorded as clean",
     [(SCRIPT, "        state=findings\n", "        state=clean\n")], [T], {}),

    # F8 — the abort reason is read off the wrong end of the gate's output. The
    # gate echoes its scope before it runs the scanner, so a run that then dies
    # on the scanner has that scope line FIRST and the fault LAST: taking the
    # first line records "scope: full history (all refs), plus the working
    # tree" as why a repository could not be scanned, which reads as a
    # successful scan. This is the branch where the choice is observable —
    # an rc=3 refusal happens before the gate prints anything, so head and tail
    # agree there and neither is pinned.
    ("F8: the abort reason is taken from the gate's first line",
     [(SCRIPT, '            why="$(tail -n 1 "$TMPD/$IDX-gate.log" 2>/dev/null || true)"\n'
               '            record "$name" "$url" unscannable \\\n'
               '                "scanner unusable:',
       '            why="$(head -n 1 "$TMPD/$IDX-gate.log" 2>/dev/null || true)"\n'
       '            record "$name" "$url" unscannable \\\n'
       '                "scanner unusable:')], [T], {}),
]

# Must SURVIVE. A message reworded inside the sweep: no test reads this string,
# and the code it labels did not change. A battery whose mutation killed this
# too would be pinning prose rather than the dispositions above.
NEGATIVE_CONTROLS = [
    ("N1: the unknown summary reworded, saying exactly the same thing",
     [(SCRIPT, "[secret-scan-fleet] UNKNOWN: at least one declared repository",
       "[secret-scan-fleet] INCOMPLETE: at least one declared repository")],
     [T], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it proves the guards read the dispositions, not the messages"))
