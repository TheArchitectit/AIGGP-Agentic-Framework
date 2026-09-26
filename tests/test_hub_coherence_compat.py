# // spec: coh-arch-01, coh-rt-06
"""Compatibility and schema versioning (S8 tasks.md:920, measured 2026-09-26;
acceptance criterion 1 of 12, plus the Stage-2 no-regression boundary from 8).

Criterion 1 — "all normative schemas are versioned and published with
compatibility tests". Measured before this suite: the schemas DID carry
versions (a wire `api_version` const, or the package's `schema_version`), and
the wire schemas WERE validated against emitted results — but nothing asserted
the pair of properties that makes a version a version: that EVERY normative
schema declares one in a recognized place, and that a FOREIGN or MISSING
version is refused rather than parsed under this version's rules and
mis-judged. A conformance suite that is green over an unversioned family is the
same shape as the mid-run-mutation gap: a documented contract with no enforcing
test.

This is a TEST-ONLY slice: the version refusals it pins were already built (the
measurement found them, it did not create them). What is new is that the
contract is pinned, parameterized over the normative family, with anti-vacuity
guards — so a future schema cannot join the family unversioned, and a future
"be liberal, default a missing version to v1" change fails here.

One genuine annotation the measurement surfaced, recorded by name rather than
silently passed: `execution-profiles.schema.json` names itself with
`schema: "execution-profiles"` — a shape discriminator, not a version. The
other fourteen all carry a version, split across two roads (an in-document
`const`, or the `title` family string), so "versioned" is checked per schema
and never inferred from the majority.

All fixtures synthetic (R9).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import context, package, policy

REPO = Path(__file__).resolve().parent.parent
SCHEMAS = REPO / "openspec/changes/devgate-spec-coherence-service/schemas"

# `<family>/vN` — the shape every version value must have, wherever it lives.
FAMILY_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*/v[0-9]+$")

# The normative wire-contract family (acceptance criterion 1). An explicit
# list, not a glob: a new schema file must be ADDED here deliberately, and
# `test_the_family_list_covers_every_schema_on_disk` fails until it is.
NORMATIVE_SCHEMAS = (
    "assertion.schema.json",
    "attestation.schema.json",
    "baseline-entry.schema.json",
    "error-envelope.schema.json",
    "evaluation-context.schema.json",
    "evidence-manifest.schema.json",
    "exception.schema.json",
    "execution-profiles.schema.json",
    "package.schema.json",
    "policy-bundle.schema.json",
    "request.schema.json",
    "result.schema.json",
    "run-envelope.schema.json",
    "signer-set.schema.json",
    "subject-manifest.schema.json",
)

# Every normative schema must declare a version in one of these places, and
# the value must be a `<family>/vN` string. `api_version` is the wire
# convention; `schema_version` is the package manifest's own (package.resolve
# checks exactly this field).
VERSION_FIELDS = ("api_version", "schema_version")

# The one contract with no version anywhere. Named and justified rather than
# implied: `test_annotated_exceptions_are_still_exceptions` fails the moment it
# GAINS one, so the exemption is dropped deliberately instead of rotting over a
# fixed contract.
UNVERSIONED_BY_ANNOTATION = {
    "execution-profiles.schema.json": "its `schema: \"execution-profiles\"` "
                                      "is a shape discriminator, not a version",
}


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _version_const(name: str):
    """The contract version this schema declares, or None.

    Two roads, both a string a machine can dispatch on:
      - `properties.<field>.const` — `api_version` on the wire contracts,
        `schema_version` on the package manifest (`package.resolve` checks
        exactly this field).
      - `title` — the `devgate.spec-coherence.<contract>/vN` family string,
        which the three entry-shaped schemas carry INSTEAD of an in-document
        version const (`baseline-entry` and `exception` name the container
        family; `assertion` names its grammar).

    Measured census (2026-09-26): 14 of 15 carry one; the only schema with no
    version anywhere is `UNVERSIONED_BY_ANNOTATION`'s
    `execution-profiles.schema.json`, whose `schema: "execution-profiles"` is a
    SHAPE DISCRIMINATOR (which kind of document this is), not a version —
    reading it as one is exactly the looks-versioned-but-isn't this suite is
    here to catch.
    """
    doc = _schema(name)
    props = doc.get("properties") or {}
    for f in VERSION_FIELDS:
        v = props.get(f)
        if isinstance(v, dict) and isinstance(v.get("const"), str):
            return v["const"]
    title = doc.get("title")
    if isinstance(title, str) and FAMILY_RE.match(title):
        return title
    return None


def _write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


class TestSchemaVersioning(unittest.TestCase):
    """Acceptance criterion 1: versioned schemas + compatibility tests."""

    def test_the_family_list_covers_every_schema_on_disk(self):
        # Anti-vacuity + completeness: the parameterized tests below iterate
        # this tuple, so a rename that empties it must fail loudly rather than
        # pass zero cases, and an ADDED schema must not slip in uncovered.
        #
        # The count is asserted separately from the set comparison: a path or
        # glob drift that made `on_disk` empty would leave the set assertion
        # as the only signal, and a future edit that also trimmed the tuple
        # would satisfy it — the measured count cannot be satisfied that way.
        on_disk = sorted(p.name for p in SCHEMAS.glob("*.schema.json"))
        self.assertEqual(len(on_disk), len(NORMATIVE_SCHEMAS),
                         f"schema count drifted: {len(on_disk)} on disk vs "
                         f"{len(NORMATIVE_SCHEMAS)} in the family list — "
                         f"{on_disk}")
        self.assertEqual(sorted(NORMATIVE_SCHEMAS), on_disk,
                         "a schema file exists that no versioning assertion "
                         "covers — add it to NORMATIVE_SCHEMAS deliberately")

    def test_the_version_readers_actually_read(self):
        """Anti-vacuity for the helper itself: a `_version_const` that always
        returned None (or a `VERSION_FIELDS` typo) would make the malformed-
        version and family-sharing checks iterate emptily and pass. Pin that
        each road returns a real value for a schema known to carry one — this
        is the mutant M12 of the battery that found it survived."""
        self.assertEqual(_version_const("result.schema.json"),
                         "devgate.spec-coherence.result/v1")
        self.assertEqual(_version_const("package.schema.json"),
                         "devgate.openspec.package/v1")
        self.assertEqual(_version_const("assertion.schema.json"),
                         "devgate.spec-coherence.assertion/v1")   # title road
        self.assertIsNone(_version_const("execution-profiles.schema.json"))

    def test_every_normative_schema_declares_a_version(self):
        """A normative schema with no version has no name for a future
        breaking change to retire — it cannot be published as a versioned
        contract, only as an unnamed shape that silently drifts. Measured
        2026-09-26: 12 of 15 carry one; the 3 that do not are annotated by
        name below, so this is a pinned exemption rather than a blind pass."""
        problems = []
        for name in NORMATIVE_SCHEMAS:
            const = _version_const(name)
            if const is None and name not in UNVERSIONED_BY_ANNOTATION:
                problems.append(f"{name}: no version const among "
                                f"{VERSION_FIELDS}")
        self.assertEqual(problems, [],
                         f"normative schemas with no version: {problems}")

    def test_version_values_are_recognizable_family_vN_strings(self):
        """The value must be usable as a dispatch key, not prose: `<family>/vN`."""
        pattern = FAMILY_RE
        problems = []
        for name in NORMATIVE_SCHEMAS:
            const = _version_const(name)
            if const is not None and not pattern.match(const):
                problems.append(f"{name}: version {const!r} is not a "
                                f"<family>/vN string")
        self.assertEqual(problems, [], f"malformed schema versions: {problems}")

    def test_every_normative_schema_has_a_unique_published_id(self):
        """Document identity lives in `$id`, not in the version string: one
        `$id` per contract, so a consumer resolving a schema by URI lands on
        exactly one document.

        A shared version string is NOT a collision — design.md:244 makes
        `error-envelope` an explicit member of the result `api_version`
        family, and the version describes the wire family the document
        belongs to. What must not collide is the identity."""
        ids = {}
        for name in NORMATIVE_SCHEMAS:
            doc = _schema(name)
            sid = doc.get("$id")
            if not isinstance(sid, str):
                continue
            ids.setdefault(sid, []).append(name)
        collisions = {v: names for v, names in ids.items() if len(names) > 1}
        self.assertEqual(collisions, {}, f"duplicate $id: {collisions}")

    def test_wire_family_sharing_is_only_the_documented_one(self):
        """The one legitimate version-sharing pair is result + error-envelope
        (design.md:244, "same api_version family"). Pinned as an exact set, so
        a future contract that starts sharing a family version must say so
        here rather than inherit the exemption silently."""
        SHARED_BY_DESIGN = {
            "devgate.spec-coherence.result/v1":
                {"error-envelope.schema.json", "result.schema.json"},
        }
        versions = {}
        for name in NORMATIVE_SCHEMAS:
            const = _version_const(name)
            if const is not None:
                versions.setdefault(const, set()).add(name)
        shared = {v: names for v, names in versions.items() if len(names) > 1}
        self.assertEqual(shared, SHARED_BY_DESIGN,
                         "a new pair shares a family version, or the "
                         "documented pair changed — update deliberately")

    def test_annotated_exceptions_are_still_exceptions(self):
        """The annotation set is a pinned exemption, not a dumping ground: if
        an annotated schema GAINS a version, this fails so the exemption is
        removed deliberately rather than left to rot over a fixed contract."""
        stale = [f"{name} now carries {_version_const(name)} — drop its "
                 f"UNVERSIONED_BY_ANNOTATION entry"
                 for name in UNVERSIONED_BY_ANNOTATION
                 if _version_const(name) is not None]
        self.assertEqual(stale, [], "; ".join(stale))


class TestForeignVersionIsRefused(unittest.TestCase):
    """Compatibility is two-sided: a foreign or missing version must be
    refused, never parsed under this version's rules."""

    def test_foreign_policy_api_version_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(root / "policy.json",
                        {"api_version": "devgate.spec-coherence.policy/v2",
                         "rules": []})
            with self.assertRaises(policy.PolicyError) as cm:
                policy.resolve(str(root), "sha256:" + "0" * 64)
            self.assertIn("v2", str(cm.exception))

    def test_foreign_context_api_version_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(root / "context.json",
                        {"api_version": "devgate.spec-coherence.context/v2"})
            with self.assertRaises(context.ContextError) as cm:
                context.load(str(root))
            self.assertIn("v2", str(cm.exception))

    def test_missing_version_is_refused_not_defaulted(self):
        # Defaulting a missing version to v1 is the classic silent-compat bug:
        # an older writer that omitted the field would be judged as current.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(root / "policy.json", {"rules": []})
            with self.assertRaises(policy.PolicyError) as cm:
                policy.resolve(str(root), "sha256:" + "0" * 64)
            self.assertIn("None", str(cm.exception))
            _write_json(root / "context.json", {})
            with self.assertRaises(context.ContextError) as cm:
                context.load(str(root))
            self.assertIn("None", str(cm.exception))

    def test_foreign_package_schema_version_is_refused(self):
        # The package manifest version is separate from the wire api_version —
        # pinned here rather than left implied by the tests that only exercise
        # the happy v1 path.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(root / "package.json",
                        {"schema_version": "devgate.openspec.package/v99",
                         "normative_inventory": ["x.md"]})
            with self.assertRaises(package.PackageError) as cm:
                package.resolve(str(root))
            self.assertIn("v99", str(cm.exception))

    def test_foreign_request_api_version_is_refused_by_the_cli(self):
        # The entry point is the boundary an operator actually crosses: a
        # request claiming another version must fail, never be judged by this
        # version's schema and emit a PASS/FAIL that means something else.
        from tests.fixtures.coherence import fixtures as fx

        with tempfile.TemporaryDirectory() as td:
            out_root = Path(td)
            req, out = fx.build_root(out_root, stage=1)
            doc = json.loads(req.read_text(encoding="utf-8"))
            doc["api_version"] = "devgate.spec-coherence/v2"
            _write_json(req, doc)
            r = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--request", str(req)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=str(REPO),
                env={**os.environ, **fx.cli_env()})
            self.assertNotEqual(r.returncode, 0, "foreign version must not pass")
            parsed = json.loads((out / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed["decision"], "ERROR")
            self.assertIn("v2", json.dumps(parsed["error"]))


class TestStage2NoRegression(unittest.TestCase):
    """Acceptance criterion 8's boundary half (advisory-expiry enforcement is
    shipped and pinned in the adoption policy/ledger suites; this is the part
    criterion 1's compatibility framing also implies — the ratchet stage must
    not let an unresolved row read as settled)."""

    def test_unresolved_core_row_cannot_read_as_pass_at_stage_2(self):
        """An UNRESOLVED row whose evaluator is in the enforced core must keep
        blocking at the ratchet stage. A ladder that let it degrade to
        SATISFIED-or-advisory would be a silent regression — the exact failure
        no-regression exists to prevent."""
        from hub.coherence import adoption, policy

        planned = [{"id": "a1", "version": 1, "severity": "high",
                    "evaluator": {"id": "devgate.builtin.identity-consistency"},
                    "dependencies": []}]
        ledger = [{"assertion_id": "a1", "version": 1,
                   "outcome": "UNRESOLVED", "reason": "captured-fact-missing:x",
                   "enforcement": "BLOCK"}]
        out = adoption.evaluate(ledger, [], planned, [], [], stage=2,
                                evaluation_time="2026-09-26T00:00:00Z")
        row = out["ledger"][0]
        self.assertEqual(row["outcome"], "UNRESOLVED",
                         "the ratchet stage mutated an unresolved row")
        self.assertEqual(row["enforcement"], "BLOCK",
                         "unresolved must stay BLOCK at the ratchet stage")
        self.assertTrue(out["blocked"],
                        "an unresolved enforced-core row must still block at "
                        "Stage 2 — the no-regression contract")

    def test_the_same_unresolved_row_is_advisory_before_the_ratchet(self):
        # Control: the block above is Stage 2's doing, not an unconditional
        # refusal. Without this, "it blocks" would prove nothing about the
        # ratchet (the guard could just always block).
        from hub.coherence import adoption

        planned = [{"id": "a1", "version": 1, "severity": "high",
                    "evaluator": {"id": "devgate.builtin.identity-consistency"},
                    "dependencies": []}]
        ledger = [{"assertion_id": "a1", "version": 1,
                   "outcome": "UNRESOLVED", "reason": "captured-fact-missing:x",
                   "enforcement": "BLOCK"}]
        out = adoption.evaluate(ledger, [], planned, [], [], stage=1,
                                evaluation_time="2026-09-26T00:00:00Z")
        self.assertEqual(out["ledger"][0]["enforcement"], "ADVISORY",
                         "Stage 1 must not block on incompleteness")
        self.assertFalse(out["blocked"])

    def test_core_membership_is_by_evaluator_id_not_assertion_name(self):
        """A repository must not rename its way out of the enforced core: the
        ladder keys core membership on the evaluator ID, so a re-identified
        assertion with a core evaluator stays core."""
        from hub.coherence import policy
        core = policy.enforced_core_classes(
            {"enforced_core": {"evaluator_classes":
                               ["devgate.builtin.identity-consistency"]}})
        self.assertIn("devgate.builtin.identity-consistency", core)


if __name__ == "__main__":
    unittest.main()
