# // spec: coh-ev-02, coh-ev-03, coh-ev-01
"""Evidence object path integrity (round-9 audit finding): sealing must give
every finding its own file, and every derived path — on the write side
(`seal`) and the read side (`verify`) — must stay inside the output bundle.

The bug: `seal` named each object file by `assertion_id` alone, but the engine
emits "zero-or-many findings per assertion" (design.md section 8), so a second
finding of one assertion overwrote the first on disk while keeping its own
digest in the manifest — `verify` then recomputed a digest from the last
written bytes and rejected every earlier entry. A legitimate Stage 2 run with
two violations of one assertion sealed a bundle its own `--verify-run` rejects.

The second bug: `assertion_id` is repository-declared (package specs) and
reached the filesystem unvalidated, so a hostile id could write outside the
run directory; and the same string is read back from a manifest an attacker may
have edited. Repository files are untrusted input (design.md: Repository
boundary); the id pattern is now enforced at planning through
`assertion.schema.json`, but seal() is reachable directly and is the last gate
before any write, so the checks pinned here stand on their own. All fixtures
synthetic (R9).
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, evidence
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent


def _finding(aid, loc, expected, observed, vclass="identity-mismatch"):
    """A finding shaped exactly as evaluators._mk emits one (identity_consistency
    and traceability_completeness both produce many of these per assertion_id)."""
    return {
        "assertion_id": aid,
        "finding_key": f"{aid}|{loc}|{vclass}",
        "subject_locations": [loc], "expected": expected, "observed": observed,
        "violation_class": vclass, "outcome": "VIOLATED", "enforcement": "BLOCK",
        "severity": "high", "evidence_refs": [],
    }


class TestEvidencePathIntegrity(unittest.TestCase):
    def test_multiple_findings_per_assertion_seal_to_distinct_files(self):
        """The collision, pinned: two findings of ONE assertion must each get
        their own evidence object and the sealed bundle must verify."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            out.mkdir()
            f1 = _finding("product.identity", "a.md", "widget", "gizmo")
            f2 = _finding("product.identity", "b.md", "widget", "gadgets")
            digest = evidence.seal([f1, f2], str(out))

            files = sorted((out / "evidence" / "findings").glob("*.json"))
            self.assertEqual(len(files), 2,
                             "two findings of one assertion must be two files")
            # No overwrite: each object's bytes carry that finding's own
            # subject location, not the last-written one.
            payloads = {json.loads(fp.read_text(encoding="utf-8"))["subject_locations"][0]
                        for fp in files}
            self.assertEqual(payloads, {"a.md", "b.md"})
            # Distinct refs, and the whole bundle verifies against its digest.
            self.assertNotEqual(f1["evidence_refs"], f2["evidence_refs"])
            self.assertTrue(evidence.verify(str(out), digest),
                            "a legitimate multi-finding bundle must verify")

    def test_repeat_seal_is_deterministic(self):
        """Same findings in the same order seal to byte-identical names and
        the same manifest digest (Fixture A's byte-identity contract)."""
        a = _finding("product.identity", "a.md", "w", "x")
        b = _finding("product.identity", "b.md", "w", "y")
        with tempfile.TemporaryDirectory() as td:
            d1 = evidence.seal([dict(a), dict(b)], f"{td}/one")
            d2 = evidence.seal([dict(a), dict(b)], f"{td}/two")
            self.assertEqual(d1, d2, "manifest digest is reproducible")
            n1 = sorted(p.name for p in
                        Path(f"{td}/one/evidence/findings").glob("*.json"))
            n2 = sorted(p.name for p in
                        Path(f"{td}/two/evidence/findings").glob("*.json"))
            self.assertEqual(n1, n2)

    def test_names_are_content_derived_not_positional(self):
        """A finding sealed alone takes the same filename it takes inside a
        larger batch: the name is derived from content, not list position."""
        a = _finding("product.identity", "a.md", "w", "x")
        b = _finding("product.identity", "b.md", "w", "y")
        with tempfile.TemporaryDirectory() as td:
            evidence.seal([dict(a)], f"{td}/solo")
            evidence.seal([dict(b), dict(a)], f"{td}/batch")
            solo = sorted(p.name for p in
                          Path(f"{td}/solo/evidence/findings").glob("*.json"))
            batch = sorted(p.name for p in
                           Path(f"{td}/batch/evidence/findings").glob("*.json"))
            self.assertIn(solo[0], batch)
            self.assertEqual(len(batch), 2)

    def test_duplicate_findings_collapse_to_one_matching_object(self):
        """Two identical findings are the same evidence: one file whose digest
        matches both manifest entries (dedup, not loss)."""
        with tempfile.TemporaryDirectory() as td:
            out = f"{td}/run"
            a = _finding("product.identity", "a.md", "w", "x")
            b = _finding("product.identity", "a.md", "w", "x")
            digest = evidence.seal([a, b], out)
            files = list(Path(out, "evidence/findings").glob("*.json"))
            self.assertEqual(len(files), 1)
            self.assertTrue(evidence.verify(out, digest))

    def test_retention_class_is_derived_from_declared_days(self):
        """coh-ev-02's manifest-completeness clause: every evidence object
        MUST be classified by retention. The only faithful signal in the
        assertion model is its declared evidence.retention_days (no invented
        bucket taxonomy — the spec schema leaves the class field free-form).
        The default preserves the current 'standard' string for callers that
        do not supply the map (backward-compat with all pre-existing tests).
        """
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            out.mkdir()
            a1 = _finding("a1", "x", "e", "o")
            a2 = _finding("a2", "y", "e", "o")
            a3 = _finding("a3", "z", "e", "o")
            evidence.seal([a1, a2, a3], str(out),
                          retention_by_aid={"a1": 30, "a2": 0})
            m = json.loads((out / "evidence-manifest.json").read_text(encoding="utf-8"))
            by_aid = {obj["assertion_id"]: obj["retention_class"]
                      for obj in m["objects"]}
            self.assertEqual(by_aid["a1"], "retention:30d")
            self.assertEqual(by_aid["a2"], "retention:0d")
            # a3 is unmapped — falls back to the pre-existing default.
            self.assertEqual(by_aid["a3"], "standard")

    def test_negative_retention_days_is_rejected_at_seal(self):
        """assertion.schema.json sets `minimum: 0`; a repository-declared
        negative days is invalid input reaching seal, not a class string."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            out.mkdir()
            with self.assertRaises(evidence.EvidenceError):
                evidence.seal([_finding("a1", "x", "e", "o")], str(out),
                              retention_by_aid={"a1": -1})

    def test_hostile_assertion_id_fails_closed_at_seal(self):
        """A repository-declared id that cannot name a file must be rejected
        before any write, with nothing created outside the output directory."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "deep" / "run"
            out.mkdir(parents=True)
            f = _finding("../../../PWNED", "a.md", "w", "x")
            with self.assertRaises(evidence.EvidenceError) as cm:
                evidence.seal([f], str(out))
            self.assertIn("bad-assertion-id", str(cm.exception))
            # Nothing escaped the bundle. Reaching this assert at all requires
            # seal to have raised (assertRaises above); a hostile id that
            # slipped past the guard would have written PWNED.json under
            # root/deep and landed on this list.
            strays = [p for p in root.rglob("PWNED*") if p.is_file()]
            self.assertEqual(strays, [],
                             f"seal wrote outside the output dir: {strays}")

    def test_id_with_trailing_newline_fails_closed_at_seal(self):
        """C1 audit: `_ASSERTION_ID_RE.match` with a trailing `$` lets Python
        match `"a1\n"` (the `$` sits before the final newline), naming a file
        `a1\n--….json`. That contradicts the planning gate — C1 fixed the
        same slip in schemacheck with re.fullmatch — and two guards on
        opposite ends of the pipeline disagreeing on the same grammar is the
        round-9 family. seal's copy must reject what the schema rejects."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            out.mkdir()
            with self.assertRaises(evidence.EvidenceError) as cm:
                evidence.seal([_finding("a1\n", "x", "e", "o")], str(out))
            self.assertIn("bad-assertion-id", str(cm.exception))
            self.assertEqual(list((out / "evidence").rglob("*")), [],
                             "a rejected id must not leave a half-sealed bundle")

    def test_escaping_manifest_path_is_a_verify_failure(self):
        """The read side: a manifest whose object path traverses outside the
        bundle must fail verify even when the out-of-bounds file's digest
        matches — verify may not read beyond the bundle to answer a question."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "run"
            (out / "evidence" / "findings").mkdir(parents=True)
            payload = canon.canon({"subject_locations": ["x"], "expected": "e",
                                   "observed": "o", "assertion_id": "a",
                                   "finding_key": "a|x|c"})
            digest = canon.digest_bytes("evidence-manifest/v1", payload)
            # Plant the matching bytes OUTSIDE the bundle and point the
            # manifest at them via a traversal path.
            stray = root / "stray.json"
            stray.write_bytes(payload)
            manifest = {
                "api_version": "devgate.spec-coherence.evidence/v1",
                "objects": [{"path": "../stray.json", "digest": digest,
                             "media_type": "application/json",
                             "assertion_id": "a", "retention_class": "standard",
                             "redacted": True}],
            }
            (out / "evidence-manifest.json").write_bytes(canon.canon(manifest))
            manifest_digest = canon.digest_obj("evidence-manifest/v1", manifest)
            self.assertFalse(
                evidence.verify(str(out), manifest_digest),
                "a matching out-of-bounds object must not make verify pass")


