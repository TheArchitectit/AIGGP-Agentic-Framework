"""Read-only DG-02 batch 013 historical behavior controls.

Runs the real extraction rehearsal against a supplied checkout twice (normal
PATH and a disposable PATH containing git but no node), and probes whether the
plan value/document preserves its reported capacity summary. Temporary
workspaces are owned by extraction_rehearsal.py and removed by it.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[2]


def _load_fixture(source: Path) -> Any:
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    boundary = str(source / "fleet-manager")
    if boundary not in sys.path:
        sys.path.insert(0, boundary)
    test_fixture = source / "fleet-manager/tests/test_plan_apply_v1.py"
    spec = importlib.util.spec_from_file_location("dg02_plan_test_fixture", test_fixture)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load existing fixture helpers from supplied source checkout")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_status(output: str, rc: int) -> dict[str, Any]:
    phase_a = next((line.strip() for line in output.splitlines()
                    if "phase A:" in line), None)
    phase_b = next((line.strip() for line in output.splitlines()
                    if "phase B: core suite collection" in line), None)
    scan = next((line.strip() for line in output.splitlines()
                 if "phase B: guardrails scan" in line), None)
    skipped = next((line.strip() for line in output.splitlines()
                    if "guardrails half skipped" in line), None)
    count = None
    for line in output.splitlines():
        marker = "phase B: "
        suffix = " core tests collect"
        if marker in line and suffix in line:
            try:
                count = int(line.split(marker, 1)[1].split(suffix, 1)[0])
            except ValueError:
                pass
    return {
        "exit_code": rc,
        "phase_a": {"status": "ran" if phase_a else "not_reported", "line": phase_a},
        "collection": {
            "status": "ran" if phase_b else "not_reported",
            "line": phase_b,
            "collected_count": count,
        },
        "guardrails_scan": {
            "status": "ran" if scan else ("skipped" if skipped else "not_reported"),
            "line": scan or skipped,
        },
        "diagnostics": output,
    }


def _run_rehearsal(checkout: Path, rehearsal: Path, target: Path, *, path: str | None, python: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if path is not None:
        env["PATH"] = path
    try:
        proc = subprocess.run(
            [python, str(rehearsal), "--source", str(target)],
            cwd=str(checkout), env=env, capture_output=True, text=True, check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        output = output.replace(str(checkout), "<CHECKOUT>").replace(str(target), "<SOURCE>")
        return _extract_status(output, proc.returncode)
    except OSError as exc:
        return {
            "exit_code": None,
            "phase_a": {"status": "not_run", "line": None},
            "collection": {"status": "not_run", "line": None, "collected_count": None},
            "guardrails_scan": {"status": "not_run", "line": None},
            "diagnostics": f"could not launch rehearsal: {type(exc).__name__}: {exc}",
        }


def extraction_controls(source: Path, python: str) -> dict[str, Any]:
    rehearsal = source / "fleet-manager/scripts/extraction_rehearsal.py"
    with tempfile.TemporaryDirectory(prefix="dg02-batch-013-path-") as bin_dir:
        git = shutil.which("git")
        if git:
            os.symlink(git, Path(bin_dir) / "git")
        no_node_path = bin_dir
        return {
            "normal": _run_rehearsal(source, rehearsal, source, path=None, python=python),
            "no_node": _run_rehearsal(source, rehearsal, source, path=no_node_path, python=python),
            "absent_source": _run_rehearsal(
                source, rehearsal, source / "__dg02_batch_013_absent_source__",
                path=None, python=python,
            ),
            "no_node_path_contract": {
                "contains_git": bool(git),
                "git_available": bool(git),
                "contains_node": shutil.which("node", path=no_node_path) is not None,
            },
        }


def plan_control(source: Path) -> dict[str, Any]:
    try:
        fixture = _load_fixture(source)
        from fleet_manager.plan import CapacityImpact
    except (OSError, ImportError, RuntimeError) as exc:
        return {"status": "not_run", "diagnostic": f"fixture unavailable: {type(exc).__name__}: {exc}"}
    plan = fixture.build_plan(fixture._state(), [fixture._assign_change()])
    genuine = plan.document()
    impact_type = type(plan.impacts[0])
    forged_impact = CapacityImpact(
        host_id=plan.impacts[0].host_id, before_free=20, after_free=19,
    )
    forged_plan = dataclasses.replace(plan, impacts=(forged_impact,))
    forged = forged_plan.document()
    return {
        "identity_equal": plan.plan_id == forged_plan.plan_id,
        "changes_equal": [c.document() for c in plan.changes] == [c.document() for c in forged_plan.changes],
        "impact_type": impact_type.__name__,
        "genuine": {
            "acceptance": "accepted_by_build_plan",
            "plan_id": plan.plan_id,
            "summary": genuine["capacity_impact"],
        },
        "dataclasses_replace": {
            "acceptance": "accepted_by_Plan_and_document",
            "plan_id": forged_plan.plan_id,
            "summary": forged["capacity_impact"],
            "changed_from_genuine": forged["capacity_impact"] != genuine["capacity_impact"],
        },
        "interpretation": "observed pinned behavior only; does not prescribe permanent behavior",
    }


def _version(command: str) -> str:
    try:
        proc = subprocess.run([command, "--version"], capture_output=True, text=True, check=False)
    except OSError:
        return "unavailable"
    return (proc.stdout or proc.stderr).strip() or "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REPO,
                        help="checkout to pass to extraction_rehearsal.py (default: this repository)")
    parser.add_argument("--python", default=sys.executable,
                        help="absolute/interpreter command for subprocesses (defaults to this script's interpreter)")
    args = parser.parse_args()
    source = args.source.resolve()
    result = {
        "format": "dg02-batch-013-controls/v1",
        "python_version": _version(args.python),
        "normal_node_version": _version("node"),
        "source": "supplied-checkout",
        "extraction_rehearsal": extraction_controls(source, args.python),
        "fleet_002_01_capacity_document": plan_control(source),
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    rehearsal = result["extraction_rehearsal"]
    if not (source / "fleet-manager/scripts/extraction_rehearsal.py").is_file():
        return 1
    if rehearsal["normal"]["exit_code"] != 0:
        return 1
    if result["fleet_002_01_capacity_document"].get("status") == "not_run":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
