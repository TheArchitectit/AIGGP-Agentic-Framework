#!/usr/bin/env python3
"""Mutation battery for the fleet sweep's report reaching the hub (5.3).

The subject is a file on the runner and the state that leaves it, so what is
mutated here is every step between the two — and every step is a place a fleet
view can come out reading CLEAN on the strength of a report nobody could read:

  * the report path, which TWO carriers hold (the sweep unit's `--report` and
    the env file the heartbeat reads) and which nothing but a test keeps
    together (S1, S2),
  * the name the path is built from, where `$SLUG` and `$RUNNER_NAME` are two
    different spellings of one host for any name needing sanitizing (S13),
  * the owned-key rewrite that stops a re-enroll accumulating a second copy of
    the path (S12),
  * the reader's three cases, each of which collapses into a wrong answer if
    its branch is weakened: a missing report becoming an unreadable one, a
    corrupt report becoming an EMPTY FLEET, and an unscannable repository
    losing the reason it could not be scanned (S4, S5, S6),
  * what the heartbeat ships: locations stay on the host (S3),
  * the write, which has to be a replace rather than a truncation now that a
    second process reads the file on its own timer (S7),
  * the presence-aware read at the registry and at the JSON boundary, where
    conflating "says null" with "says nothing" either keeps a superseded sweep
    or wipes a real one (S8, S9),
  * the predicate the renderer will key on, whose whole job is that an
    unreadable report is not a usable verdict (S10).

Every mutation leaves its file well formed — `bash -n` for the shell, the
compiler for the Python — so no verdict here comes from a syntax error. The
verdicts are read from the env file, the generated unit, the POST body the
heartbeat actually sent, and the registry.

The mutations span four suites rather than one, which is the honest shape of the
change: it crosses the runner and the hub, and each end's guards are tested
where they live.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

ENROLL = "scripts/runner-enroll.sh"
LIB = "scripts/lib/runner-units.sh"
HB = "scripts/runner-heartbeat.sh"
FLEET = "scripts/secret-scan-fleet.sh"
REG = "hub/registry.py"
SERVER = "hub/server.py"

T_SPOKE = "tests/test_runner_scan_report.py"
T_FLEET = "tests/test_secret_scan_fleet.py"
T_REG = "tests/test_hub_registry.py"
T_HTTP = "tests/test_hub_enroll_heartbeat.py"

MUTATIONS = [
    # S1 — enrollment writes a DIFFERENT path to the env file than the unit
    # names. This is the two-carriers-one-fact failure in its plainest form:
    # the sweep reports faithfully to a file the heartbeat never opens, and the
    # host reads unknown forever while scanning perfectly. Loud in the report,
    # silent on the fleet view.
    ("S1: the env file names a report path the sweep unit does not write to",
     [(LIB, '    SCAN_REPORT="$(runtime_dir)/devgate-secretscan-$SLUG.json"',
            '    SCAN_REPORT="$HOME/.cache/devgate-secretscan-$SLUG.json"')],
     [T_SPOKE], {}),

    # S2 — the unit goes back to systemd's `%t`. It looks equivalent and is not:
    # `%t` is resolved by the MANAGER, at unit start, from a variable the
    # heartbeat script cannot see, so the path would exist in one carrier only.
    ("S2: the sweep unit names its report with systemd's %t, which no other reader can resolve",
     [(LIB, 'ExecStart=$FLEET_HELPER --declared "\\$SECRET_SCAN_DECLARED" --report "$SCAN_REPORT"',
            'ExecStart=$FLEET_HELPER --declared "\\$SECRET_SCAN_DECLARED" --report %t/devgate-secretscan-$SLUG.json')],
     [T_SPOKE], {}),

    # S13 — the path is built from the UNSANITIZED name. For `alpha` the two
    # spellings agree and every other test in the file passes; only the runner
    # whose name needs a slug can see it, which is why that test exists.
    ("S13: the report path is built from RUNNER_NAME, which is not the name the unit writes",
     [(LIB, '    SCAN_REPORT="$(runtime_dir)/devgate-secretscan-$SLUG.json"',
            '    SCAN_REPORT="$(runtime_dir)/devgate-secretscan-$RUNNER_NAME.json"')],
     [T_SPOKE], {}),

    # S12 — the report key stops being one enrollment owns, so a re-enroll
    # carries the old line over AND writes a new one. Two lines, and which one
    # a reader picks is an accident of the reader.
    ("S12: a re-enrollment accumulates a second report path in the env file",
     [(ENROLL, "grep -vE '^(HUB_URL|RUNNER_NAME|HEARTBEAT_TOKEN|LAST_JOB_SEEN|SECRET_SCAN_REPORT)='",
               "grep -vE '^(HUB_URL|RUNNER_NAME|HEARTBEAT_TOKEN|LAST_JOB_SEEN)='")],
     [T_SPOKE], {}),

    # S3 — the finding locations ride along. A decision, not an accident: the
    # report file keeps rule/path/line/commit so an operator on the host can
    # act, and the heartbeat ships the per-repo STATE. Shipping them makes the
    # heartbeat grow with every finding in the fleet and puts file paths of
    # unremediated findings on the wire on every tick.
    ("S3: the heartbeat ships every finding's file path and commit",
     [(HB, '        } for r in repos], "unreadable": None}',
           '            "locations": r.get("locations", []),\n'
           '        } for r in repos], "unreadable": None}')],
     [T_SPOKE], {}),

    # S4 — a report that will not parse becomes an EMPTY FLEET. This is the
    # mutation that matters most in this battery: the return value reads as
    # "no repositories, nothing found", which is the exact sentence a dashboard
    # renders as clean, produced from a file nobody could read. The sweep
    # rewrites this file on its own timer while the heartbeat reads it, so the
    # window is live, not theoretical.
    ("S4: a report that will not parse is read as an empty, clean fleet",
     [(HB, '    except Exception as exc:\n'
           '        return {"repos": [], "unreadable": f"{type(exc).__name__}: {exc}"}',
           '    except Exception:\n'
           '        return {"repos": [], "unreadable": None}')],
     [T_SPOKE], {}),

    # S5 — a MISSING report is reported as an unreadable one. The state is no
    # longer null, so a host that has never been swept stops being
    # indistinguishable from a faulted one, and `scan_state_unknown` keeps
    # saying unknown for a reason that is not true.
    ("S5: a missing report is reported as an unreadable one, not as absent",
     [(HB, '    except FileNotFoundError:\n        return None',
           '    except FileNotFoundError:\n'
           '        return {"repos": [], "unreadable": "no report file"}')],
     [T_SPOKE], {}),

    # S6 — the reason is dropped, keeping the state. The requirement's first
    # scenario is about the reason: a repository the sweep could not fetch has
    # to arrive saying why, or the operator is sent to look at a repository
    # that is simply gone.
    ("S6: a repository that could not be scanned loses the reason it could not",
     [(HB, '            "reason": r.get("reason"), "scope": r.get("scope"),',
           '            "reason": None, "scope": r.get("scope"),')],
     [T_SPOKE], {}),

    # S7 — the report is written IN PLACE again. Correct as long as nothing else
    # reads it, which stopped being true when the heartbeat did: a reader
    # arriving mid-write sees a zero-length or half-finished file.
    ("S7: the report is truncated in place rather than replaced atomically",
     [(FLEET, '    os.replace(tmp, report_path)',
              '    with open(report_path, "w") as dst, open(tmp) as src:\n'
              '        dst.write(src.read())\n'
              '    os.unlink(tmp)')],
     [T_FLEET], {}),

    # S8 — the registry treats an explicit null as no-news. A host whose report
    # is gone keeps the superseded verdict, and the fleet view shows a clean
    # sweep for a host that has nothing on disk.
    ("S8: an explicit null scan_state is treated as no news",
     [(REG, '        if scan_state is not UNREPORTED:\n'
            '            runner["scan_state"] = scan_state',
            '        if scan_state is not None:\n'
            '            runner["scan_state"] = scan_state')],
     [T_REG], {}),

    # S9 — the same conflation one layer out, at the JSON boundary, where it is
    # invisible: `data.get` returns None for a key that is absent and for a key
    # that is null, so every poster that never mentions scanning clears the
    # host's real report.
    ("S9: the server cannot tell a body that omits scan_state from one that sends null",
     [(SERVER, '                          data.get("scan_state", UNREPORTED))',
                '                          data.get("scan_state"))')],
     [T_HTTP], {}),

    # S10 — an unreadable report counts as a usable verdict. The predicate is
    # the one thing the renderer will key on, and its whole job is this case.
    ("S10: an unreadable report counts as a usable scan verdict",
     [(REG, '    if state.get("unreadable"):\n'
            '        return True\n'
            '    return not isinstance(state.get("repos"), list)',
            '    return not isinstance(state.get("repos"), list)')],
     [T_REG], {}),

    # S14 — the predicate goes back to attribute access on whatever the spoke
    # posted. Nothing validates this field on the way in (the drift test says
    # so), so `"clean"` and `[1, 2]` are values a buggy or hostile spoke can put
    # there — and `.get` on those raises, in the function a fleet view renders
    # through. The unmutated code asks `isinstance` first, so the worst a bad
    # value does is read as unknown.
    ("S14: the predicate assumes scan_state is an object and raises on a posted string",
     [(REG, '    if not isinstance(state, dict):\n        return True',
            '    if not state:\n        return True')],
     [T_REG], {}),

    # S15 — a state with no repositories becomes a usable verdict: "nothing to
    # report, therefore nothing wrong", which is the sentence a dashboard shows
    # for a clean fleet. Reached by `{}` and by `{"repos": {}}` alike.
    ("S15: a scan state with no repositories in it counts as a usable verdict",
     [(REG, '    return not isinstance(state.get("repos"), list)',
            '    return False')],
     [T_REG], {}),

    # S16 — the reader's own half of S15, one process earlier: a report that
    # parses with a non-list `repos` flows through as an empty fleet instead of
    # being routed to `unreadable`.
    ("S16: the reader accepts a report whose repos is not a list",
     [(HB, '        if not isinstance(repos, list):\n'
            '            # The hub predicate requires the same thing for the same reason\n'
            '            # (scan_state_unknown in hub/registry.py): a report whose repos is\n'
            '            # not a list has no repositories to render, and "no repositories"\n'
            '            # is what a dashboard shows as clean. Raising routes it to the\n'
            '            # `unreadable` branch below rather than returning an empty fleet.\n'
            '            # No apostrophes in here: this whole snippet lives in a\n'
            '            # single-quoted python3 -c, and one would end it mid-function.\n'
            '            raise ValueError("repos is not a list")\n',
            '')],
     [T_SPOKE], {}),

    # S17 — the runtime directory falls back to nothing when XDG_RUNTIME_DIR is
    # unset. That variable is absent over a non-login ssh session, and the user
    # manager still sets it for the units — so the sweep and the heartbeat would
    # name different directories on the host where provisioning happens.
    ("S17: the runtime directory has no fallback when XDG_RUNTIME_DIR is unset",
     [(LIB, '    printf \'%s\' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"',
            '    printf \'%s\' "${XDG_RUNTIME_DIR}"')],
     [T_SPOKE], {}),

    # S18 was here, and there is no S18. It mutated `os.path.abspath(report_path)`
    # in the temp-directory line, on the reasoning that an unresolved relative
    # `--report` would leave `dirname` empty and mkstemp would fail — the audit
    # that proposed it said so. It SURVIVED, and the reason is worth keeping:
    # measured, `mkstemp(dir="")` resolves against the process directory and
    # succeeds, so the line changed no behaviour on any input, and the guard the
    # mutation claimed to remove did not exist. The line is gone from
    # secret-scan-fleet.sh rather than left in with a comment praising it, and
    # `test_a_relative_report_path_is_written_where_the_caller_meant` stays to
    # pin the BEHAVIOUR for both spellings.
    #
    # There is deliberately no replacement mutation for "the temp must be a
    # sibling of the report" — the property the atomicity comment rests on. It
    # cannot be killed by a test on one machine with one filesystem, because the
    # observable outcomes are identical (`os.replace` succeeds either way), and
    # a mutation that survives only because the suite runs on a single box is
    # noise, not a finding. Recorded here so the next reader does not re-add it.

    # S20 — the seam between the two halves, and the one mutation here that no
    # single suite could see before this slice: the sweep writes the repository
    # under a key the heartbeat does not read. Both halves stay green on their
    # own — the sweep's tests check the report it wrote, this file's check a
    # report it wrote itself — and every host in the fleet reads `unreadable`
    # for a field that is present under a different name. Killed by
    # test_the_report_the_heartbeat_reads_is_the_one_the_sweep_actually_wrote,
    # which is the only test that runs a real sweep into a real heartbeat.
    ("S20: the sweep names a repository under a key the heartbeat never reads",
     [(FLEET, '        "name": name,\n        "url": url,',
              '        "repo_name": name,\n        "url": url,')],
     [T_SPOKE, T_FLEET], {}),

    # S19 — the failure path stops cleaning up. The temporary is left beside the
    # report for anything globbing the directory to pick up, and it is left
    # holding a half-written report — the state the sibling-and-rename write
    # exists to make impossible.
    ("S19: a failed report write leaves its temporary behind",
     [(FLEET, 'except BaseException:\n    os.unlink(tmp)\n    raise',
              'except BaseException:\n    raise')],
     [T_FLEET], {}),
]

# Must SURVIVE. Reworded comments, one per suite the mutations draw their kills
# from, saying exactly the same thing and read by nothing.
#
# One per suite on purpose. A kill is "the named test exited non-zero" and the
# harness (tests/mutation_harness.py) does not first check that the test passes
# UNMUTATED, so a test that later starts failing for a reason of its own would
# be credited as the killer of whatever mutation names it. A control under each
# suite is what keeps that from being invisible per suite: if the guards were
# reading prose, or the named tests were failing for the wrong reason, the
# control stops surviving and says so.
NEGATIVE_CONTROLS = [
    ("N1: a heartbeat comment reworded, saying exactly the same thing",
     [(HB, "# None of it can fail the tick. As with the image probe, a heartbeat that dies",
           "# Nothing here can fail the tick: as with the image probe, a heartbeat that dies")],
     [T_SPOKE], {}),
    ("N2: a sweep comment reworded, saying exactly the same thing",
     [(FLEET, "# Written to a sibling and RENAMED into place, never opened for writing at",
              "# Written beside the target and renamed into place, never opened for writing at")],
     [T_FLEET], {}),
    ("N3: a registry comment reworded, saying exactly the same thing",
     [(REG, "# Null until a sweep reports one, and null is UNKNOWN: a freshly",
            "# Null until a sweep reports one, and null means UNKNOWN: a freshly")],
     [T_REG], {}),
    ("N4: a server comment reworded, saying exactly the same thing",
     [(SERVER, "# presence-aware: a body that omits them must not clear a host's",
                "# presence-aware: a body that leaves them out must not clear a host's")],
     [T_HTTP], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "these four MUST survive — one per suite the kills come from, proving the "
        "guards read the env file, the unit, the report, the POST body and the "
        "registry rather than the messages around them"))
