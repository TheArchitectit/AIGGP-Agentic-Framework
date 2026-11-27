"""Replay the consumer-fixture sensitivity checks for DG-02 batch 012."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from extraction_rehearsal import DECLARED_BUILD_INPUTS, IGNORE


def run_suite(workspace, expected_exit, expected_diagnostic=None):
    suite = workspace / "fleet-manager/tests/test_contracts_v1.py"
    run = subprocess.run([sys.executable, "-I", str(suite)], cwd=workspace,
                         capture_output=True, text=True)
    count = re.search(r"^Ran (\d+) tests? in ", run.stderr, re.MULTILINE)
    if not count or int(count[1]) == 0 or run.returncode != expected_exit:
        raise RuntimeError(run.stderr)
    if expected_diagnostic and expected_diagnostic not in run.stderr:
        raise RuntimeError(run.stderr)
    return {"exit_code": run.returncode, "tests_run": int(count[1]),
            "diagnostic_checked": expected_diagnostic}


def main():
    package = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        copied = workspace / "fleet-manager"
        shutil.copytree(package, copied, ignore=IGNORE)
        for rel in DECLARED_BUILD_INPUTS:
            target = workspace / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(package.parent / rel, target)

        contracts = copied / "contracts/v1"
        fixture = contracts / "fixtures/core-consumer-expectations.json"
        baseline = fixture.read_text(encoding="utf-8")
        results = {"baseline": run_suite(workspace, 0)}
        changed = json.loads(baseline)
        changed["decision"]["required_paths"].append("batch_probe_field")
        fixture.write_text(json.dumps(changed), encoding="utf-8")
        results["extra_required_path"] = run_suite(workspace, 1, "batch_probe_field")

        changed = json.loads(baseline)
        reason = "batch_probe_reason"
        schema = json.loads((contracts / "capacity-decision.schema.json").read_bytes())
        allowed = schema["properties"]["reason"]["properties"]["code"]["enum"]
        if reason in allowed:
            raise ValueError("The control requires a reason outside the producer schema")
        changed["decision"]["required_reason_codes"].append(reason)
        fixture.write_text(json.dumps(changed), encoding="utf-8")
        results["extra_unsupported_reason"] = run_suite(workspace, 0)
        results["extra_unsupported_reason"]["code"] = reason
        results["extra_unsupported_reason"]["declared_in_producer_enum"] = False
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
