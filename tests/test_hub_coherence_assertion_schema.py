# // spec: coh-eval-02, coh-assert-01, coh-rt-06
"""C1 — planning-time enforcement of the frozen `assertion.schema.json`
(design.md:71 "assertion schema completeness", coh-assert-01/04).

Assertions come from repository-declared package content, which design.md's
"Repository boundary" marks untrusted. Before this slice, `plan.py` checked
only a hand-rolled subset of the schema — the ten required field *names* and
that `requirement_refs` was truthy — while the schema's shape rules (id
grammar, subjects selector keys, severity enum, finding_key vocabulary,
`additionalProperties: false`, the nested `evidence.retention_days`) were
never enforced at planning. That left the hostile-id defense split: sealing
(`evidence.py`) had to invent its own regex because `assertion.schema.json`
was not a runtime contract. The `assertion.schema.json` file *does* pin every
one of those rules, so the right place to load it is the one gate that every
plan() call passes through — not a per-module ad-hoc copy.

Dual-runnable (see __main__ below). All fixtures synthetic (R9)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import plan, result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent


def _good() -> dict:
    """A minimal assertion that satisfies every rule in
    assertion.schema.json, so any rejection in these tests is caused by the
    mutation named in the test, not by an unrelated shape error in the
    fixture."""
    return {
        "id": "a1", "version": 1, "requirement_refs": ["r1"], "owner": "o",
        "requirement": "r", "subjects": [{"kind": "file", "path": "x"}],
        "evaluator": {"id": "devgate.builtin.identity-consistency",
                      "digest": "sha256:" + "a" * 64},
        "parameters": {}, "severity": "high", "dependencies": [],
        "finding_key": ["assertion_id", "subject_location", "violation_class"],
        "evidence": {"retention_days": 1},
    }


def _plan(assertion: dict):
    return plan.plan([assertion], [])


class TestSchemaCompleteness(unittest.TestCase):
    """The hand-rolled required-field loop rejected a missing field name but
    not a required field's *shape* — the schema pins more rules than ten
    names."""

    def test_a_schema_valid_assertion_plans(self):
        # Baseline (the positive case that makes every other test here
        # meaningful): the good fixture passes with no schema violation.
        self.assertEqual([a["id"] for a in _plan(_good())], ["a1"])

    def test_a_negative_version_is_rejected(self):
        # Hand-rolled loop only checked that `version` was present; schema
        # pins integer, minimum:1.
        a = _good()
        a["version"] = 0
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_an_unknown_subject_selector_kind_is_rejected(self):
        # subjects[] items are objects with kind enum — the loop skipped
        # nested keys and enums entirely.
        a = _good()
        a["subjects"] = [{"kind": "url", "path": "http://x"}]
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_a_finding_key_member_outside_the_vocabulary_is_rejected(self):
        # finding_key must be an array of three named components; any other
        # string (a hand-typed "author" field) breaks ratchet matching
        # downstream but was accepted by "required field present" checks.
        a = _good()
        a["finding_key"] = ["assertion_id", "author", "violation_class"]
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_an_unexpected_top_level_property_is_rejected(self):
        # additionalProperties:false at the assertion object level. A
        # repository adding "notes": "hi" — plausible convenience — drifts
        # the shape of the sealed result and was silently accepted.
        a = _good()
        a["notes"] = "just a friendly comment"
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_a_negative_retention_days_is_rejected(self):
        # evidence.retention_days minimum: 0 — negative would produce a
        # nonsensical bundle expiry. Hand-rolled loop checked the "evidence"
        # name only, not the nested shape.
        a = _good()
        a["evidence"] = {"retention_days": -5}
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_an_undersized_requirement_refs_is_rejected(self):
        # Empty array was already rejected, but a null (a JSON file with the
        # field present and set to null) passed the required-field check and
        # the truthiness check, then crashed downstream. Schema pins array
        # type, minItems:1.
        a = _good()
        a["requirement_refs"] = None
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_an_empty_subjects_array_is_rejected(self):
        # minItems: 1 — an assertion that scopes to nothing runs no check.
        a = _good()
        a["subjects"] = []
        with self.assertRaises(plan.PlanError):
            _plan(a)

    def test_an_id_with_a_trailing_newline_is_rejected(self):
        """C1 audit: JSON Schema `pattern` is ECMA-262 — `$` means
        end-of-string only. Python's `$` also matches before a trailing `\\n`,
        so a repository id like "a1\\n" passed `re.search` and planned clean,
        then reached evidence.seal and named a file with a literal newline —
        bytes a strict JSON-Schema consumer rejects against this very schema.
        The gate must be as strong as the contract it enforces."""
        a = _good()
        a["id"] = "a1\n"
        with self.assertRaises(plan.PlanError):
            _plan(a)


class TestEvaluatorAllowlistPreserved(unittest.TestCase):
    """C1 wires the schema check; it does not *replace* the allowlist, which
    is a policy rule rather than a shape rule. A schema-valid evaluator
    reference to an unapproved id must still be rejected by plan() before
    any evaluator runs (coh-rt-06)."""

    def test_a_schema_valid_but_unapproved_evaluator_is_still_rejected(self):
        # Object shape matches; the id is not on the built-in list.
        a = _good()
        a["evaluator"] = {"id": "repo.evil", "digest": "sha256:" + "b" * 64}
        with self.assertRaises(plan.PlanError) as cm:
            _plan(a)
        self.assertIn("unapproved-evaluator:repo.evil", str(cm.exception))

    def test_a_schema_valid_digest_shape_is_accepted(self):
        # The allowlist gate reads the id, not the digest shape — a
        # correctly-shaped digest with an approved id still passes planning.
        a = _good()
        a["evaluator"] = {"id": "devgate.builtin.traceability-completeness",
                          "digest": "sha256:" + "c" * 64}
        self.assertEqual(len(_plan(a)), 1)


class TestErrorEnvelopeShape(unittest.TestCase):
    """Every rejection reports what failed, so a repository author editing a
    spec file learns which field to change instead of a generic 'invalid
    assertion'."""

    def test_a_schema_violation_names_the_path(self):
        # schemacheck reports "$.version"; that prefix is what makes the
        # message actionable.
        a = _good()
        a["version"] = 0
        with self.assertRaises(plan.PlanError) as cm:
            _plan(a)
        msg = str(cm.exception)
        self.assertIn("a1", msg, "the failing assertion id must be in the message")
        self.assertIn("version", msg, "the failing path must be named")

    def test_an_non_dict_assertion_is_reported_not_crashed(self):
        # Repository content is untrusted at the JSON layer too — a specs/
        # file that parses to a bare string reaches plan() unchanged, and
        # the required-fields loop used to AttributeError on .get(). The
        # schema check converts that into a normal PlanError.
        for bad in (["not", "a", "dict"], "just-a-string", 42, None):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(plan.PlanError):
                    plan.plan([bad], [])


