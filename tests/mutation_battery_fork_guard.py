#!/usr/bin/env python3
"""Mutation battery for the fork guard on ci.yml (R19-13 routing).

The guard is only worth having if removing it fails the suite — and only if the
suite fails for the RIGHT reason. Three shapes are mutated:

  * the guard deleted from a job (a fork PR's jobs would be dispatched),
  * the guard's `||` inverted to `&&` (every push run would be skipped —
    the exact defect a prose comparison on the `if:` cannot see),
  * the guard moved behind the job's own condition, so the leading-clause
    property that a later edit is most likely to break is pinned,
  * `pull_request_target` substituted for `pull_request` (base-repo workflow
    against PR-controlled code).

Each mutation is measured against `tests/test_fork_guard.py` alone, so a kill
names the guard that caught it. The negative control reworded the header comment
without changing a condition: the guards read conditions, not prose, so it must
survive — and a battery that killed it would be pinning wording again.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

CI = ".github/workflows/ci.yml"
T_GUARD = "tests/test_fork_guard.py"

GUARD = ("github.event_name != 'pull_request' || "
         "github.event.pull_request.head.repo.full_name == github.repository")

# A job-specific anchor: the publish condition is unique in the file, so
# mutating it cannot be confused with the plain guard lines the other jobs use.
PUBLISH_IF = ("    if: (" + GUARD + ") && ((github.event_name == 'push' && "
              "github.ref == 'refs/heads/main') || (github.event_name == "
              "'workflow_dispatch' && inputs.publish))")
PUBLISH_IF_REORDERED = ("    if: ((github.event_name == 'push' && github.ref == "
                        "'refs/heads/main') || (github.event_name == "
                        "'workflow_dispatch' && inputs.publish)) && (" + GUARD + ")")

HEADER = "# Runner targeting: the UCS03 fleet lane (`devgate`, runner ucs03-devgate)."
HEADER_REWORDED = ("# Fleet routing: this repository's CI runs on the UCS03 "
                   "`devgate` lane (runner ucs03-devgate).")

MUTATIONS = [
    # F1 — the guard deleted from one job. The job still runs on the fleet, so
    # only the guard rule can see it.
    ("F1: the fork guard is deleted from one job",
     [(CI,
       "  tests:\n    if: " + GUARD + "\n",
       "  tests:\n")],
     [T_GUARD], {}),

    # F2 — the guard inverted. Every push run would be skipped, so CI would go
    # green-by-silence on main.
    ("F2: the fork guard's `||` is inverted to `&&`",
     [(CI,
       "  self-gates:\n    if: " + GUARD + "\n",
       "  self-gates:\n    if: "
       + GUARD.replace("||", "&&") + "\n")],
     [T_GUARD], {}),

    # F3 — the guard demoted behind the job's own condition. Semantically the
    # same expression today; the leading-clause property is what stops the next
    # edit from dropping it while appending a condition.
    ("F3: the guard is moved behind the job's own condition",
     [(CI, PUBLISH_IF, PUBLISH_IF_REORDERED)],
     [T_GUARD], {}),

    # F4 — the unsafe trigger. `pull_request_target` runs the base repository's
    # workflow against a PR-controlled checkout with a writable token.
    ("F4: `pull_request_target` is substituted for `pull_request`",
     [(CI, "on:\n  pull_request:\n", "on:\n  pull_request_target:\n")],
     [T_GUARD], {}),
]

# Must SURVIVE: the header comment reworded, asserting nothing about the
# conditions. The guards evaluate payloads, so prose changes cannot fail them.
NEGATIVE_CONTROLS = [
    ("N1: the runner-routing comment reworded, same meaning",
     [(CI, HEADER, HEADER_REWORDED)],
     [T_GUARD], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it proves the guards read conditions, not comments"))
