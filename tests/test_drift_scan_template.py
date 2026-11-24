#!/usr/bin/env python3
# // spec: ci-tpl-02
"""The drift-scan template must consume a host's runner declaration faithfully.

`detect-host-ci.py` reports `runs-on:` values verbatim. A host that writes a
YAML flow sequence — `runs-on: [self-hosted, devgate-rtp]` — therefore yields
the single string `"[self-hosted, devgate-rtp]"`, and the template that shipped
used `labels[0]` as the scan job's placement. No runner carries that label, so
the job did not fail: it queued forever, and a schedule that never runs reports
nothing, which reads exactly like a quiet repository.

These tests execute the resolution step against fixtures rather than reading it:
a text assertion cannot tell a corrected parse from a comment that describes
one, and the failure being prevented here is the absence of any output at all.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.platform_caps import require_bash

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "github-workflows" / "drift-scan.yml"
BASH = "/bin/bash"

STEP_NAME = "Detect host CI"


def _step_run(text: str, name_contains: str) -> str:
    """Return the `run:` body of the step whose name contains the needle.

    Read by indentation, the same narrow reader `detect-host-ci.py` and the
    secret-validation suite use — a YAML library would be a test-only
    dependency this lane does not install.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("- name:") and name_contains in line:
            for j in range(i, len(lines)):
                if lines[j].strip() == "run: |":
                    indent = len(lines[j]) - len(lines[j].lstrip()) + 2
                    body = []
                    for raw in lines[j + 1:]:
                        if raw.strip() and (len(raw) - len(raw.lstrip())) < indent:
                            break
                        body.append(raw[indent:] if raw.strip() else "")
                    return "\n".join(body)
            break
    raise AssertionError(f"no step named {name_contains!r} with a run block")


# detect-host-ci.py's own output shape, with only the fields this step reads.
STUB = """#!/usr/bin/env python3
import json, os
print(json.dumps({"runs_on_labels": json.loads(os.environ["FIXTURE_LABELS"]),
                  "scheduled_crons": ["23 4 * * *"]}))
"""


class TestDriftScanRunnerResolution(unittest.TestCase):
    def setUp(self):
        self.text = TEMPLATE.read_text(encoding="utf-8")
        self.run = _step_run(self.text, STEP_NAME)
        # Non-vacuity: an extractor that returned an empty body would make every
        # execution below pass by running nothing.
        self.assertIn("host-ci.json", self.run, "the resolution step was not read")

    # --- placement is an array, not a label string --------------------------

    def test_the_scan_job_consumes_the_array_with_fromJSON(self):
        self.assertIn(
            "runs-on: ${{ fromJSON(needs.resolve-target.outputs.runner_json) }}",
            self.text,
            "the scan job does not consume the resolved placement as an array")
        self.assertIn("runner_json: ${{ steps.host.outputs.runner_json }}",
                      self.text,
                      "the resolution job does not publish runner_json")

    def _resolve(self, labels_json: str) -> dict[str, str]:
        require_bash("the resolution step's body is bash")
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            stub = tmp / ".devgate" / "scripts" / "detect-host-ci.py"
            stub.parent.mkdir(parents=True)
            stub.write_text(STUB, encoding="utf-8")
            out = tmp / "github_output"
            out.write_text("", encoding="utf-8")
            env = {**os.environ,
                   "FIXTURE_LABELS": labels_json,
                   "GITHUB_OUTPUT": str(out)}
            proc = subprocess.run([BASH, "-c", "set -eu\n" + self.run],
                                  cwd=str(tmp), env=env, capture_output=True,
                                  text=True, timeout=60)
            self.assertEqual(proc.returncode, 0,
                             f"resolution failed: {proc.stdout}{proc.stderr}")
            pairs = (line.split("=", 1) for line in
                     out.read_text(encoding="utf-8").splitlines() if "=" in line)
            got = dict(pairs)
            self.assertIn("runner_json", got,
                          "the step published no runner_json")
            # It must be JSON the workflow expression language can parse.
            json.loads(got["runner_json"])
            return got

    def test_a_flow_sequence_is_split_into_its_labels(self):
        got = self._resolve('["[self-hosted, devgate-rtp]"]')
        self.assertEqual(json.loads(got["runner_json"]),
                         ["self-hosted", "devgate-rtp"])

    def test_an_expression_is_not_a_label(self):
        got = self._resolve('["${{ needs.other.outputs.runner }}"]')
        self.assertEqual(json.loads(got["runner_json"]), ["ubuntu-latest"],
                         "an expression was requested as a runner label")

    def test_no_declaration_falls_back_to_a_hosted_runner(self):
        got = self._resolve("[]")
        self.assertEqual(json.loads(got["runner_json"]), ["ubuntu-latest"])

    def test_alternatives_are_not_merged_into_one_placement(self):
        """Two `runs-on:` values are two alternative placements. Combining
        their labels would ask for a runner carrying labels from two different
        jobs at once — the same never-queues failure in another shape."""
        got = self._resolve('["${{ needs.other.outputs.runner }}", '
                            '"[self-hosted, devgate-rtp]", "devgate"]')
        self.assertEqual(json.loads(got["runner_json"]),
                         ["self-hosted", "devgate-rtp"])


if __name__ == "__main__":
    unittest.main()