class TestCliRejectsAtPlanning(unittest.TestCase):
    """The whole point of moving enforcement here: a hostile or merely
    malformed repository assertion is exit 30 (invalid-input) at planning,
    not exit 33 (evidence) at seal — the graph is never evaluated and no
    evidence is ever sealed against it. Driven through the real CLI."""

    def _cli(self, req, out):
        r = subprocess.run([sys.executable, "-m", "hub.coherence",
                            "--request", str(req)],
                           capture_output=True, text=True, cwd=str(REPO),
                           env={**os.environ, **fx.cli_env()})
        rp = Path(out) / "result.json"
        return r.returncode, json.loads(rp.read_text()) if rp.exists() else None

    def _run(self, assertions, td):
        # build_root computes every digest from the files it writes, so a
        # schema-invalid assertion is fully package-consistent: the only
        # thing that can reject it is the planning check itself.
        req, out = fx.build_root(Path(td), assertions=assertions, stage=2)
        return self._cli(req, out)

    def test_a_traversal_id_never_reaches_sealing(self):
        """The hostile-id vector: a repository specs/*.json whose file name is
        conventional but whose declared assertion id is a path traversal.
        Before C1 this passed planning and was caught only at evidence.seal
        (exit 33) after a full evaluation; the planner must reject it as
        invalid input (exit 30) so no evaluation or sealing ever happens."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=2)
            # Tamper the spec content AFTER build, then recompute the digests
            # the request carries — so the package stays internally
            # consistent and planning is the ONLY thing left to reject it.
            from hub.coherence import canon, package as pkgmod
            spec = Path(td) / "openspec" / "specs" / "product.identity.json"
            doc = json.loads(spec.read_text())
            doc["id"] = "../../../PWNED"
            spec.write_text(json.dumps(doc))
            pman = Path(td) / "openspec" / "package.json"
            pm = json.loads(pman.read_text())
            for e in pm["normative_inventory"]:
                fp = Path(td) / "openspec" / e["path"]
                e["digest"] = fx.digest_bytes(fp.read_bytes())
            pman.write_text(json.dumps(pm))
            fresh = pkgmod.resolve(str(Path(td) / "openspec"))["package_digest"]
            r = json.loads(req.read_text())
            r["openspec"]["expected_digest"] = fresh
            req.write_text(json.dumps(r))
            code, res = self._cli(req, out)
            self.assertEqual(code, result.EXIT_INVALID_INPUT,
                             "schema-invalid id is invalid-input (30), not evidence (33)")
            self.assertEqual(res["error"]["class"], "invalid-input")
            self.assertIn("assertion.schema.json", res["error"]["reason"])
            # And the run sealed nothing — planning failed before evaluation.
            self.assertEqual(list(Path(out).glob("**/evidence*")), [])

    def test_a_valid_package_still_passes_the_planner(self):
        # The positive CLI case: the standard fixture (which fx.assertion()
        # builds to be schema-complete) is not newly rejected.
        with tempfile.TemporaryDirectory() as td:
            code, res = self._run([fx.assertion()], td)
            self.assertNotEqual(code, result.EXIT_INVALID_INPUT)


if __name__ == "__main__":
    unittest.main()
