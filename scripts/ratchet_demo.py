#!/usr/bin/env python3
# // spec: coh-pol-04, coh-pol-05, coh-pol-06
"""ratchet_demo.py — the Stage-2 adoption-ladder demonstration (criterion 8).

Criterion 8 asks the adoption ladder to enforce two separate things, and this
drill runs both through the REAL service (`python3 -m hub.coherence`, the same
entry point the containerized gate invokes) against synthesized findings laid
out in the shape of the R9-captured LobsterWars baseline:

  * **no-regression** (coh-pol-04): a baseline fingerprinted from the captured
    debt shelters exactly those findings at stage 2, and a NEW violation of the
    same assertion on a NEW location is NOT sheltered — it blocks. This is the
    ratchet proper: adopted debt stays adopted, new debt does not.
  * **advisory-expiry** (coh-pol-05/06): the same baseline shelters nothing
    once the repository record's advisory has aged past
    `stages.max_advisory_age_days` with `on_expiry: block`. Expiry is read
    once, from the context's evaluation_time against the caller's record.

WHAT IS CAPTURED AND WHAT IS SYNTHETIC — read this before citing the output.

The *baseline shape* is the captured fact: 12 x PREVENT-011 + 1 x PREVENT-029
over 13 locations, taken from `r9-provenance-capture.md` (LobsterWars commit
f5b48a30a7113217742f0754ffe1cc6357ac9416, drift-scan run 36405534067, report
digest sha256:8c19f2f1a2482f6852c562939b00e1fb81e8aa25c886601a1e8a300c9dba558f).
The *run* is synthetic, and dispatching it does not make it otherwise: this
produces no coherence attestation over LobsterWars' bytes, evaluates no
LobsterWars file, and the signer here is a throwaway fixture key. Per R9 and
ADR-019 this demonstrates the LADDER against a captured SHAPE; relabeling any
fixture to non-synthetic still requires a real run against the pinned subject,
which needs the enrolled spoke and runner time this host does not provide.

Exit codes: 0 both obligations held; 1 an obligation failed; 30 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVGATE_ROOT))

from tests.fixtures.coherence import fixtures as fx  # noqa: E402

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 30
_results: list[tuple[str, bool]] = []

# The captured LobsterWars baseline, in the order r9-provenance-capture.md
# lists it (emitted order — the digest above is order-dependent). 12 findings
# of one class plus a single distinct-class finding.
LOBSTERWARS_BASE = [
    ("server/GameRoom.ts", 93), ("server/GameRoom.ts", 108),
    ("server/index.ts", 75), ("src/audio/AudioManager.ts", 64),
    ("src/game/scenes/BootScene.ts", 914), ("src/game/scenes/BootScene.ts", 915),
    ("src/game/systems/ProjectileSystem.ts", 283),
    ("src/game/systems/UISystem.ts", 65), ("src/game/systems/UISystem.ts", 66),
    ("src/network/NetworkManager.ts", 40), ("src/systems/ReplayRecorder.ts", 24),
    ("src/systems/ReplayTypes.ts", 17), ("src/systems/TheaterSystem.ts", 27),
]
# The captured classes (12 x PREVENT-011 plus one PREVENT-029) are what the
# drift-scan gate reported, and they are the reason the shape is real debt.
# They are NOT what this drill can fingerprint a baseline with: the ladder
# keys a finding by its `violation_class` (adoption._vclass reads that field
# directly), and the identity evaluator emits `identity-mismatch`. Binding a
# baseline entry to `pattern-violation:prevent-011` while the run produces
# `identity-mismatch` yields a fingerprint that matches NOTHING — every
# location blocks and the ratchet looks broken when it is the fixture that is
# wrong. (I made exactly that error: 13/13 BLOCK, decision FAIL, no reason on
# the row, and the first drill passed only because a non-sheltering baseline
# also blocks.) So the baseline is keyed to the class the evaluator actually
# emits; the captured provenance lives in the ledger and in the record.
CLASS_EMITTED = "identity-mismatch"


def step(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name:44s} {detail}")
    return ok


def _run(rep_repo: Path, request: Path, out: Path) -> tuple[int, dict, list]:
    """Invoke the REAL service entry point on a built request.

    Returns (exit code, result, findings). `findings` comes from the SEALED
    evidence bundle, not from `result["assertion_results"]` — and that
    distinction cost me a wrong expectation worth recording. The ledger
    carries ONE ROW PER ASSERTION (`evaluate.run`: each row is appended once
    per planned assertion, right after the subject-mutation re-check), while
    the *findings* the evaluator produced — one per violating subject — are
    extended into a separate list and sealed. So a single assertion over 14
    files yields 1 ledger row carrying 14 evidence findings. Reading the
    ledger for per-location cardinality reports "1 of 13" forever and looks
    like a broken ratchet; it is a broken reading. (Whether the ledger SHOULD
    also expose the locations is a real question — it carries no
    `subject_locations` — but it is a schema decision, not this drill's.)
    """
    p = subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(request)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(rep_repo), env={**os.environ, **fx.cli_env()})
    res = json.loads((out / "result.json").read_text(encoding="utf-8"))
    sealed = out / "evidence" / "findings"
    findings = [json.loads(f.read_text(encoding="utf-8"))
                for f in sorted(sealed.glob("*.json"))] if sealed.is_dir() else []
    return p.returncode, res, findings


def _location_of(finding: dict) -> str:
    locs = finding.get("subject_locations") or []
    return locs[0] if locs else ""


def _captured_baseline(assertion_id: str) -> list:
    """One adopted-debt entry per captured location, keyed to the class this
    run's evaluator emits (see CLASS_EMITTED)."""
    return [fx.baseline_entry(assertion_id, 1, _loc(location, line), CLASS_EMITTED)
            for location, line in LOBSTERWARS_BASE]


def _loc(location: str, line: int) -> str:
    """The finding's subject_location, flattened for the fixture subject root.

    The captured location is a real repo path (`server/GameRoom.ts:93`), but a
    fixture subject is a directory of files, not a checkout. The location
    string is what the fingerprint is taken over, so flattening the separator
    keeps every entry distinct and keeps the captured path readable in the
    ledger — without materializing 13 nested directories to hold one line."""
    return f"{location.replace('/', '__')}:{line}"


def _subject_files() -> dict:
    """One file per captured location, each carrying the declared product name
    so the identity evaluator has something real to disagree with."""
    return {_loc(loc, line): "# product: widget\n"
            for loc, line in LOBSTERWARS_BASE}


def _drive(td: Path, repo: Path, *, extra_subjects=(), repository=None):
    """Build one stage-2 run over the captured shape and execute it.

    `extra_subjects` adds locations beyond the captured 13 (the regression
    probe); `repository` is the caller-supplied repo record the advisory clock
    is read from. Returns (exit code, result, findings).
    """
    a = fx.assertion(subjects=[{"kind": "file", "path": _loc(loc, line)}
                               for loc, line in LOBSTERWARS_BASE]
                     + list(extra_subjects))
    files = {**_subject_files(),
             **{s["path"]: "# product: widget\n" for s in extra_subjects}}
    req, out = fx.build_root(
        td, declared_name="widget", approved_name="gadget", assertions=[a],
        baseline=_captured_baseline(a["id"]), stage=2, subject_files=files,
        repository=repository)
    return _run(repo, req, out)


def _row(res: dict) -> dict:
    """The single ledger row this one-assertion run produces."""
    rows = res["assertion_results"]
    assert len(rows) == 1, f"expected one assertion row, got {len(rows)}"
    return rows[0]


def drill_no_regression(td: Path, repo: Path) -> bool:
    """Adopted debt stays adopted; a NEW location is not sheltered."""
    print("\n[1] no-regression — the ratchet shelters adopted debt, not new debt")
    probe = {"kind": "file", "path": "src__new__Regression.ts:12"}
    code, res, findings = _drive(td, repo, extra_subjects=[probe])
    locs = [_location_of(f) for f in findings]
    adopted = [l for l in locs if "src__new__" not in l]
    fresh = [l for l in locs if "src__new__" in l]
    row = _row(res)
    ok = (len(locs) == 14 and len(adopted) == 13 and len(fresh) == 1
          and row["enforcement"] == "BLOCK" and res["decision"] == "FAIL")
    step("14 locations produce 14 findings", len(locs) == 14, f"{len(locs)}/14")
    step("13 adopted locations carry findings", len(adopted) == 13, f"{len(adopted)}/13")
    step("the new location is NOT sheltered (BLOCK)", row["enforcement"] == "BLOCK",
         f"enforcement={row['enforcement']}")
    step("run decision is FAIL", res["decision"] == "FAIL", f"exit={code}")
    return ok


def drill_advisory_expiry(td: Path, repo: Path) -> bool:
    """Past the window, the same baseline shelters nothing."""
    print("\n[2] advisory-expiry — the same baseline stops sheltering once aged out")
    # The repository record dates the advisory 90 days before the run's
    # evaluation_time; the bundle's window is 30. Read from the record, not
    # from the host clock — the service is deterministic.
    code, res, findings = _drive(td, repo,
                                 repository={"advisory_started": "2026-06-19T00:00:00Z"})
    row = _row(res)
    ok = len(findings) == 13 and row["enforcement"] == "BLOCK" and res["decision"] == "FAIL"
    step("13 findings still evaluated", len(findings) == 13, f"{len(findings)}/13")
    step("expired baseline shelters nothing (BLOCK)", row["enforcement"] == "BLOCK",
         f"enforcement={row['enforcement']}")
    step("run decision is FAIL", res["decision"] == "FAIL", f"exit={code}")
    return ok


def drill_direction_control(td: Path, repo: Path) -> bool:
    """Control: inside the window the SAME baseline still shelters.

    Without this the expiry drill proves nothing — a ladder that blocked
    everything would pass it. Both directions, one baseline.
    """
    print("\n[3] direction control — inside the window the same baseline shelters")
    code, res, findings = _drive(td, repo,
                                 repository={"advisory_started": "2026-09-16T00:00:00Z"})
    row = _row(res)
    ok = len(findings) == 13 and row["enforcement"] == "ADVISORY" and res["decision"] == "ADVISORY"
    step("13 findings still evaluated", len(findings) == 13, f"{len(findings)}/13")
    step("in-window baseline shelters (ADVISORY)", row["enforcement"] == "ADVISORY",
         f"enforcement={row['enforcement']}")
    step("run decision is ADVISORY", res["decision"] == "ADVISORY", f"exit={code}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    print("ratchet_demo — Stage-2 adoption ladder (criterion 8)")
    print("baseline shape: captured (R9); this run: synthetic (see module docstring)")
    results = []
    with tempfile.TemporaryDirectory(prefix="dg-ratchet-") as td:
        root = Path(td)
        for i, fn in enumerate((drill_no_regression, drill_advisory_expiry,
                                drill_direction_control)):
            sub = root / f"case{i}"
            sub.mkdir()
            results.append(fn(sub, DEVGATE_ROOT))
    held = all(results)
    print(f"\n{'=' * 66}\n  {'ALL OBLIGATIONS HELD' if held else 'OBLIGATION FAILED'}"
          f" — {sum(1 for _, ok in _results if ok)}/{len(_results)} steps\n{'=' * 66}")
    return EXIT_OK if held else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
