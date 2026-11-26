# spec: repo-003-01, repo-003-02, repo-004-01, repo-004-02, repo-004-03, repo-004-04
"""The v1 contracts are tested in both directions (REPO-004).

Direction 1 — **core producer, Fleet Manager consumer**: the fixture
``fixtures/core-capacity-request.json`` is what core would emit; the Fleet
Manager consumer must accept it, and must refuse every mutation of it with a
named path instead of a crash.

Direction 2 — **Fleet Manager producer, core consumer**: the Fleet Manager
builders must emit documents that satisfy the core side's declared minimum
(``fixtures/core-consumer-expectations.json``) and the schema itself.

Not tested here, and deliberately: the "previous supported contract version"
leg of REPO-004. v1 is the first version, so there is no previous one; the leg
re-opens when ``contracts/v2/`` exists. A test that pretended to cover it today
would be testing a version that does not exist.

No network, no clock coupling, no core test tree: these run from the boundary
package alone (which is also what the extraction rehearsal in 1.3 needs).
"""
import copy
import json
import re
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))   # hub.coherence.schemacheck (open core)
sys.path.insert(0, str(PKG_ROOT))    # fleet_manager (this package)

from fleet_manager import contracts  # noqa: E402

FIXTURES = PKG_ROOT / "contracts" / "v1" / "fixtures"

# This suite keeps its own floor instead of joining tests/expected-counts.json:
# that file is generated from the open-core tests/ tree, and this package has to
# survive being extracted (REPO-005) with its tests intact. Bump deliberately.
EXPECTED_TEST_COUNT = 24


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _assignment() -> dict:
    return {
        "assignment_id": "as-2026-10-24-0001",
        "pool": "devgate-linux",
        "host": "ucs03",
        "runner_image": "ghcr.io/owner/repo/devgate@sha256:" + "a" * 64,
    }


def _evidence() -> dict:
    return {"digest": "sha256:" + "b" * 64, "location": "docs/qa/receipts/1.json"}


def _refusal(code: str = "capacity") -> dict:
    return {"code": code, "detail": "no warm runner available in the pool"}


def _request() -> dict:
    return contracts.parse("capacity_request",
                           _fixture("core-capacity-request.json"))


def _set(*path, value):
    """Return a mutator that assigns through a path."""
    def mutate(doc):
        node = doc
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value
    return mutate


def _drop(*path):
    """Return a mutator that deletes through a path."""
    def mutate(doc):
        node = doc
        for part in path[:-1]:
            node = node[part]
        del node[path[-1]]
    return mutate


def _missing_paths(doc, dotted_paths):
    """Return the dotted paths that do not resolve in ``doc``."""
    missing = []
    for path in dotted_paths:
        node = doc
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                missing.append(path)
                break
            node = node[part]
    return missing


class TestVersionDispatch(unittest.TestCase):
    def test_v1_is_accepted(self):
        doc = _fixture("core-capacity-request.json")
        self.assertEqual(contracts.check_version(doc), 1)
        self.assertEqual(contracts.parse("capacity_request", doc), doc)

    def test_a_future_major_is_refused_and_named(self):
        doc = _fixture("core-capacity-request.json")
        doc["contract_version"] = 2
        with self.assertRaises(contracts.ContractUnsupportedVersion) as ctx:
            contracts.check_version(doc)
        message = str(ctx.exception)
        self.assertIn("2", message)
        self.assertIn("1", message)

    def test_a_missing_version_is_refused_not_crashed(self):
        doc = _fixture("core-capacity-request.json")
        del doc["contract_version"]
        with self.assertRaises(contracts.ContractUnsupportedVersion) as ctx:
            contracts.check_version(doc)
        self.assertIn("missing contract_version", str(ctx.exception))

    def test_a_string_version_is_not_coerced(self):
        doc = _fixture("core-capacity-request.json")
        doc["contract_version"] = "1"
        with self.assertRaises(contracts.ContractUnsupportedVersion):
            contracts.check_version(doc)

    def test_a_v2_document_is_refused_as_a_version_problem_only(self):
        # Not a pile of shape errors from a schema never meant to describe it.
        doc = _fixture("core-capacity-request.json")
        doc["contract_version"] = 2
        doc["future_only_field"] = {"anything": True}
        errors = contracts.validate("capacity_request", doc)
        self.assertEqual(len(errors), 1)
        self.assertIn("contract_version", errors[0])

    def test_a_non_document_is_refused_not_crashed(self):
        for hostile in (None, "not-a-document", ["a", "list"], 7):
            with self.subTest(hostile=hostile):
                errors = contracts.validate("capacity_request", hostile)
                self.assertTrue(errors)
                self.assertIn("contract_version", errors[0])


