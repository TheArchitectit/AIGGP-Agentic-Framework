"""Exercise the protected committed-range scanner with synthetic transition decisions."""

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_corruption as gate
import corruption_reviews as cr


def stamp(offset):
    return (datetime.now(timezone.utc) + timedelta(hours=offset)).isoformat().replace("+00:00", "Z")


class CommitReviews(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "subject"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.before = "alpha bravo charlie delta echo foxtrot golf"
        self.after = "qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt"
        self.path = "example.txt"
        (self.root / self.path).write_text(self.before + "\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD")
        (self.root / self.path).write_text(self.after + "\n")
        self.git("commit", "-qam", "replacement")
        self.head = self.git("rev-parse", "HEAD")
        self.oid_range = self.base + ".." + self.head
        old = self.git("rev-parse", self.base + ":" + self.path)
        new = self.git("rev-parse", self.head + ":" + self.path)
        self.subject = "github:github.com:1234"
        self.grant = {
            "exception_id": "synthetic-001",
            "subject_ref": self.subject,
            "assertion_id": cr.ASSERTION,
            "subject_path": self.path,
            "finding_fingerprint": {
                "assertion_id": cr.ASSERTION,
                "assertion_version": 1,
                "subject_location": self.path,
                "violation_key": f"substitution-flip:{old}:{new}:1",
            },
            "owner": "lab-fixture",
            "reason": "reviewed synthetic edit",
            "approving_authority": "test-controller",
            "created_at": stamp(-1),
            "expires_at": stamp(1),
            "enforcement_treatment": cr.TREATMENT,
            "remediation_ref": "fixture-123",
        }
        self.binding_path = cr.RUN_BINDINGS / (
            hashlib.sha256(os.fsencode(str(self.root))).hexdigest() + ".json"
        )
        self.documents = {}
        self.provision([self.grant])

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def provision(self, grants):
        catalog = json.dumps({"api_version": cr.CATALOG_TYPE, "exceptions": grants}).encode()
        binding = {
            "api_version": cr.BINDING_TYPE,
            "checkout": str(self.root),
            "subject_ref": self.subject,
            "base": self.base,
            "head": self.head,
            "issued_at": stamp(-1),
            "expires_at": stamp(1),
            "catalog_sha256": hashlib.sha256(catalog).hexdigest(),
        }
        self.documents[cr.CATALOG] = catalog
        self.documents[self.binding_path] = json.dumps(binding).encode()

    def scan(self, *args, reviewed=True):
        argv = ["gate", "--repo", str(self.root), "--range", self.oid_range, *args]
        if reviewed:
            argv.append("--reviewed-transitions")
        out = io.StringIO()

        # Only the protected OS read is substituted. Git, parsing, fingerprints, gate
        # policy and the ordinary CLI entry point all execute on real synthetic commits.
        def load(path):
            try:
                return self.documents[path]
            except KeyError:
                raise FileNotFoundError("missing synthetic controller input") from None

        with (
            patch.object(cr, "read_protected", side_effect=load),
            patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            code = gate.main()
        return code, out.getvalue()

    # spec: scan-corruption-reviewed-default-01
    def test_exact_transition_is_reported_without_clearing_the_finding(self):
        self.assertEqual(self.scan(reviewed=False)[0], 1)
        code, output = self.scan()
        self.assertEqual(code, 0, output)
        self.assertIn("VIOLATED EXCEPTION-ADVISORY example.txt:1", output)
        self.assertIn(self.grant["exception_id"], output)
        self.assertNotIn("diff scan clean", output)

    # spec: scan-corruption-reviewed-exact-01
    def test_wrong_repository_path_line_or_ordered_blob_stays_blocking(self):
        import copy

        for case in ("subject", "path", "line", "before", "after", "reverse"):
            with self.subTest(case=case):
                record = copy.deepcopy(self.grant)
                fp = record["finding_fingerprint"]
                kind, before, after, line = fp["violation_key"].split(":")
                if case == "subject":
                    record["subject_ref"] = "github:github.com:999"
                if case == "path":
                    record["subject_path"] = fp["subject_location"] = "another.txt"
                if case == "line":
                    line = "2"
                if case == "before":
                    before = "b" * 40
                if case == "after":
                    after = "a" * 40
                if case == "reverse":
                    before, after = after, before
                fp["violation_key"] = ":".join((kind, before, after, line))
                self.provision([record])
                self.assertEqual(self.scan()[0], 1)

    def test_distinct_git_paths_with_the_same_blobs_are_separate_findings(self):
        neighbor = self.path + " "
        for path in (self.path, neighbor):
            (self.root / path).write_text(self.before + "\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base with two filenames")
        self.base = self.git("rev-parse", "HEAD")
        for path in (self.path, neighbor):
            (self.root / path).write_text(self.after + "\n")
        self.git("commit", "-qam", "update both files")
        self.head = self.git("rev-parse", "HEAD")
        self.oid_range = self.base + ".." + self.head
        self.provision([self.grant])
        code, output = self.scan()
        self.assertEqual(code, 1, output)
        self.assertEqual(output.count("VIOLATED EXCEPTION-ADVISORY"), 1)
        self.assertIn(neighbor + ":1: substitution flip", output)

    def test_full_tree_content_check_remains_independent(self):
        # A reviewed committed range and the separate working-tree content scan.
        self.assertEqual(self.scan()[0], 0)
        (self.root / self.path).write_text("synthetic " + chr(0xFFFD) + " example\n")
        out = io.StringIO()
        with (
            patch.object(sys, "argv", ["gate", "--repo", str(self.root), "--no-baseline"]),
            contextlib.redirect_stdout(out),
        ):
            self.assertEqual(gate.main(), 1, out.getvalue())
        self.assertNotIn("EXCEPTION-ADVISORY", out.getvalue())

    def test_new_change_to_same_file_requires_another_review(self):
        (self.root / self.path).write_text(self.after.replace("qwerty", "ytrewq") + "\n")
        self.git("commit", "-qam", "another edit")
        self.head = self.git("rev-parse", "HEAD")
        self.oid_range = self.base + ".." + self.head
        self.provision([self.grant])
        self.assertEqual(self.scan(reviewed=False)[0], 1, "the new edit must exercise the detector")
        code, output = self.scan()
        self.assertEqual(code, 1, output)
        self.assertNotIn("EXCEPTION-ADVISORY", output)

    # spec: scan-corruption-reviewed-visible-01
    def test_approved_finding_does_not_cover_a_second_substitution(self):
        p = self.root / self.path
        p.write_text(self.before + "\nunchanged\n" + self.before + "\n")
        self.git("commit", "-qam", "second fixture base")
        self.base = self.git("rev-parse", "HEAD")
        p.write_text(self.after + "\nunchanged\n" + self.after + "\n")
        self.git("commit", "-qam", "two changes")
        self.head = self.git("rev-parse", "HEAD")
        self.oid_range = self.base + ".." + self.head
        fp = self.grant["finding_fingerprint"]
        fp["violation_key"] = "substitution-flip:{}:{}:1".format(
            self.git("rev-parse", self.base + ":" + self.path),
            self.git("rev-parse", self.head + ":" + self.path),
        )
        self.provision([self.grant])
        code, output = self.scan()
        self.assertEqual(code, 1)
        self.assertIn("EXCEPTION-ADVISORY example.txt:1", output)
        self.assertIn("example.txt:3: substitution flip", output)

    def test_revocation_expiry_or_stale_policy_cannot_authorize(self):
        self.grant["created_at"] = stamp(-3)
        self.grant["expires_at"] = stamp(-2)
        self.provision([self.grant])
        self.assertEqual(self.scan()[0], 1)
        self.provision([])
        self.assertEqual(self.scan()[0], 1)
        self.documents[cr.CATALOG] += b" "
        self.assertEqual(self.scan()[0], 2)
        del self.documents[self.binding_path]
        self.assertEqual(self.scan()[0], 2)

    # spec: scan-corruption-reviewed-authority-01
    def test_binding_cannot_be_reused_for_another_checkout_or_commit(self):
        binding = json.loads(self.documents[self.binding_path])
        for key, value in (
            ("checkout", "/somewhere/else"),
            ("head", self.base),
            ("base", self.head),
            ("expires_at", stamp(-2)),
        ):
            with self.subTest(key=key):
                self.documents[self.binding_path] = json.dumps(
                    dict(binding, **{key: value})
                ).encode()
                self.assertEqual(self.scan()[0], 2)

    # spec: scan-corruption-reviewed-lifecycle-01
    def test_catalog_change_during_evaluation_is_refused(self):
        with (
            patch.object(cr, "read_protected", side_effect=self.documents.__getitem__),
            cr.open_reviews(self.root, self.base, self.head) as reviews,
        ):
            self.assertEqual(reviews.match(self.path, 1), self.grant["exception_id"])
            self.provision([])
            with self.assertRaises(cr.ReviewError):
                reviews.check_current()

    def test_protected_file_loader_rejects_writable_ancestors(self):
        path = self.root / "policy.json"
        path.write_text("{}")
        with self.assertRaises(cr.ReviewError):
            cr.read_protected(path)

    def test_subject_path_allowlist_does_not_grant_a_review(self):
        overlay = self.root / ".guardrails" / "corruption-allowlist.json"
        overlay.parent.mkdir()
        overlay.write_text(json.dumps({"entries": [{"path": self.path, "reason": "synthetic"}]}))
        self.assertEqual(self.scan(reviewed=False)[0], 0)
        self.provision([])
        code, output = self.scan()
        self.assertEqual(code, 1, output)
        self.assertNotIn("EXCEPTION-ADVISORY", output)

    def test_use_the_bound_repository_regardless_of_inherited_git_context(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "irrelevant")}):
            code, output = self.scan()
        self.assertEqual(code, 0, output)
        self.assertIn("EXCEPTION-ADVISORY", output)

    def test_reviewed_git_uses_its_own_configuration_and_executable(self):
        self.git("config", "diff.algorithm", "patience")
        self.git("config", "diff.noprefix", "true")
        with patch.dict(os.environ, {"PATH": "/unavailable"}):
            code, output = self.scan()
        self.assertEqual(code, 0, output)
        self.assertIn("EXCEPTION-ADVISORY", output)

    def test_bounded_report_counts_reviewed_substitutions(self):
        out = io.StringIO()
        with (
            patch.object(cr, "read_protected", side_effect=self.documents.__getitem__),
            cr.open_reviews(self.root, self.base, self.head) as reviews,
            contextlib.redirect_stdout(out),
        ):
            self.assertEqual(gate.scan_diff(reviews.diff(), {}, 0, reviews=reviews), 0)
        self.assertNotIn(self.grant["exception_id"], out.getvalue())
        self.assertIn("1 reviewed substitutions total", out.getvalue())

    def test_bulk_mutation_is_blocking_alongside_reviewed_substitution(self):
        for index in range(gate.BULK_MUTATION_FILES):
            (self.root / f"bulk-{index}.md").write_text("First text\n" * 10)
        self.git("add", ".")
        self.git("commit", "-qm", "add synthetic files")
        (self.root / self.path).write_text(self.before + "\n")
        self.git("commit", "-qam", "fixture base")
        self.base = self.git("rev-parse", "HEAD")
        for index in range(gate.BULK_MUTATION_FILES):
            (self.root / f"bulk-{index}.md").write_text("Replacement text\n" * 10)
        (self.root / self.path).write_text(self.after + "\n")
        self.git("commit", "-qam", "full rewrite and reviewed substitution")
        self.head = self.git("rev-parse", "HEAD")
        self.oid_range = self.base + ".." + self.head
        self.provision([self.grant])
        code, output = self.scan()
        self.assertEqual(code, 1, output)
        self.assertIn("BULK MUTATION", output)
        self.assertIn("EXCEPTION-ADVISORY", output)

    def test_reviewed_mode_refuses_staged_and_content_checks(self):
        for args in (
            ["--reviewed-transitions"],
            ["--reviewed-transitions", "--staged"],
            ["--reviewed-transitions", "--range", self.oid_range, "--staged"],
        ):
            with (
                self.subTest(args=args),
                patch.object(sys, "argv", ["gate", "--repo", str(self.root), *args]),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as raised:
                    gate.main()
                self.assertEqual(raised.exception.code, 2)

    def test_malformed_or_duplicated_review_is_not_used(self):
        self.provision([self.grant, self.grant])
        self.assertEqual(self.scan()[0], 2)
        self.grant["finding_fingerprint"]["assertion_version"] = True
        self.provision([self.grant])
        self.assertEqual(self.scan()[0], 2)


if __name__ == "__main__":
    unittest.main()
