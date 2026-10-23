#!/usr/bin/env python3
"""toolchain_probe.py — observe the tools a lane's runner image actually has.

// spec: mon-tc-01 (spoke side), design.md "Detection"

Loaded by runner-heartbeat.sh under the same sibling rule registry-digest.sh
uses: installed FLAT beside the helper (by lib/runner-installs.sh, sourced by
runner-enroll.sh), and resolved next to itself at run time. Not `import`ed by
the body-builder — a library beside a script is not on sys.path, and editing
sys.path inside the snippet that builds the heartbeat's body is the wrong place
to make a filesystem decision. The tick resolves the path once, then loads it by
path with importlib in the probe step, so a host missing this file loses the
toolchain fields and keeps ticking, exactly like the digest advisory — a
heartbeat that dies blinds the fleet, which is worse than a toolchain field that
reads unknown.

Why Python and not shell. The old argument against `timeout(1)` — a bare host
with an empty PATH must still tick — does not apply here, because this file
only ever runs *after* the tick has already resolved `python3` to build the
body it posts. `subprocess.run(timeout=...)` is a wall-clock bound with no
external binary and no fd discipline, and unlike `read -t` it can actually be
unit-tested in milliseconds. Probing means executing the probes, which is what
the spoke's whole job has always been (curl, podman, python3); the
no-execution rule lives hub-side (mon-tc-05) and this file is not that rule.

The required set is never computed here and never named here. mon-tc-01 makes
the vocabulary and the profile tables spec-governed data owned by the hub, so
the hub echoes the lane's reviewed profile in its heartbeat response and the
helper caches it; this module probes exactly the list it is handed. That is why
the vocabulary appears below only in probe *definitions* — the fixed
`python`/`pip`/`java`/`maven`/`g++` rules the spec mandates — and why a name
added to the vocabulary with a plain-existence probe (a future `ripgrep`) needs
no change here at all.

Run-state honesty (mon-tc-01): every tool answers `present`, `absent`, or
`unknown`. `unknown` is what a probe that exceeded its bound returns, and the
missing list excludes unknowns — an unknown never becomes an absent (that would
report a gap the probe did not see) and never becomes a present (that would be
absence reported as health). When anything is unknown the run reports itself
incomplete (`probe_complete: false`), which is the ONLY way the hub can ever
learn `probe-failed` coverage; a hub cannot tell an incomplete run from a
complete one by counting a list.

The observation root is `RUNNER_PROBE_PATH` when set (the containerised-runner
knob and the test seam), else the process PATH. The default deserves the
honest word: today's units run on the host, so an unset knob observes the host
— that is the deployment's limitation, not the probe's, and the test suite
never runs with it unset, so "never host PATH" stays enforced for everything
the suite can see rather than asserted in prose.
"""

import os
import shutil
import subprocess
import sys

# // spec: mon-tc-01 — TOOL_PROBE_TIMEOUT_S is 10 seconds. Overridable for
# tests via TOOL_PROBE_TIMEOUT_S; an earlier draft invented RUNNER_PROBE_-
# TIMEOUT_S and then a reviewer grepped for a name that did not exist.
TOOL_PROBE_TIMEOUT_S = 10.0

PRESENT, ABSENT, UNKNOWN = "present", "absent", "unknown"


def _path_dirs():
    root = os.environ.get("RUNNER_PROBE_PATH")
    raw = root if root is not None else os.environ.get("PATH", "")
    return [d for d in raw.split(os.pathsep) if d]


def _find(program: str, dirs) -> str | None:
    for d in dirs:
        p = os.path.join(d, program)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _run_ok(argv, timeout) -> str:
    """present on exit 0, absent on any other answer, unknown on the bound."""
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return UNKNOWN
    except OSError:
        # The program vanished between resolve and exec, or is not executable
        # for a reason `access` could not see. Not-found is a fact, not a
        # timeout; only the bound is unknown.
        return ABSENT
    return PRESENT if proc.returncode == 0 else ABSENT


def probe_tool(name: str, dirs, timeout: float) -> str:
    """The fixed probes mon-tc-01 mandates; every other name is existence."""
    if name == "python":
        # `python` is `python3` present.
        return PRESENT if _find("python3", dirs) else ABSENT
    if name == "pip":
        # `pip` is `python3 -m pip` succeeding: a python3 without the module
        # is `absent`, never `present` because an interpreter exists. The
        # RESOLVED python3 runs it — a bare "python3" would fall through to
        # the process PATH and probe the wrong environment, which under the
        # RUNNER_PROBE_PATH knob is precisely the image-vs-host distinction
        # this whole module exists to keep.
        prog = _find("python3", dirs)
        return ABSENT if not prog else _run_ok([prog, "-m", "pip", "--version"],
                                               timeout)
    if name == "java":
        prog = _find("java", dirs)
        return ABSENT if not prog else _run_ok([prog, "-version"], timeout)
    if name == "maven":
        # maven requires a working JDK, which `mvn -version` proves by
        # failing without one; a maven binary alone is not present.
        prog = _find("mvn", dirs)
        return ABSENT if not prog else _run_ok([prog, "-version"], timeout)
    # g++ is its own probe and is never inferred from gcc; every future name
    # with a plain-existence rule takes this branch unchanged.
    return PRESENT if _find(name, dirs) else ABSENT


def probe_required(required, timeout: float | None = None):
    """(missing, complete) for the handed-over required list.

    Byte-exact names, no normalisation, and the result is sorted only to keep
    the wire shape stable — mon-tc-01 forbids a spoke-side vocabulary, so
    `required` arrives from the hub's own echo and a name outside it is probed
    like any other (the hub refuses a report containing it, all-or-nothing,
    which is the hub's call to make, not this module's to second-guess).
    """
    if timeout is None:
        timeout = float(os.environ.get("TOOL_PROBE_TIMEOUT_S")
                        or TOOL_PROBE_TIMEOUT_S)
    dirs = _path_dirs()
    missing = []
    complete = True
    for name in required:
        if not isinstance(name, str) or not name:
            continue  # defensive: a malformed cache is skipped, never executed
        state = probe_tool(name, dirs, timeout)
        if state == ABSENT:
            missing.append(name)
        elif state == UNKNOWN:
            complete = False
    return sorted(missing), complete


if __name__ == "__main__":
    # CLI form for ad-hoc runs and the shell-side smoke test:
    #   toolchain_probe.py <required-json-file> -> {"missing":[...],"complete":bool}
    import json
    with open(sys.argv[1], encoding="utf-8") as fh:
        required = json.load(fh).get("required_tools") or []
    missing, complete = probe_required(required)
    print(json.dumps({"missing": missing, "complete": complete}))