class TestCoreProducerAgainstFleetConsumer(unittest.TestCase):
    """Direction 1: the fixture core would emit is acceptable here."""

    def test_the_core_producer_fixture_parses(self):
        doc = _fixture("core-capacity-request.json")
        self.assertEqual(contracts.validate("capacity_request", doc), [])

    def test_the_consumer_keys_off_the_request_id_it_was_given(self):
        request = _request()
        decision = contracts.build_capacity_decision(
            request, "assigned", assignment=_assignment())
        self.assertEqual(decision["request_id"], request["request_id"])

    def test_every_recorded_mutation_is_refused_with_a_named_path(self):
        cases = [
            ("missing request_id", _drop("request_id"), "request_id"),
            ("wrong type for concurrency",
             _set("demand", "concurrency", value="1"), "concurrency"),
            ("empty labels", _set("runner", "labels", value=[]),
             "runner.labels"),
            ("trust class outside the enum",
             _set("runner", "trust_class", value="commercial"),
             "trust_class"),
            ("unparseable timestamp",
             _set("created_at", value="yesterday"), "created_at"),
            ("repository without an owner",
             _set("repository", value="REPO"), "repository"),
            ("persistent runner demand",
             _set("demand", "ephemeral", value=False), "ephemeral"),
            ("nested required field missing",
             _drop("workflow", "event"),
             "missing required property 'event'"),
            ("undeclared top-level field",
             _set("priority", value="high"), "unexpected property 'priority'"),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label):
                doc = copy.deepcopy(_fixture("core-capacity-request.json"))
                mutate(doc)
                with self.assertRaises(contracts.ContractInvalid) as ctx:
                    contracts.parse("capacity_request", doc)
                self.assertIn(expected, str(ctx.exception))
                # And the refusal is typed: no KeyError/TypeError leaked out.
                self.assertIsInstance(ctx.exception, contracts.ContractError)


class TestFleetProducerAgainstCoreConsumer(unittest.TestCase):
    """Direction 2: what this package emits satisfies the core side's needs."""

    def setUp(self):
        self.expectations = _fixture("core-consumer-expectations.json")

    def test_assigned_decision_meets_the_core_minimum(self):
        decision = contracts.build_capacity_decision(
            _request(), "assigned", assignment=_assignment())
        self.assertEqual(_missing_paths(
            decision, self.expectations["decision"]["required_paths"]), [])
        self.assertIn(decision["outcome"],
                      self.expectations["decision"]["allowed_outcomes"])
        self.assertEqual(self.expectations["decision"]
                         ["job_path_requires_outcome"], "assigned")

    def test_every_outcome_builds_and_validates(self):
        request = _request()
        self.assertTrue(contracts.build_capacity_decision(
            request, "assigned", assignment=_assignment()))
        for outcome in ("queued", "refused"):
            with self.subTest(outcome=outcome):
                self.assertTrue(contracts.build_capacity_decision(
                    request, outcome, reason=_refusal()))

    def test_unavailable_is_an_explicit_document_not_an_absence(self):
        decision = contracts.build_capacity_decision(
            _request(), "unavailable",
            reason=_refusal("fleet_unavailable"))
        self.assertEqual(decision["outcome"], "unavailable")
        self.assertEqual(decision["reason"]["code"], "fleet_unavailable")
        self.assertIn(decision["reason"]["code"],
                      self.expectations["decision"]["required_reason_codes"])
        # The core side's rule for an absent decision is "unavailable", so the
        # degradation path and the explicit document mean the same thing.
        self.assertEqual(self.expectations["decision"]
                         ["absent_decision_means"], "unavailable")

    def test_a_grant_and_an_excuse_in_one_document_is_refused(self):
        with self.assertRaises(contracts.ContractInvalid) as ctx:
            contracts.build_capacity_decision(
                _request(), "assigned",
                assignment=_assignment(), reason=_refusal())
        self.assertIn("$.reason: not allowed", str(ctx.exception))

    def test_a_refusal_without_a_reason_is_refused(self):
        with self.assertRaises(contracts.ContractInvalid) as ctx:
            contracts.build_capacity_decision(_request(), "refused")
        self.assertIn("$.reason: required", str(ctx.exception))

    def test_an_assignment_without_the_assigned_outcome_is_refused(self):
        with self.assertRaises(contracts.ContractInvalid) as ctx:
            contracts.build_capacity_decision(
                _request(), "queued", assignment=_assignment(),
                reason=_refusal())
        self.assertIn("$.assignment: not allowed", str(ctx.exception))

    def test_the_producer_refuses_a_request_it_could_not_have_been_given(self):
        bad = copy.deepcopy(_fixture("core-capacity-request.json"))
        bad["demand"]["ephemeral"] = False
        with self.assertRaises(contracts.ContractInvalid):
            contracts.build_capacity_decision(
                bad, "assigned", assignment=_assignment())

    def test_completed_receipt_meets_the_core_minimum(self):
        receipt = contracts.build_receipt(
            receipt_id="rc-2026-10-24-0001",
            subject={"kind": "runner", "id": "ucs03-devgate"},
            operation="enroll",
            outcome="completed",
            actor={"kind": "operator", "id": "owner"},
            evidence=_evidence())
        self.assertEqual(_missing_paths(
            receipt, self.expectations["receipt"]["required_paths"]), [])
        self.assertTrue(self.expectations["receipt"]
                        ["completed_requires_evidence"])

    def test_a_completion_without_evidence_is_not_a_receipt(self):
        with self.assertRaises(contracts.ContractInvalid) as ctx:
            contracts.build_receipt(
                receipt_id="rc-2026-10-24-0002",
                subject={"kind": "runner", "id": "ucs03-devgate"},
                operation="enroll",
                outcome="completed",
                actor={"kind": "operator", "id": "owner"})
        self.assertIn("$.evidence: required", str(ctx.exception))

    def test_a_rejected_receipt_needs_no_evidence(self):
        receipt = contracts.build_receipt(
            receipt_id="rc-2026-10-24-0003",
            subject={"kind": "runner", "id": "ucs03-devgate"},
            operation="enroll",
            outcome="rejected",
            actor={"kind": "system", "id": "fleet-manager"},
            detail="signature verification failed")
        self.assertNotIn("evidence", receipt)

    def test_a_receipt_digest_that_is_not_sha256_is_refused(self):
        with self.assertRaises(contracts.ContractInvalid) as ctx:
            contracts.build_receipt(
                receipt_id="rc-2026-10-24-0004",
                subject={"kind": "runner", "id": "ucs03-devgate"},
                operation="enroll",
                outcome="completed",
                actor={"kind": "operator", "id": "owner"},
                evidence={"digest": "md5:whatever", "location": "x"})
        self.assertIn("digest", str(ctx.exception))


