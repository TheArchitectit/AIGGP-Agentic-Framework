#!/usr/bin/env python3
"""Mutation battery for tests/test_runbook_claims.py — the runbook claim-pinner
(the S6 line's "operator runbook" closure; doc-truth is load-bearing here
because an operator follows these files during an outage).

A claims-test is worthless if it passes when the claim is false, so every
mutation here makes ONE class of documented claim stale while leaving the rest
of the repo alone, and names the test that must notice:

  M1 outage:    edit a behavior anchor out of its runbook — the behavior-home
                test must catch that the doc no longer documents its behavior.
  M2 index:     drop a runbook row from README's table — the index test must
                catch an on-disk file the entry point does not list.
  M3 code:      renumber EXIT_PROTOCOL in result.py (a rename-without-docs) —
                the exit-code test is the one that reads result.py live and
                compares it to what the docs still cite. test_hub_coherence_exitcodes
                uses the SAME constant on both sides of its assert, so it stays
                green under this mutation — exactly why this test exists: it is
                the only one that checks doc-vs-code, not code-vs-code.
  M4 migration: rename a legacy unit that the migration guide names and the
                script removes — the migration-anchor test must catch the guide
                pointing at a unit that no longer exists. (test_runner_enroll
                shares this killer honestly: a real unit rename SHOULD break
                both, and the mutation proves neither silently ignores it.)

Negative control N1: a benign wording edit touching no anchor — the suite MUST
survive it. A battery that reported a survivor here as a kill would be
misreading its own detection.

Run from the repository root; it rewrites files in place and restores them.
"""
import sys

import mutation_harness  # noqa: E402

CLAIMS = "tests/test_runbook_claims.py"
BEHAVIOR = CLAIMS + "::test_each_s6_behavior_has_a_named_runbook_home"
CODES = CLAIMS + "::test_cited_coherence_exit_codes_match_result_constants"
INDEX = CLAIMS + "::test_readme_indexes_every_runbook_with_a_scenario"
MIGRATION = CLAIMS + "::test_migration_guide_anchors_exist_in_the_scripts"

DOC_OUTAGE = "docs/runbooks/hub-outage.md"
DOC_README = "docs/runbooks/README.md"
RES = "hub/coherence/result.py"
LIB = "scripts/lib/runner-units.sh"

MUTATIONS = [
    ("M1: outage behavior anchor edited out of its runbook",
     [(DOC_OUTAGE, "exits 1 with `HUB UNREACHABLE`", "exits 1 with `HUB OFFLINE`")],
     [BEHAVIOR], {}),
    ("M2: migration guide dropped from README's index table",
     [(DOC_README,
       "| [migration-fixed-name-to-per-runner-units.md](./migration-fixed-name-to-per-runner-units.md) | moving a host from fixed-name to per-runner units (`bfb7e99`) | `tests/mutation_battery_image_state.py`; `tests/test_runbook_claims.py` |\n",
       "")],
     [INDEX], {}),
    ("M3: EXIT_PROTOCOL renumbered — docs cite 40, code says 41 (and no other test notices)",
     [(RES, "EXIT_PROTOCOL = 40", "EXIT_PROTOCOL = 41")],
     [CODES], {}),
    ("M4: legacy unit renamed in the script the migration guide names",
     [(LIB, '"$STATE_DIR/devgate-heartbeat.service"',
       '"$STATE_DIR/devgate-heartbeat-X.service"')],
     [MIGRATION], {}),
]

NEGATIVE_CONTROLS = [
    ("N1: benign wording edit touching no anchor — must survive",
     [(DOC_OUTAGE,
       "covers the implemented detection and recovery path only.",
       "covers the implemented detection and recovery path, only.")],
     [CLAIMS], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it is a prose-only edit, no claim changes"))
