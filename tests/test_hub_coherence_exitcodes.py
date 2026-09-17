# // spec: coh-pol-04, coh-pol-05, coh-pol-06, coh-dec-04, coh-eval-02, coh-ctx-03
"""Frozen S2 conformance suite: Fixtures A-F, full exit-code sweep, error
envelopes. Dual-runnable. All fixtures synthetic (R9).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
ZERO_DIGEST = "sha256:" + "0" * 64


def _run(req_path: Path, out_dir: Path):
    """Invoke the real CLI; return (exit_code, parsed result or None)."""
    r = subprocess.run([sys.executable, "-m", "hub.coherence", "--request", str(req_path)],
                       capture_output=True, text=True, cwd=str(REPO))
    rp = out_dir / "result.json"
    parsed = json.loads(rp.read_text()) if rp.exists() else None
    return r.returncode, parsed


class TestExitCodeSweep(unittest.TestCase):
    """Every documented exit code is reachable and carries a parseable payload."""

    def test_0_pass(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            code, res = _run(req, out)
            self.assertEqual(code, 0)
            self.assertEqual(res["decision"], "PASS")

    def test_10_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="x", approved_name="widget", stage=1)
            code, _ = _run(req, out)
            self.assertEqual(code, result.EXIT_ADVISORY)

    def test_20_fail(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="x", approved_name="widget", stage=3)
            code, _ = _run(req, out)
            self.assertEqual(code, result.EXIT_FAIL)

    def test_30_invalid_input(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td))
            r = json.loads(req.read_text())
            r["openspec"]["root"] = str(Path(td) / "missing")
            req.write_text(json.dumps(r))
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_INVALID_INPUT)
            self.assertEqual(res["decision"], "ERROR")

    def test_31_policy_error(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), policy_digest_ok=False)
            code, _ = _run(req, out)
            self.assertEqual(code, result.EXIT_POLICY)

    def test_32_execution_error(self):
        """Evaluator limit exhaustion -> exit 32."""
        from hub.coherence import evaluate
        with self.assertRaises(evaluate.EvaluatorError):
            evaluate.run([fx.assertion(aid=f"a{i}") for i in range(5)], {}, ".",
                         limits={"max_evaluators": 2})

    def test_33_evidence_error(self):
        """Sealing to an unwritable location raises EvidenceError (unit level)."""
        from hub.coherence import evidence
        findings = [{
            "assertion_id": "a1", "finding_key": "k", "outcome": "VIOLATED",
            "enforcement": "BLOCK", "severity": "high", "subject_locations": ["x"],
            "expected": "e", "observed": "o", "evidence_refs": [],
        }]
        with self.assertRaises(evidence.EvidenceError):
            evidence.seal(findings, "/proc/definitely/not/writable")

    def test_33_reachable_through_the_real_cli(self):
        """B1 (audit round 2): exit 33 was UNREACHABLE via the CLI — the error
        path wrote its envelope into the same unwritable directory that had
        just failed, dying with exit 1 and a traceback. The frozen sweep
        requires 33 to reach a caller. Three distinct unwritable shapes."""
        import os
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # (a) outputs is a regular file — cannot be a directory
            f = base / "afile"; f.write_text("x")
            # (b) outputs is read-only — cannot be written into
            ro = base / "ro"; ro.mkdir(); os.chmod(ro, 0o555)
            # (c) outputs nested under a regular file — no such directory
            nested = base / "afile" / "sub"
            cases = {"file": str(f), "readonly": str(ro), "nested": str(nested)}
            try:
                for label, bad in cases.items():
                    req, _ = fx.build_root(base / label, stage=3,
                                           declared_name="other", approved_name="widget")
                    r = json.loads(req.read_text())
                    r["outputs"] = bad
                    req.write_text(json.dumps(r))
                    p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                        "--request", str(req)],
                                       capture_output=True, text=True, cwd=str(REPO))
                    self.assertEqual(p.returncode, result.EXIT_EVIDENCE,
                                     f"{label}: expected exit 33, got {p.returncode}")
                    self.assertNotIn("Traceback", p.stderr,
                                     f"{label}: must not emit a raw traceback")
                    # The envelope must be findable: exit 33 via the temp
                    # fallback must announce the path on stderr. A non-writable
                    # out_dir always takes the fallback branch.
                    self.assertIn("devgate-coherence-", p.stderr,
                                  f"{label}: fallback path not announced on stderr")
            finally:
                os.chmod(ro, 0o755)

    def test_40_protocol(self):
        """Unsupported api_version -> exit 40, before any resolver runs."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td))
            r = json.loads(req.read_text())
            r["api_version"] = "devgate.spec-coherence/v99"
            req.write_text(json.dumps(r))
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_PROTOCOL)
            self.assertEqual(res["decision"], "ERROR")
            self.assertEqual(res["error"]["class"], "protocol")