class TestEvidencePathEndToEnd(unittest.TestCase):
    """The headline: a real Stage 2 run with two violations of one assertion
    must seal a bundle that `--verify-run` accepts. Before the fix it could not."""

    def _two_violation_run(self, td):
        # Two file subjects, both declaring "widget"; approved is "gadget" ->
        # identity_consistency emits TWO findings, one per subject, one assertion.
        assertion = fx.assertion(
            subjects=[{"kind": "file", "path": "a.md"},
                      {"kind": "file", "path": "b.md"}])
        req, out = fx.build_root(
            Path(td) / "f", approved_name="gadget", stage=2, assertions=[assertion],
            subject_files={"a.md": "# product: widget\n",
                           "b.md": "# product: widget\n"})
        r = subprocess.run(
            [sys.executable, "-m", "hub.coherence", "--request", str(req)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
            env={**os.environ, **fx.cli_env()})
        res = json.loads((out / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(res["decision"], "FAIL",
                         "two identity mismatches must be a FAIL")
        # A sealed FAIL run exits 20 and still produces a verifiable bundle —
        # the check-run consumer verifies the decision, it does not re-run it.
        self.assertEqual(r.returncode, 20, r.stderr)
        findings = list((out / "evidence" / "findings").glob("*.json"))
        self.assertEqual(len(findings), 2,
                         "two violations of one assertion seal two objects")
        # coh-ev-02 integration: the CLI threaded the assertion's declared
        # retention_days (fx.assertion defaults to 365) into every object's
        # class — proving the derivation is exercised by a real run, not just
        # the unit test's synthetic dict.
        m = json.loads((out / "evidence-manifest.json").read_text(encoding="utf-8"))
        classes = {obj["retention_class"] for obj in m["objects"]}
        self.assertEqual(classes, {"retention:365d"},
                         "CLI must thread the declared retention_days to the manifest")
        return out

    def test_two_violation_run_passes_verify_run(self):
        with tempfile.TemporaryDirectory() as td:
            out = self._two_violation_run(td)
            ss = fx.signer_set("a" * 64, key_id="signer-1",
                               identity="pilot-signer", as_of=fx.FIXED_TIME)
            ssp = Path(td) / "signer-set.json"
            ssp.write_text(json.dumps(ss), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "-m", "hub.coherence",
                 "--verify-run", str(out), "--signer-set", str(ssp)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO))
            self.assertEqual(r.returncode, 0,
                             f"verify-run must accept the bundle: {r.stderr}")


if __name__ == "__main__":
    unittest.main()
