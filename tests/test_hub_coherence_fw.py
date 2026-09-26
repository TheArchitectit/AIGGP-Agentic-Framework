# fw-* evaluator integrity: kills the mutation blind spots found in
# hub/coherence/evidence.py (raise-removals + fail-closed return flips).
# Every test here encodes a refusal: a tampered, malformed, escaping, or
# unattributed evidence bundle must be rejected — never accepted, never
# crashed through.
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, evidence


def _finding(aid="a1", expected="widget", observed="other"):
    return {
        "assertion_id": aid, "finding_key": f"{aid}|x|identity-mismatch",
        "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
        "subject_locations": ["README.md"], "expected": expected,
        "observed": observed, "evidence_refs": [],
    }


class TestVerifyFailClosed(unittest.TestCase):
    """verify()'s early `return False` paths are the fail-closed contract:
    flipping any of them to True must be caught here."""

    def test_missing_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(evidence.verify(td, "sha256:" + "a" * 64))

    def test_unparseable_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "evidence-manifest.json").write_text('{"objects": [', encoding="utf-8")
            self.assertFalse(evidence.verify(td, "sha256:" + "a" * 64))

    def test_object_replaced_by_directory_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            digest = evidence.seal([_finding()], td)
            manifest = json.loads(
                (Path(td) / "evidence-manifest.json").read_text(encoding="utf-8"))
            obj = Path(td) / manifest["objects"][0]["path"]
            obj.unlink()
            obj.mkdir()
            self.assertFalse(evidence.verify(td, digest))

    def test_object_digest_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            digest = evidence.seal([_finding()], td)
            manifest = json.loads(
                (Path(td) / "evidence-manifest.json").read_text(encoding="utf-8"))
            obj = Path(td) / manifest["objects"][0]["path"]
            obj.write_text('{"tampered": true}', encoding="utf-8")
            self.assertFalse(evidence.verify(td, digest))

    def test_nonstring_object_path_rejected_not_crash(self):
        """A manifest entry with a non-string path must be rejected
        (False), never crash the verification path."""
        with tempfile.TemporaryDirectory() as td:
            manifest = {"api_version": "devgate.spec-coherence.evidence/v1",
                        "objects": [{"path": None, "digest": "sha256:" +
                                     "a" * 64}]}
            (Path(td) / "evidence-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            self.assertFalse(evidence.verify(td, "sha256:" + "a" * 64))

    def test_consistent_escaping_bundle_rejected(self):
        """The containment rule must hold even when every digest lines up:
        an attacker-controlled manifest plus a matching outside file must
        still be rejected because the object path escapes the bundle."""
        with tempfile.TemporaryDirectory() as td:
            outer = Path(td)
            payload = canon.canon({"secret": "value"})
            (outer / "payload.json").write_bytes(payload)
            h = canon.digest_bytes("evidence-manifest/v1", payload)
            bundle = outer / "bundle"
            bundle.mkdir()
            manifest = {
                "api_version": "devgate.spec-coherence.evidence/v1",
                "objects": [{"path": "../payload.json", "digest": h,
                             "media_type": "application/json",
                             "assertion_id": "a1",
                             "retention_class": "standard",
                             "redacted": True}]}
            md = canon.digest_obj("evidence-manifest/v1", manifest)
            (bundle / "evidence-manifest.json").write_bytes(canon.canon(manifest))
            self.assertFalse(evidence.verify(str(bundle), md))


class TestContainmentContract(unittest.TestCase):
    """contained() is the bundle-containment rule; its two rejection
    reasons are distinct contracts (malformed vs escaping) and both must
    stay loud."""

    def test_empty_path_rejected_as_malformed(self):
        from hub.coherence import evidence as E
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(E.EvidenceError) as c:
                E.contained(Path(td), "")
            self.assertIn("evidence-path-malformed", str(c.exception))

    def test_escaping_path_rejected_as_out_of_bounds(self):
        from hub.coherence import evidence as E
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(E.EvidenceError) as c:
                E.contained(Path(td), "../escape.json")
            self.assertIn("evidence-path-out-of-bounds", str(c.exception))


class TestSealErrorPaths(unittest.TestCase):
    """Sealing's EvidenceError paths are load-bearing fail-safes; removing
    one must turn a silent seal into a loud test failure."""

    def test_bad_assertion_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(evidence.EvidenceError):
                evidence.seal([_finding(aid="bad id!")], td)

    def test_unredacted_secret_never_sealed(self):
        """coh-rt-04: a granted secret that survives redaction makes
        sealing an ERROR — never a sealed secret."""
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            f = _finding(observed="sk-live-SUPERSECRET")
            # Bypass scrubbing: the seal-time RE-CHECK is the last line of
            # defense and must refuse on its own (coh-rt-04).
            with mock.patch.object(evidence, "redact_values",
                                   side_effect=lambda obj, values: obj):
                with self.assertRaises(evidence.EvidenceError):
                    evidence.seal([f], td,
                                  redact=["sk-live-SUPERSECRET"])

    def test_nonstring_redact_values_filtered(self):
        with tempfile.TemporaryDirectory() as td:
            digest = evidence.seal([_finding()], td,
                                   redact=["", 123, None])
            self.assertTrue(evidence.verify(td, digest))

    def test_retention_class_recorded_in_manifest(self):
        """The retention map must reach the manifest: an entry with
        retention_days gets a retention:Nd classification (not the
        default)."""
        with tempfile.TemporaryDirectory() as td:
            digest = evidence.seal([_finding()], td,
                                   retention_by_aid={"a1": 365})
            manifest = json.loads(
                (Path(td) / "evidence-manifest.json").read_text(encoding="utf-8"))
            classes = {o["assertion_id"]: o.get("retention_class")
                       for o in manifest["objects"]}
            self.assertEqual(classes.get("a1"), "retention:365d")

    def test_negative_retention_days_rejected(self):
        """A negative retention is invalid policy input, not a class
        label: sealing must refuse."""
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(evidence.EvidenceError):
                evidence.seal([_finding()], td,
                              retention_by_aid={"a1": -5})

    def test_seal_zero_findings_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            digest = evidence.seal([], td)
            self.assertTrue(
                (Path(td) / "evidence-manifest.json").exists())
            self.assertTrue(evidence.verify(td, digest))


if __name__ == "__main__":
    unittest.main()


REPO_FW = Path(__file__).resolve().parent.parent


class TestMutationToolCrashRecovery(unittest.TestCase):
    """The tool's SIGKILL-safety contract: a killed run leaves a backup
    sidecar, and the next run recovers the original — a mutant must never
    survive on disk unnoticed."""

    def test_stale_backup_is_recovered(self):
        import subprocess
        victim_src = (
            "def check(n):\n"
            "    return n >= 10\n"
        )
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            victim = tdp / "victim.py"
            victim.write_text(victim_src, encoding="utf-8")
            backup = victim.with_name(victim.name + ".mutation-backup")
            # Simulate a killed run: mutant on disk + stale backup.
            victim.write_text("def check(n):\n    return n < 10  # mutant\n", encoding="utf-8")
            backup.write_bytes(victim_src.encode())

            from scripts import mutation_check  # noqa: E402  (ported tool)
            self.assertTrue(mutation_check._Restore.recover(victim))
            self.assertEqual(victim.read_text(encoding="utf-8"), victim_src)
            self.assertFalse(backup.exists())

            # And a normal run afterwards leaves no sidecar behind.
            r = subprocess.run(
                [sys.executable, str(REPO_FW / "scripts" / "mutation_check.py"),
                 "--target", str(victim), "--tests", "true"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, cwd=str(REPO_FW))
            self.assertFalse(backup.exists(),
                             "clean run must consume the backup")
            self.assertEqual(victim.read_text(encoding="utf-8"), victim_src)