class TestEnvelopeHonestyIndep(unittest.TestCase):
    """Round-3-independent items 1-5: caller-reachable inputs that killed the
    process with exit 1 + traceback instead of a documented envelope."""

    def test_zero_findings_unwritable_out_is_exit33(self):
        """Item 1: the fully-PASS shape has no findings, so the manifest write
        was the only seal write — and it was outside the try/except. The
        exit-33 battery only forced findings, which is why it stayed green."""
        with tempfile.TemporaryDirectory() as td:
            ro = Path(td) / "ro"; ro.mkdir(); os.chmod(ro, 0o555)
            try:
                # declared == approved -> zero findings (PASS shape)
                req, out = fx.build_root(Path(td) / "f", stage=1)
                r = json.loads(req.read_text())
                r["outputs"] = str(ro)
                req.write_text(json.dumps(r))
                p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                    "--request", str(req)],
                                   capture_output=True, text=True, cwd=str(REPO))
                self.assertNotIn("Traceback", p.stderr, "raw traceback")
                self.assertEqual(p.returncode, result.EXIT_EVIDENCE,
                                 f"expected exit 33, got {p.returncode}")
            finally:
                os.chmod(ro, 0o755)

    def test_success_emit_blocked_is_announced_not_traceback(self):
        """Item 2: seal succeeded but result.json is blocked by a directory —
        the decision payload must reach the fallback with an announcement."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f", stage=1)
            out.mkdir(parents=True, exist_ok=True)
            (out / "result.json").mkdir()   # IsADirectoryError on write
            p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                "--request", str(req)],
                               capture_output=True, text=True, cwd=str(REPO))
            self.assertNotIn("Traceback", p.stderr)
            self.assertEqual(p.returncode, result.EXIT_PASS,
                             "decision stands; the payload just relocates")
            self.assertIn("fallback location", p.stderr,
                          "relocated success result must be announced")

    def test_policy_block_without_root_is_exit31(self):
        """Item 3: KeyError escaped the policy except -> exit 1 traceback."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f")
            r = json.loads(req.read_text())
            r["policy"] = {"expected_digest": "sha256:" + "a" * 64}
            req.write_text(json.dumps(r))
            p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                "--request", str(req)],
                               capture_output=True, text=True, cwd=str(REPO))
            self.assertNotIn("Traceback", p.stderr)
            self.assertEqual(p.returncode, result.EXIT_POLICY,
                             f"expected exit 31, got {p.returncode}")

    def test_malformed_baseline_is_exit31(self):
        """Item 4: baseline.json/exceptions.json were parsed outside any
        handler; overlay.json was clean — the asymmetry was the tell."""
        for name, prefix in (("baseline.json", "cannot read baseline set"),
                             ("exceptions.json", "cannot read exception set")):
            with tempfile.TemporaryDirectory() as td:
                req, out = fx.build_root(Path(td) / "f", stage=2)
                pr = Path(json.loads(req.read_text())["policy"]["root"])
                (pr / name).write_text("{ broken")
                p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                    "--request", str(req)],
                                   capture_output=True, text=True, cwd=str(REPO))
                self.assertNotIn("Traceback", p.stderr, name)
                self.assertEqual(p.returncode, result.EXIT_POLICY,
                                 f"{name}: expected exit 31, got {p.returncode}")
                # Pin the reason came from the set loader, not any other
                # policy failure — otherwise a CLI-level catch-all could mask
                # the loader's own wrap being deleted (mutation round 2).
                env = json.loads((out / "result.json").read_text())
                self.assertIn(prefix, env["error"]["reason"], name)

    def test_load_adoption_sets_wraps_json_errors(self):
        """Unit-level pin for the loader's own wrap (belt layer)."""
        from hub.coherence import policy
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "baseline.json").write_text("{ broken")
            with self.assertRaises(policy.PolicyError) as c:
                policy.load_adoption_sets(td)
            self.assertIn("cannot read baseline set", str(c.exception))

    def test_null_expected_digest_is_rejected(self):
        """Item 5: the b6 fix verified wrong claims but accepted absent/null
        claims — verification could still be skipped by sending null. Assert
        the specific guard message: with only the mismatch backstop left,
        null yields exit 30 with a confusing 'mismatch' reason, so the code
        alone does not pin the guard (mutation round 2)."""
        for bad in (None, "", "   "):
            with tempfile.TemporaryDirectory() as td:
                req, out = fx.build_root(Path(td) / "f")
                r = json.loads(req.read_text())
                r["subject"]["expected_digest"] = bad
                req.write_text(json.dumps(r))
                p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                    "--request", str(req)],
                                   capture_output=True, text=True, cwd=str(REPO))
                self.assertNotIn("Traceback", p.stderr)
                self.assertEqual(p.returncode, result.EXIT_INVALID_INPUT,
                                 f"expected_digest={bad!r}: expected exit 30, "
                                 "got silent skip")
                env = json.loads((out / "result.json").read_text())
                self.assertIn("required and must be a non-empty",
                              env["error"]["reason"],
                              f"expected_digest={bad!r}: wrong guard fired")


