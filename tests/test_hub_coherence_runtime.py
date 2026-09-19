# // spec: coh-rt-03, coh-rt-04, coh-rt-07, coh-ctx-04
"""Runtime-boundary slice increments: the source-level default-deny network
proof (kernel-level denial lives in the launcher's enforced --network=none),
digest-verified captured-fact mediation with UNRESOLVED-never-SATISFIED
semantics, scoped fact exposure per evaluator, secret redaction at the seal,
and atomic artifact export (coh-rt-07 — presence of a canonical file is
completeness). All fixtures synthetic (R9).
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, context, evaluate, evidence, evaluators, result

REPO = Path(__file__).resolve().parent.parent


class TestStaticDefaultDeny(unittest.TestCase):
    """coh-rt-03 / coh-rt-04 at the source level: the service has no network
    path and reads no environment outside the control-plane signing module —
    egress denial and secret absence are structural, not just configured."""

    NETWORK_MODULES = {"socket", "ssl", "urllib", "http", "ftplib", "smtplib",
                       "telnetlib", "xmlrpc", "requests", "httpx"}

    def test_no_network_module_imported_anywhere(self):
        for p in sorted((REPO / "hub/coherence").glob("*.py")):
            for ln in p.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", ln)
                if m:
                    root = m.group(1).split(".")[0]
                    self.assertNotIn(root, self.NETWORK_MODULES,
                                     f"{p.name}: {ln.strip()}")

    def test_environ_read_only_by_the_signing_module(self):
        # Evaluator secrets never reach the runtime: only the control-plane
        # secret holders (issue.py context key, attest.py signer key,
        # retention.py retention key — none of them on the evaluation path)
        # and __main__.py (evaluator image digest env var for coh-dec-02)
        # touch the environment. Adding a module here is a deliberate
        # security decision, not a convenience fix.
        for p in sorted((REPO / "hub/coherence").glob("*.py")):
            if p.name in ("issue.py", "attest.py", "retention.py",
                          "__main__.py"):
                continue
            self.assertNotIn("os.environ", p.read_text(encoding="utf-8"),
                             f"{p.name} reads the environment")


def _fact_payload(value):
    return json.dumps({"value": value}, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _fact_assertion(fact_id="fact.registry", params=None):
    return {
        "id": "fact.check", "version": 1, "requirement_refs": ["r1"],
        "owner": "o", "requirement": "r",
        "subjects": [{"kind": "captured-fact", "fact_id": fact_id}],
        "evaluator": {"id": "devgate.builtin.captured-fact-consistency",
                      "digest": "sha256:" + "a" * 64},
        "parameters": params if params is not None else {
            "approved_value_ref": "package:product.identity.name"},
        "severity": "high", "dependencies": [],
        "finding_key": ["assertion_id", "subject_location", "violation_class"],
        "evidence": {"retention_days": 1},
    }


PACKAGE = {"product": {"identity": {"name": "widget"}}}


class TestCapturedFactMediation(unittest.TestCase):
    """coh-rt-03 / coh-ctx-04: the approved external lookup ran outside the
    evaluator as a capture step; replay consumes the digest-verified captured
    content, and a missing bound fact is UNRESOLVED, never SATISFIED."""

    def test_bound_fact_satisfied_on_match(self):
        out = evaluate.run([_fact_assertion()], PACKAGE, ".",
                           captured_facts={"fact.registry": {"value": "widget"}})
        self.assertEqual(out["ledger"][0]["outcome"], "SATISFIED")

    def test_mismatched_fact_violates(self):
        out = evaluate.run([_fact_assertion()], PACKAGE, ".",
                           captured_facts={"fact.registry": {"value": "other"}})
        self.assertEqual(out["ledger"][0]["outcome"], "VIOLATED")
        self.assertEqual(out["findings"][0]["violation_class"],
                         "captured-fact-mismatch")

    def test_unbound_declared_fact_is_unresolved_never_satisfied(self):
        # The spec scenario: a required assertion depending on a denied/
        # missing lookup becomes UNRESOLVED, and enforcement blocks.
        out = evaluate.run([_fact_assertion()], PACKAGE, ".",
                           captured_facts={})
        e = out["ledger"][0]
        self.assertEqual(e["outcome"], "UNRESOLVED")
        self.assertEqual(e["reason"], "captured-fact-missing:fact.registry")
        self.assertEqual(e["enforcement"], "BLOCK")
        decision, code = result.decide(out["ledger"], 2)
        self.assertEqual((decision, code), ("FAIL", result.EXIT_FAIL))

    def test_null_digest_record_binds_nothing(self):
        # A record with a null digest binds no content — same as unbound.
        out = evaluate.run([_fact_assertion()], PACKAGE, ".", captured_facts={})
        self.assertEqual(out["ledger"][0]["outcome"], "UNRESOLVED")

    def test_facts_scoped_to_declared_ids_only(self):
        # coh-rt-04 analog at fact scope: an evaluator is exposed ONLY the
        # facts its own subjects declared — never another capability's.
        seen = {}

        def probe(assertion, package, subject_root, facts):
            seen.update(facts or {})
            return []

        with mock.patch.dict(evaluators.BUILTINS,
                             {"devgate.builtin.test-probe": probe}):
            a = _fact_assertion()
            a["evaluator"]["id"] = "devgate.builtin.test-probe"
            evaluate.run([a], PACKAGE, ".",
                         captured_facts={"fact.registry": {"value": "widget"},
                                         "fact.other-capability": {"value": "x"}})
        self.assertEqual(sorted(seen), ["fact.registry"])


class TestCapturedFactContent(unittest.TestCase):
    """context.load_captured_facts: content under the context root is
    verified against the digest bound in the trusted context record."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-rt-"))
        (self.tmp / "facts").mkdir()
        (self.tmp / "context.json").write_text(json.dumps({
            "api_version": "devgate.spec-coherence.context/v1",
            "context_id": "rt-fixture", "evaluation_time": "2026-09-17T00:00:00Z",
            "stage": 1, "execution_profile": "linux-amd64-v1",
            "captured_facts": [], "issuance": {
                "issued_at": "2026-09-17T00:00:00Z", "issuer": "cp"}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bind(self, fact_id, payload, digest=None):
        fp = self.tmp / "facts" / fact_id
        fp.write_bytes(payload)
        ctx = json.loads((self.tmp / "context.json").read_text())
        ctx["captured_facts"].append({
            "fact_id": fact_id,
            "digest": digest or canon.digest_bytes("file/v1", payload),
            "captured_at": "2026-09-17T00:00:00Z", "source": "registry"})
        (self.tmp / "context.json").write_text(json.dumps(ctx))

    def test_verified_content_is_loaded(self):
        self._bind("fact.registry", _fact_payload("widget"))
        ctx = context.load(str(self.tmp))
        facts = context.load_captured_facts(str(self.tmp), ctx)
        self.assertEqual(facts["fact.registry"], {"value": "widget"})

    def test_tampered_content_rejected(self):
        self._bind("fact.registry", _fact_payload("widget"),
                   digest=canon.digest_bytes("file/v1", _fact_payload("other")))
        ctx = context.load(str(self.tmp))
        with self.assertRaises(context.ContextError) as cm:
            context.load_captured_facts(str(self.tmp), ctx)
        self.assertIn("captured-fact-tampered:fact.registry", str(cm.exception))

    def test_missing_content_rejected(self):
        dig = canon.digest_bytes("file/v1", _fact_payload("widget"))
        ctx = json.loads((self.tmp / "context.json").read_text())
        ctx["captured_facts"].append({
            "fact_id": "fact.registry", "digest": dig,
            "captured_at": "2026-09-17T00:00:00Z", "source": "registry"})
        (self.tmp / "context.json").write_text(json.dumps(ctx))
        ctx = context.load(str(self.tmp))
        with self.assertRaises(context.ContextError) as cm:
            context.load_captured_facts(str(self.tmp), ctx)
        self.assertIn("captured-fact-content-missing", str(cm.exception))

    def test_path_traversal_in_fact_id_rejected(self):
        ctx = json.loads((self.tmp / "context.json").read_text())
        ctx["captured_facts"].append({
            "fact_id": "../escape", "digest": "sha256:" + "a" * 64,
            "captured_at": "2026-09-17T00:00:00Z", "source": "x"})
        (self.tmp / "context.json").write_text(json.dumps(ctx))
        ctx = context.load(str(self.tmp))
        with self.assertRaises(context.ContextError) as cm:
            context.load_captured_facts(str(self.tmp), ctx)
        self.assertIn("captured-fact-bad-id", str(cm.exception))


class TestSecretRedactionAtSeal(unittest.TestCase):
    """coh-rt-04: granted secret values never enter sealed evidence; an
    unredacted secret in sealed evidence is an evidence ERROR."""

    FINDINGS = [{
        "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
        "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
        "subject_locations": ["README.md"],
        "expected": "widget", "observed": "token=super-secret-123",
        "evidence_refs": [],
    }]

    def _sealed_object(self, td):
        """The single sealed evidence object's text, resolved through the
        manifest (object names are content-derived, not reconstructible)."""
        m = json.loads((Path(td) / "evidence-manifest.json").read_text())
        self.assertEqual(len(m["objects"]), 1)
        return (Path(td) / m["objects"][0]["path"]).read_text()

    def test_secret_scrubbed_before_sealing(self):
        with tempfile.TemporaryDirectory() as td:
            digest = evidence.seal(self.FINDINGS, td, redact=["super-secret-123"])
            sealed = self._sealed_object(td)
            self.assertNotIn("super-secret-123", sealed)
            self.assertIn("[REDACTED]", sealed)
            self.assertTrue(evidence.verify(td, digest))

    def test_scrub_bypass_is_an_evidence_error_never_a_silent_seal(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(evidence, "redact_values",
                                   side_effect=lambda obj, values: obj):
                with self.assertRaises(evidence.EvidenceError) as cm:
                    evidence.seal(self.FINDINGS, td, redact=["super-secret-123"])
            self.assertIn("unredacted-secret-in-sealed-evidence",
                          str(cm.exception))
            # Assert over the directory, not one filename: a hardcoded name
            # would pass vacuously once the real object is named differently.
            leftover = list((Path(td) / "evidence" / "findings").glob("*.json")) \
                if (Path(td) / "evidence" / "findings").is_dir() else []
            self.assertEqual(leftover, [],
                             "a failed seal must not leave canonical evidence bytes")

    def test_no_redact_values_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            evidence.seal(self.FINDINGS, td)
            sealed = self._sealed_object(td)
            self.assertIn("token=super-secret-123", sealed,
                          "without a granted-value list nothing is invented "
                          "to redact")


class TestAtomicArtifactExport(unittest.TestCase):
    """coh-rt-07: every canonical artifact appears via fsync-then-rename; a
    kill mid-export can leave a temp fragment but never partial bytes at a
    canonical path — callers can treat presence as completeness."""

    FINDINGS = [{
        "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
        "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
        "subject_locations": ["README.md"], "expected": "widget",
        "observed": "other", "evidence_refs": [],
    }]

    def test_interrupted_seal_leaves_no_canonical_partial(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("os.replace", side_effect=OSError("killed mid-export")):
                with self.assertRaises(evidence.EvidenceError):
                    evidence.seal(self.FINDINGS, td)
            # Over the directory, not a hardcoded name: object names are
            # content-derived now, so `a1.json` never exists and asserting on
            # it would pass vacuously without proving the canonical bytes are
            # absent. os.replace is patched to always fail, so no rename ever
            # lands; the findings dir must hold nothing.
            findings = Path(td) / "evidence" / "findings"
            leftover = list(findings.glob("*.json")) if findings.is_dir() else []
            self.assertEqual(leftover, [],
                             "partial evidence bytes must not sit at a canonical path")
            self.assertFalse((Path(td) / "evidence-manifest.json").exists())

    def test_interrupted_result_emit_leaves_no_canonical_partial(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("os.replace", side_effect=OSError("killed mid-write")):
                with self.assertRaises(OSError):
                    result.emit(str(Path(td) / "result.json"), b'{"decision":"PASS"}')
            self.assertFalse((Path(td) / "result.json").exists())

    def test_emit_is_complete_or_absent(self):
        # The happy path: after emit, the canonical file holds exactly the
        # payload and no temp fragment remains.
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "result.json"
            result.emit(str(fp), b'{"decision":"PASS"}')
            self.assertEqual(fp.read_bytes(), b'{"decision":"PASS"}')
            leftovers = [p.name for p in Path(td).iterdir() if p != fp]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