class TestEntitlementIsolation(unittest.TestCase):
    """OD-001: no commercial split in Phase 1 — so a tier is not expressible."""

    FORBIDDEN_KEYS = ("tier", "entitlement", "entitlements", "license",
                      "paid", "plan", "subscription")

    def _walk_keys(self, node, found):
        if isinstance(node, dict):
            for key, value in node.items():
                found.add(key)
                self._walk_keys(value, found)
        elif isinstance(node, list):
            for item in node:
                self._walk_keys(item, found)

    def test_no_v1_schema_declares_a_tier_or_entitlement_field(self):
        keys = set()
        for path in sorted((PKG_ROOT / "contracts" / "v1").glob("*.schema.json")):
            self._walk_keys(json.loads(path.read_text(encoding="utf-8")), keys)
        offending = sorted(keys.intersection(self.FORBIDDEN_KEYS) |
                           {k for k in keys
                            if k.lower() in self.FORBIDDEN_KEYS})
        self.assertEqual(offending, [],
                         "a paid-tier field appeared in a v1 contract: under "
                         "OD-001 the boundary must not be able to express one")

    def test_the_schemas_are_closed_so_an_undeclared_field_cannot_cross(self):
        for kind, name in contracts.SCHEMAS.items():
            with self.subTest(kind):
                schema = json.loads(
                    (PKG_ROOT / "contracts" / "v1" / name).read_text(
                        encoding="utf-8"))
                self.assertIs(schema.get("additionalProperties"), False)


class TestRehearsalDeclaresTheSameBuildInputs(unittest.TestCase):
    """The rehearsal copies exactly what this suite pins as the import surface.

    Two places now say "the package may import these open-core files": the pin
    above, and the extraction rehearsal's build-input list. If they drift, the
    rehearsal would pass by copying a module the package never declared — which
    is the hidden dependency REPO-005 exists to find.
    """

    def test_the_declared_build_inputs_are_the_pinned_import_surface(self):
        sys.path.insert(0, str(PKG_ROOT / "scripts"))
        import extraction_rehearsal  # noqa: E402

        modules = set()
        for rel in extraction_rehearsal.DECLARED_BUILD_INPUTS:
            self.assertTrue((REPO_ROOT / rel).is_file(),
                            f"declared build input {rel} does not exist")
            if rel.endswith(".py"):
                modules.add(rel[:-3].replace("/", "."))
        imported = {m for m in modules if not m.endswith(".__init__")}
        self.assertEqual(imported, TestCoreImportSurfacePinned.ALLOWED)


class TestCoreImportSurfacePinned(unittest.TestCase):
    """Extraction needs a bounded dependency, not a discovered one (REPO-005)."""

    ALLOWED = {"hub.coherence.schemacheck"}

    def test_the_only_core_import_is_the_schema_checker(self):
        imports = set()
        for path in sorted((PKG_ROOT / "fleet_manager").glob("*.py")):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                from_match = re.match(
                    r"from\s+(hub[\w.]*)\s+import\s+(.+)", stripped)
                if from_match:
                    module, names = from_match.groups()
                    for name in names.split(","):
                        name = name.split(" as ")[0].strip()
                        if name:
                            imports.add(f"{module}.{name}")
                elif re.match(r"import\s+hub", stripped):
                    imports.add(stripped.split()[1].split(" as ")[0])
        self.assertEqual(imports, self.ALLOWED,
                         "the package's open-core import surface changed — "
                         "extraction (REPO-005) has to carry exactly this")


if __name__ == "__main__":
    unittest.main()