class TestSchemacheckNegativeControls(unittest.TestCase):
    """Item 6: guard-of-the-guard. Disabling the enum, pattern, or
    additionalProperties enforcement arm of schemacheck left the full suite
    green — every conformance case only validated documents expected to pass.
    Each arm gets a dedicated invalid document."""

    _SCHEMA = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "size"],
        "properties": {
            "kind": {"enum": ["a", "b"]},
            "size": {"type": "integer", "minimum": 0},
            "code": {"type": "string", "pattern": "^sha256:[0-9a-f]{8}$"},
        },
    }

    def test_enum_arm_enforced(self):
        from hub.coherence import schemacheck
        errs = schemacheck.validate({"kind": "z", "size": 1}, self._SCHEMA)
        self.assertTrue(any("enum" in e for e in errs),
                        f"enum arm silent: {errs}")

    def test_type_arm_enforced(self):
        from hub.coherence import schemacheck
        errs = schemacheck.validate({"kind": "a", "size": "not-int"}, self._SCHEMA)
        self.assertTrue(any("type" in e for e in errs),
                        f"type arm silent: {errs}")

    def test_pattern_arm_enforced(self):
        from hub.coherence import schemacheck
        errs = schemacheck.validate(
            {"kind": "a", "size": 1, "code": "sha256:ZZZZ"}, self._SCHEMA)
        self.assertTrue(any("pattern" in e for e in errs),
                        f"pattern arm silent: {errs}")

    def test_additional_properties_arm_enforced(self):
        from hub.coherence import schemacheck
        errs = schemacheck.validate(
            {"kind": "a", "size": 1, "sneaky": True}, self._SCHEMA)
        self.assertTrue(any("unexpected property" in e for e in errs),
                        f"additionalProperties arm silent: {errs}")

    def test_minimum_arm_enforced(self):
        from hub.coherence import schemacheck
        errs = schemacheck.validate({"kind": "a", "size": -3}, self._SCHEMA)
        self.assertTrue(any("minimum" in e for e in errs),
                        f"minimum arm silent: {errs}")

    def test_required_arm_enforced(self):
        from hub.coherence import schemacheck
        errs = schemacheck.validate({"kind": "a"}, self._SCHEMA)
        self.assertTrue(any("required" in e for e in errs),
                        f"required arm silent: {errs}")


class TestOutputsTypeGuard(unittest.TestCase):
    """Round-3 audit item 2: non-string or NUL-bearing outputs must yield the
    documented invalid-input envelope, never exit 1 with a traceback."""

    def test_non_string_and_nul_outputs_rejected_cleanly(self):
        bad_values = [("list", ["x"]), ("int", 123), ("dict", {"a": 1}),
                      ("bool", True), ("nul-string", "a\x00b")]
        for label, val in bad_values:
            with tempfile.TemporaryDirectory() as td:
                req, out = fx.build_root(Path(td))
                r = json.loads(req.read_text())
                r["outputs"] = val
                req.write_text(json.dumps(r))
                p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                    "--request", str(req)],
                                   capture_output=True, text=True, cwd=str(REPO))
                self.assertNotIn("Traceback", p.stderr,
                                 f"outputs={label}: raw traceback")
                self.assertEqual(p.returncode, result.EXIT_INVALID_INPUT,
                                 f"outputs={label}: expected exit 30, got {p.returncode}")
                # The declared outputs value is unusable; the envelope lands
                # beside the request file instead.
                env_path = req.parent / "result.json"
                self.assertTrue(env_path.exists(),
                                f"outputs={label}: no envelope written")
                res = json.loads(env_path.read_text())
                self.assertEqual(res["decision"], "ERROR",
                                 f"outputs={label}: must be an error envelope")
                self.assertEqual(res["error"]["class"], "invalid-input",
                                 f"outputs={label}: wrong error class")




if __name__ == "__main__":
    unittest.main()
