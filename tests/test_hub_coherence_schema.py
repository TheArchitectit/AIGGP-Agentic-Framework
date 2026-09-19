# // spec: coh-pol-04, coh-pol-05, coh-pol-06, coh-dec-04, coh-eval-02, coh-ctx-03
"""Frozen S2 conformance suite: Fixtures A-F, full exit-code sweep, error
envelopes. Dual-runnable. All fixtures synthetic (R9).
"""
import json
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


class TestErrorEnvelopes(unittest.TestCase):
    def test_null_identities_not_fabricated(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td))
            r = json.loads(req.read_text())
            r["subject"]["root"] = str(Path(td) / "nope")
            req.write_text(json.dumps(r))
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "ERROR")
            ids = res["identities"]
            # Subject could not be computed -> explicit null, never a fake digest.
            self.assertIsNone(ids["subject_digest"])
            for v in ids.values():
                if v is not None:
                    self.assertNotEqual(v, ZERO_DIGEST)

    def test_successful_result_has_no_fabricated_identity(self):
        """The actual Defect-3 case: a SUCCESSFUL result must carry null, not a
        zero digest, for identities the slice cannot compute. This is the case
        the error-envelope-only guard missed (audit finding 2)."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "PASS")
            self.assertIsNone(res["evaluator_image_digest"],
                              "slice cannot compute this; null, never fabricated")
            self.assertIsNone(res["platform"]["manifest_digest"])
            # coh-id-04 names index_digest as an identity field too (round-2
            # audit finding 2: it was left unguarded).
            self.assertIsNone(res["platform"]["index_digest"],
                              "slice cannot compute this; null, never fabricated")
            for v in (res["subject_digest"], res["openspec_digest"],
                      res["policy_digest"], res["context_digest"]):
                self.assertNotEqual(v, ZERO_DIGEST)

    def test_wrong_expected_digest_is_rejected(self):
        """Round-2 finding 6a: expected_digest was carried but never verified,
        so a wrong value still produced exit 0 / PASS."""
        for field, label in (("subject", "subject"), ("openspec", "openspec"),
                             ("context", "context")):
            with tempfile.TemporaryDirectory() as td:
                req, out = fx.build_root(Path(td), stage=1)
                r = json.loads(req.read_text())
                r[field]["expected_digest"] = "sha256:" + "9" * 64
                req.write_text(json.dumps(r))
                code, res = _run(req, out)
                self.assertNotEqual(code, 0, f"wrong {label} digest must not PASS")
                self.assertEqual(res["decision"], "ERROR",
                                 f"wrong {label} digest must be ERROR")

    def test_malformed_request_yields_envelope_not_traceback(self):
        """Round-2 finding 6b: malformed requests must produce an ERROR envelope
        with exit 30, never a raw traceback."""
        cases = [
            ("not json at all", "malformed request"),
            (json.dumps({"api_version": "devgate.spec-coherence/v1"}),
             "missing required property"),       # runtime schema validation
            (json.dumps(["a", "list"]), "must be a JSON object"),
        ]
        for i, (body, expect_in_reason) in enumerate(cases):
            with tempfile.TemporaryDirectory() as td:
                rp = Path(td) / "request.json"
                rp.write_text(body)
                out = Path(td) / "out"
                r = subprocess.run([sys.executable, "-m", "hub.coherence",
                                    "--request", str(rp)],
                                   capture_output=True, text=True, cwd=str(REPO))
                self.assertEqual(r.returncode, result.EXIT_INVALID_INPUT,
                                 f"case {i}: expected exit 30, got {r.returncode}")
                self.assertNotIn("Traceback", r.stderr,
                                 f"case {i}: must not emit a raw traceback")
                # Envelope is written beside the request when no outputs field
                # is readable — never into the caller's cwd.
                env_path = out / "result.json"
                if not env_path.exists():
                    env_path = rp.parent / "result.json"
                self.assertTrue(env_path.exists(),
                                f"case {i}: no envelope written")
                self.assertFalse((Path(REPO) / "result.json").exists(),
                                 f"case {i}: must not write into the repo cwd")
                env = json.loads(env_path.read_text())
                # Pin WHICH guard fired, so the field check cannot be deleted
                # while a later KeyError still happens to yield exit 30.
                self.assertIn(expect_in_reason, env["error"]["reason"],
                              f"case {i}: expected the {expect_in_reason!r} guard to fire")

    def test_unknown_overlay_severity_is_policy_error_not_crash(self):
        """Round-2 finding 1: an unrecognized severity string raised an uncaught
        KeyError (exit 1, no envelope) instead of exit 31."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            polroot = Path(json.loads(req.read_text())["policy"]["root"])
            from hub.coherence import canon as C
            bundle = json.loads((polroot / "policy.json").read_text())
            bundle["required_assertions"] = ["product.identity"]
            bundle["assertion_severity_floor"] = {"product.identity": "high"}
            (polroot / "policy.json").write_text(json.dumps(bundle))
            r = json.loads(req.read_text())
            r["policy"]["expected_digest"] = C.digest_obj("policy/v1", bundle)
            req.write_text(json.dumps(r))
            (polroot / "overlay.json").write_text(json.dumps(
                {"assertions": [{"id": "product.identity", "severity": "SEVERE"}]}))
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_POLICY, "must be exit 31, not a crash")
            self.assertEqual(res["decision"], "ERROR")

    def test_overlay_unknown_assertion_is_pinned(self):
        """Round-2 finding 3: replacing this raise with a silent skip left the
        suite green."""
        from hub.coherence import policy
        with self.assertRaises(policy.OverlayError) as c:
            policy.apply_overlay(
                [fx.assertion(aid="a1")],
                {"assertions": [{"id": "does-not-exist", "severity": "critical"}]},
                {"required_assertions": [], "approved_evaluators": [],
                 "assertion_severity_floor": {}})
        self.assertIn("unknown assertion", str(c.exception))

    def test_overlay_preserves_unmentioned_assertions(self):
        from hub.coherence import policy
        out = policy.apply_overlay(
            [fx.assertion(aid="a1"), fx.assertion(aid="a2")],
            {"assertions": [{"id": "a1", "severity": "critical"}]},
            {"required_assertions": [], "approved_evaluators": [],
             "assertion_severity_floor": {}})
        self.assertEqual(sorted(a["id"] for a in out), ["a1", "a2"])

    def test_outputs_never_defaults_to_callers_cwd(self):
        """An absent, empty, or whitespace-only `outputs` must not silently
        write result.json into whatever directory the process started in.
        Found by the lead's own B1 falsification run, which polluted the repo
        root and was caught by test_malformed_request_... above."""
        for label, val in (("empty", ""), ("whitespace", "   ")):
            with tempfile.TemporaryDirectory() as td:
                req, _ = fx.build_root(Path(td), stage=3,
                                       declared_name="other", approved_name="widget")
                r = json.loads(req.read_text())
                r["outputs"] = val
                req.write_text(json.dumps(r))
                stray = Path(REPO) / "result.json"
                had = stray.exists()
                subprocess.run([sys.executable, "-m", "hub.coherence",
                                "--request", str(req)],
                               capture_output=True, text=True, cwd=str(REPO))
                if stray.exists() and not had:
                    stray.unlink()
                    self.fail(f"{label}: wrote result.json into the caller's cwd")
                # The envelope must land beside the request instead.
                self.assertTrue(
                    (Path(req).parent / "result.json").exists()
                    or (Path(td) / "out" / "result.json").exists(),
                    f"{label}: no envelope written anywhere findable")

    def test_error_is_never_pass_or_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), policy_digest_ok=False)
            _, res = _run(req, out)
            self.assertNotIn(res["decision"], ("PASS", "ADVISORY"))

    def test_exit_result_disagreement_is_error_for_caller(self):
        """Frozen criterion: exit/result disagreement resolves to ERROR for the
        caller, never in favor of the permissive signal. Missing or malformed
        result with any exit code is ERROR."""
        from hub.coherence import result as R
        # Simulate a caller applying the contract.
        def caller_view(exit_code, result_doc):
            if result_doc is None:
                return "ERROR"
            expected_exit, _ = R.decide(
                result_doc.get("assertion_results", []),
                stage=1 if result_doc.get("decision") == "ADVISORY" else 3,
                blocked=result_doc.get("decision") == "FAIL")
            mapping = {"PASS": 0, "ADVISORY": 10, "FAIL": 20, "ERROR": 30}
            if mapping.get(result_doc.get("decision")) != exit_code:
                return "ERROR"
            return result_doc["decision"]
        self.assertEqual(caller_view(20, {"decision": "PASS", "assertion_results": []}), "ERROR")
        self.assertEqual(caller_view(0, None), "ERROR")
        # And the real CLI never emits a disagreeing pair.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="x", approved_name="widget", stage=3)
            code, res = _run(req, out)
            self.assertEqual(caller_view(code, res), res["decision"])

    def test_canonical_result_has_no_attestation_fields(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            _, res = _run(req, out)
            self.assertNotIn("attestation_digest", res)
            for forbidden in ("timestamp", "duration_ms", "hostname"):
                self.assertNotIn(forbidden, res)

    def test_error_envelope_validates_against_frozen_schema(self):
        from hub.coherence import schemacheck
        schema = json.loads((REPO / "hub/coherence/schemas/error-envelope.schema.json").read_text())
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), policy_digest_ok=False)
            _, res = _run(req, out)
            errs = schemacheck.validate(res, schema)
            self.assertEqual(errs, [], f"error envelope violates its schema: {errs}")


class TestSchemaConformance(unittest.TestCase):
    """The frozen schemas are wired into the gate: emitted results must satisfy
    them (closes audit finding 3 — schema drift now fails a test)."""

    def _schema(self, name):
        p = REPO / "hub/coherence/schemas" / name
        return json.loads(p.read_text())

    def test_pass_result_validates(self):
        from hub.coherence import schemacheck
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            _, res = _run(req, out)
            errs = schemacheck.validate(res, self._schema("result.schema.json"))
            self.assertEqual(errs, [], f"PASS result violates result.schema.json: {errs}")

    def test_fail_result_with_findings_validates(self):
        """Non-PASS results carry fingerprint/exception_id — the fields whose
        absence from the schema made every non-PASS result invalid (finding 3)."""
        from hub.coherence import schemacheck
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="x", approved_name="widget", stage=3)
            _, res = _run(req, out)
            self.assertEqual(res["decision"], "FAIL")
            self.assertTrue(res["findings"])
            errs = schemacheck.validate(res, self._schema("result.schema.json"))
            self.assertEqual(errs, [], f"FAIL result with findings violates schema: {errs}")

    def test_exception_advisory_result_validates(self):
        from hub.coherence import schemacheck
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid="assertion-0")]
            exc = [fx.exception_entry("assertion-0", 1, "README.md", "identity-mismatch",
                                      expires_at="2027-01-01T00:00:00Z")]
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, exceptions=exc, stage=2)
            _, res = _run(req, out)
            self.assertEqual(res["findings"][0]["enforcement"], "EXCEPTION-ADVISORY")
            errs = schemacheck.validate(res, self._schema("result.schema.json"))
            self.assertEqual(errs, [], f"EXCEPTION-ADVISORY result violates schema: {errs}")

    def test_schemacheck_detects_a_real_drift(self):
        """Guard the guard: the validator must reject a wrong-shaped result."""
        from hub.coherence import schemacheck
        bad = {"api_version": "devgate.spec-coherence.result/v1", "decision": "PASS"}
        errs = schemacheck.validate(bad, self._schema("result.schema.json"))
        self.assertTrue(errs, "validator must reject a result missing required fields")

    def test_frozen_schema_files_are_strict(self):
        """Round-3 residual: relaxing additionalProperties:false inside a
        schema FILE makes every conformance test vacuous — the suite validated
        documents against schemas but never asserted the schemas' own strictness.
        Every wire-contract schema object must forbid undeclared properties."""
        strict_files = ["result.schema.json", "request.schema.json",
                        "error-envelope.schema.json", "attestation.schema.json",
                        "subject-manifest.schema.json",
                        "evidence-manifest.schema.json", "package.schema.json",
                        "assertion.schema.json", "evaluation-context.schema.json",
                        "policy-bundle.schema.json", "exception.schema.json",
                        "baseline-entry.schema.json",
                        "execution-profiles.schema.json"]
        def walk(node, src, path):
            problems = []
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    if node.get("additionalProperties") is not False:
                        problems.append(
                            f"{src} {path}: object schema must set "
                            f"additionalProperties false")
                for k, v in node.items():
                    problems.extend(walk(v, src, f"{path}/{k}"))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    problems.extend(walk(v, src, f"{path}[{i}]"))
            return problems
        errs = []
        for name in strict_files:
            errs.extend(walk(self._schema(name), name, "$"))
        self.assertEqual(errs, [], f"schema files not strict: {errs}")

    def test_frozen_schemas_use_no_unenforced_vocabulary(self):
        """Round-5 finding 2, class-level lock: a constraint keyword the stdlib
        checker does not implement is silently ignored — a schema that LOOKS
        strict but enforces nothing (minLength shipped this way). Every
        standard constraint keyword used by a frozen file must be in
        schemacheck.SUPPORTED, so adding vocabulary without an enforcement
        arm fails here."""
        from hub.coherence import schemacheck
        vocab = {"maxLength", "maxItems", "maximum", "exclusiveMinimum",
                 "exclusiveMaximum", "multipleOf", "uniqueItems",
                 "minProperties", "maxProperties", "patternProperties",
                 "additionalItems", "oneOf", "anyOf", "allOf", "not", "if",
                 "then", "else", "dependencies", "propertyNames", "contains",
                 "minLength"}
        used = {}
        for name in ["result.schema.json", "request.schema.json",
                     "error-envelope.schema.json", "attestation.schema.json",
                     "subject-manifest.schema.json",
                     "evidence-manifest.schema.json", "package.schema.json",
                     "assertion.schema.json", "evaluation-context.schema.json",
                     "policy-bundle.schema.json", "exception.schema.json",
                     "baseline-entry.schema.json",
                     "execution-profiles.schema.json"]:
            def collect(node):
                if isinstance(node, dict):
                    for k, v in node.items():
                        if k == "properties" and isinstance(v, dict):
                            # Keys here are property NAMES, not schema
                            # keywords (assertion.schema.json legitimately has
                            # a "dependencies" property); only their values
                            # are schemas.
                            for pv in v.values():
                                collect(pv)
                            continue
                        if k in vocab:
                            used.setdefault(k, set()).add(name)
                        collect(v)
                elif isinstance(node, list):
                    for i in node:
                        collect(i)
            collect(self._schema(name))
        unenforced = {k: sorted(v) for k, v in used.items()
                      if k not in schemacheck.SUPPORTED}
        self.assertEqual(unenforced, {},
                         "frozen schemas use vocabulary schemacheck ignores: "
                         f"{unenforced}")

class TestEnforcementBlocks(unittest.TestCase):
    """End-to-end enforcement outcomes driven through the real CLI. These were
    misgrouped under the schema class by the file split."""

    def test_unresolved_enforced_blocks_end_to_end(self):
        """Audit finding 1 at the CLI level: an UNRESOLVED required assertion at
        an enforced stage must give FAIL/20, not ADVISORY/10. (The unit-level
        equivalent lives in test_hub_coherence.py::TestResult.) The vehicle is
        an empty selector — since the coh-rt-06 planner allowlist, a
        repo-supplied evaluator is rejected as invalid input (exit 30) before
        it could ever produce an UNRESOLVED ledger entry."""
        with tempfile.TemporaryDirectory() as td:
            a = fx.assertion(aid="a1")
            req, out = fx.build_root(Path(td), assertions=[a], stage=2,
                                     subject_files={"README.md": "# just a readme\n"})
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "FAIL",
                             "unresolved required assertion must block at stage >= 2")
            self.assertEqual(code, result.EXIT_FAIL)

    def test_unresolved_enforced_at_stage1_stays_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            a = fx.assertion(aid="a1")
            req, out = fx.build_root(Path(td), assertions=[a], stage=1,
                                     subject_files={"README.md": "# just a readme\n"})
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "ADVISORY")
            self.assertEqual(code, result.EXIT_ADVISORY)

    def test_violation_without_finding_detail_blocks(self):
        """coh-eval-03: a ledger entry VIOLATED with no matching finding object
        is an evidence defect for enforced assertions and must block, with a
        stable reason code."""
        from hub.coherence import adoption
        ledger = [{"assertion_id": "a1", "version": 1, "outcome": "VIOLATED",
                   "reason": None, "enforcement": "ADVISORY"}]
        out = adoption.evaluate(ledger, [], [{"id": "a1", "version": 1}],
                                [], [], stage=2, evaluation_time="2026-09-17T00:00:00Z")
        self.assertTrue(out["blocked"])
        self.assertEqual(out["ledger"][0]["enforcement"], "BLOCK")
        self.assertEqual(out["ledger"][0]["reason"], "violation-without-finding-detail")

    def test_violation_with_finding_uses_finding_enforcement(self):
        from hub.coherence import adoption
        ledger = [{"assertion_id": "a1", "version": 1, "outcome": "VIOLATED",
                   "reason": None, "enforcement": "BLOCK"}]
        findings = [{"assertion_id": "a1", "finding_key": "a1|README.md|identity-mismatch",
                     "violation_class": "identity-mismatch", "subject_locations": ["README.md"],
                     "enforcement": "ADVISORY"}]
        out = adoption.evaluate(ledger, findings, [{"id": "a1", "version": 1}],
                                [{"fingerprint": {"assertion_id": "a1", "assertion_version": 1,
                                                  "subject_location": "README.md",
                                                  "violation_key": "identity-mismatch"},
                                  "status": "open"}],
                                [], stage=2, evaluation_time="2026-09-17T00:00:00Z")
        self.assertFalse(out["blocked"], "baseline-named debt must not block")
        self.assertEqual(out["ledger"][0]["enforcement"], "ADVISORY")


class TestSchemaHome(unittest.TestCase):
    """F1 regression guard: the frozen contracts must resolve from the SERVICE
    package, never from repository or change-package layout. The pinned image
    carries only hub/ — a resolver that walks back out to openspec/ breaks
    every in-container invocation while host-side runs keep passing."""

    def test_schemas_live_with_the_service_package(self):
        from hub.coherence import schemacheck
        pkg_dir = Path(schemacheck.__file__).resolve().parent / "schemas"
        self.assertTrue((pkg_dir / "request.schema.json").is_file(),
                        "frozen schemas must ship inside the service package")
        self.assertEqual(Path(schemacheck.SCHEMA_DIR).resolve(),
                         pkg_dir.resolve())
        from hub.coherence import __main__ as cli
        self.assertEqual(Path(cli.SCHEMA_DIR).resolve(), pkg_dir.resolve())

    def test_load_resolves_by_name(self):
        from hub.coherence import schemacheck
        schema = schemacheck.load("request.schema.json")
        self.assertEqual(schema.get("$schema", "").startswith(
            "http://json-schema.org/draft-07"), True)


if __name__ == "__main__":
    unittest.main()
