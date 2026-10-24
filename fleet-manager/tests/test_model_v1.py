# spec: fleet-001-01, fleet-001-02, fleet-001-03, fleet-001-04, fleet-001-05
"""The desired-state model refuses impossible fleets (FLEET-001, Sprint 2.1).

Every test here is one of the change spec's scenarios. The shape is deliberate:
build a valid document, mutate one thing, and assert that the refusal names the
field and — where a value could be sensitive — does not repeat the value.

Runs from the boundary package alone (REPO-005): no core test tree, no network,
no clock. Timestamps are literals.
"""
import ast
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager import documents  # noqa: E402
from fleet_manager import observation  # noqa: E402
from fleet_manager.documents import DOCUMENT_SCHEMA  # noqa: E402
from fleet_manager.model import DesiredState, ModelError  # noqa: E402

# This suite keeps its own floor: the open-core tests/expected-counts.json is
# generated from tests/ and this package must survive extraction (REPO-005).
EXPECTED_TEST_COUNT = 34

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
AT = "2026-10-24T06:00:00+00:00"
LATER = "2026-10-24T06:05:00+00:00"


def _pool_doc(**overrides) -> dict:
    doc = {
        "pool_id": "phase1-linux",
        "revision": 1,
        "trust_class": "public",
        "allowed_repositories": ["TheArchitectit/AIGGP-Agentic-Framework"],
        "runner_group": None,
        "required_labels": {"pool": "phase1"},
        "runtime": "podman",
        "image_digest": DIGEST_A,
        "architectures": ["x86_64"],
        "ephemeral": True,
        "warm_min": 1,
        "warm_max": 2,
        "scale_ceiling": 4,
        "idle_timeout_seconds": 300,
        "job_timeout_seconds": 3600,
        "cleanup_timeout_seconds": 120,
        "network_profile": "egress-proxy",
        "filesystem_profile": "ephemeral-root",
        "secret_profile": "phase1-job-secrets",
        "update_channel": "stable",
        "rollback_image_digest": DIGEST_B,
        "maintenance_window": "sun 02:00-04:00",
        "disruption_budget": {"max_parallel": 1},
        "owner": "platform",
        "escalation": "oncall-fleet",
    }
    doc.update(overrides)
    return doc


def _host_doc(**overrides) -> dict:
    doc = {
        "host_id": "ucs03",
        "architectures": ["x86_64"],
        "runtimes": ["podman", "docker"],
        "labels": {"host": "ucs03"},
        "allowed_pools": ["phase1-linux"],
        "slots": 2,
        "state": "active",
    }
    doc.update(overrides)
    return doc


def _state_doc(**overrides) -> dict:
    doc = {
        "schema": DOCUMENT_SCHEMA,
        "revision": 1,
        "repositories": [],
        "pools": [_pool_doc()],
        "hosts": [_host_doc()],
        "assignments": [],
        "drains": [],
        "rollouts": [],
    }
    doc.update(overrides)
    return doc


def _state(**overrides) -> DesiredState:
    return documents.from_document(_state_doc(**overrides))


def _assign(state: DesiredState, assignment_id: str = "a-1", **overrides) -> DesiredState:
    kwargs = {"assignment_id": assignment_id, "request_id": "req-1", "pool_id": "phase1-linux", "host_id": "ucs03", "at": AT}
    kwargs.update(overrides)
    return state.with_assignment(**kwargs)


class TestDesiredStateIsTheManagersAlone(unittest.TestCase):
    """fleet-001-01 — immutable, revisioned, and not fed by observations."""

    def test_a_transition_returns_a_new_revision_and_leaves_the_input(self):
        state = _state()
        after = _assign(state)
        self.assertEqual(state.revision, 1)
        self.assertEqual(after.revision, 2)
        self.assertEqual(state.assignments, (), "the input must not gain the assignment")
        self.assertEqual(len(after.assignments), 1)

    def test_the_original_value_survives_every_transition(self):
        state = _assign(_state())
        snapshot = documents.to_document(state)
        _assign(state, "a-2")
        state.with_drain(host_id="ucs03", reason="kernel upgrade", at=AT)
        self.assertEqual(documents.to_document(state), snapshot)

    def test_an_observation_cannot_be_desired_state(self):
        report = observation.Observation(host_id="ucs03", observed_at=AT)
        # An Observation has a host_id, so "it has the field" is not evidence.
        with self.assertRaises(ModelError) as caught:
            DesiredState(revision=1, hosts=(report,))
        self.assertIn("must be a Host", str(caught.exception))
        self.assertIn("Observation", str(caught.exception))

    def test_the_two_modules_do_not_import_each_other(self):
        def imported_names(path: Path) -> set:
            names: set = set()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    names.add(node.module or "")
                    names.update(alias.name for alias in node.names)
            return names

        package = PKG_ROOT / "fleet_manager"
        self.assertFalse(
            [name for name in imported_names(package / "model.py") if "observation" in name],
            "model.py must not import the observation module",
        )
        self.assertFalse(
            [name for name in imported_names(package / "observation.py") if "model" in name],
            "observation.py must not import the model module",
        )


class TestPoolDeclaresItsContract(unittest.TestCase):
    """fleet-001-02 — a pool declares everything, or the refusal names the gap."""

    def test_a_missing_required_field_is_named_and_only_that_one(self):
        doc = _pool_doc()
        del doc["image_digest"]
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(doc)
        message = str(caught.exception)
        self.assertIn("missing required field(s): image_digest", message)
        self.assertNotIn("cleanup_timeout_seconds", message)

    def test_an_unknown_field_is_refused(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(surprise="extra"))
        self.assertIn("unknown field(s): surprise", str(caught.exception))

    def test_a_persistent_pool_is_refused_in_phase_1(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(ephemeral=False))
        self.assertIn("const true", str(caught.exception))

    def test_warm_bounds_must_be_ordered(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(warm_min=5, warm_max=2))
        self.assertIn("warm_min <= warm_max <= scale_ceiling", str(caught.exception))

    def test_pool_scope_is_exactly_one_of_repositories_or_group(self):
        both = _pool_doc(runner_group="phase1")
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(both)
        self.assertIn("exactly one of", str(caught.exception))
        neither = _pool_doc(allowed_repositories=[])
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(neither)
        self.assertIn("exactly one of", str(caught.exception))

    def test_the_rollback_image_must_differ_from_the_current_one(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(rollback_image_digest=DIGEST_A))
        self.assertIn("must differ", str(caught.exception))

    def test_an_unpinned_image_is_refused(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(image_digest="ghcr.io/x:latest"))
        self.assertIn("cannot be pinned", str(caught.exception))

    def test_the_update_channel_is_closed(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(update_channel="nightly"))
        self.assertIn("must be one of", str(caught.exception))


class TestSecretsAreReferencedNeverCarried(unittest.TestCase):
    """fleet-001-03 — and a refusal never repeats the value."""

    SECRET_VALUE = "not-a-real-token-but-shaped-like-one-0123456789"

    def test_a_value_shaped_key_is_refused_by_name_without_echoing(self):
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(registration_token=self.SECRET_VALUE))
        message = str(caught.exception)
        self.assertIn("registration_token", message)
        self.assertIn("secret-shaped", message)
        self.assertNotIn(self.SECRET_VALUE, message)

    def test_a_nested_secret_key_is_refused_by_path(self):
        doc = _state_doc()
        doc["hosts"][0]["password"] = self.SECRET_VALUE
        with self.assertRaises(ModelError) as caught:
            documents.from_document(doc)
        message = str(caught.exception)
        self.assertIn("desired_state.hosts[0].password", message)
        self.assertNotIn(self.SECRET_VALUE, message)

    def test_the_secret_profile_must_be_a_reference_not_a_blob(self):
        blob = "job-secrets-" * 8  # long enough that it cannot be an identifier
        with self.assertRaises(ModelError) as caught:
            documents.pool_from_document(_pool_doc(secret_profile=blob))
        message = str(caught.exception)
        self.assertIn("secret_profile", message)
        self.assertNotIn(blob, message)

    def test_the_reference_field_itself_is_allowed(self):
        pool = documents.pool_from_document(_pool_doc())
        self.assertEqual(pool.secret_profile, "phase1-job-secrets")


class TestHostEligibility(unittest.TestCase):
    """fleet-001-04 — runtime, architecture, allow-list and state must agree."""

    def test_an_architecture_mismatch_is_named(self):
        state = _state(pools=[_pool_doc(architectures=["arm64"])])
        with self.assertRaises(ModelError) as caught:
            _assign(state)
        self.assertIn("architectures do not intersect", str(caught.exception))

    def test_a_runtime_mismatch_is_named(self):
        state = _state(hosts=[_host_doc(runtimes=["docker"])], pools=[_pool_doc(runtime="podman")])
        with self.assertRaises(ModelError) as caught:
            _assign(state)
        self.assertIn("does not offer runtime podman", str(caught.exception))

    def test_a_pool_off_the_allow_list_is_named(self):
        state = _state(pools=[_pool_doc(pool_id="phase9")])
        with self.assertRaises(ModelError) as caught:
            _assign(state, pool_id="phase9")
        self.assertIn("allow-list", str(caught.exception))

    def test_a_draining_host_refuses_new_work(self):
        state = _state(hosts=[_host_doc(state="draining")])
        with self.assertRaises(ModelError) as caught:
            _assign(state)
        self.assertIn("host is draining", str(caught.exception))

    def test_an_eligible_host_accepts_the_assignment(self):
        state = _assign(_state())
        self.assertEqual(state.assignments[0].host_id, "ucs03")
        self.assertEqual(state.capacity("ucs03").free, 1)


class TestCapacityDrainAndRollout(unittest.TestCase):
    """fleet-001-05 — impossible states are refused, arithmetic lives here."""

    def test_over_capacity_is_refused_and_names_free_slots(self):
        state = _assign(_assign(_state(), "a-1"), "a-2")
        with self.assertRaises(ModelError) as caught:
            _assign(state, "a-3")
        message = str(caught.exception)
        self.assertIn("at capacity", message)
        self.assertIn("free 0", message)

    def test_release_frees_the_slot_and_cannot_happen_twice(self):
        state = _assign(_assign(_state(), "a-1"), "a-2")
        released = state.with_release(assignment_id="a-1", at=LATER)
        self.assertEqual(released.capacity("ucs03").free, 1)
        self.assertEqual(state.capacity("ucs03").free, 0, "release must not mutate its input")
        self.assertEqual(len(_assign(released, "a-3").assignments), 3)
        with self.assertRaises(ModelError) as caught:
            released.with_release(assignment_id="a-1", at=LATER)
        self.assertIn("already released", str(caught.exception))

    def test_completing_a_drain_with_work_in_flight_is_refused(self):
        state = _assign(_state()).with_drain(host_id="ucs03", reason="kernel upgrade", at=AT)
        with self.assertRaises(ModelError) as caught:
            state.with_drain_complete(host_id="ucs03", at=LATER)
        self.assertIn("1 assignment(s) still on the host", str(caught.exception))

    def test_drain_then_complete_then_return(self):
        state = _assign(_state()).with_release(assignment_id="a-1", at=LATER)
        drained = state.with_drain(host_id="ucs03", reason="kernel upgrade", at=LATER)
        self.assertEqual(drained.host("ucs03").state.value, "draining")
        complete = drained.with_drain_complete(host_id="ucs03", at=LATER)
        self.assertEqual(complete.host("ucs03").state.value, "drained")
        self.assertEqual(complete.drains[-1].state.value, "drained")
        back = complete.with_host_returned(host_id="ucs03", at=LATER)
        self.assertEqual(back.host("ucs03").state.value, "active")
        self.assertEqual(back.drains[-1].state.value, "ended")

    def test_a_drain_cannot_start_twice(self):
        state = _state().with_drain(host_id="ucs03", reason="kernel upgrade", at=AT)
        with self.assertRaises(ModelError) as caught:
            state.with_drain(host_id="ucs03", reason="again", at=LATER)
        self.assertIn("host is draining", str(caught.exception))

    def test_a_rollout_to_the_current_image_is_refused(self):
        with self.assertRaises(ModelError) as caught:
            _state().with_rollout(rollout_id="r-1", pool_id="phase1-linux", to_image_digest=DIGEST_A, at=AT)
        self.assertIn("already runs that image", str(caught.exception))

    def test_a_rollout_moves_the_image_bumps_the_pool_and_keeps_the_rollback(self):
        state = _state().with_rollout(rollout_id="r-1", pool_id="phase1-linux", to_image_digest=DIGEST_B, at=AT)
        pool = state.pool("phase1-linux")
        self.assertEqual(pool.image_digest, DIGEST_B)
        self.assertEqual(pool.rollback_image_digest, DIGEST_A)
        self.assertEqual(pool.revision, 2)
        self.assertEqual(state.rollouts[0].from_image_digest, DIGEST_A)

    def test_a_rollout_to_an_unpinned_digest_is_refused(self):
        with self.assertRaises(ModelError) as caught:
            _state().with_rollout(rollout_id="r-1", pool_id="phase1-linux", to_image_digest="runner:next", at=AT)
        self.assertIn("cannot be pinned", str(caught.exception))


class TestDocuments(unittest.TestCase):
    """fleet-001-02 — the store's wire form is closed and round-trips exactly."""

    def test_the_document_round_trips_byte_identical(self):
        doc = _state_doc()
        self.assertEqual(documents.to_document(documents.from_document(doc)), doc)

    def test_an_unknown_top_level_field_is_refused(self):
        doc = _state_doc()
        doc["schema_extra"] = True
        with self.assertRaises(ModelError) as caught:
            documents.from_document(doc)
        self.assertIn("unknown field(s): schema_extra", str(caught.exception))

    def test_the_wrong_schema_is_refused(self):
        doc = _state_doc()
        doc["schema"] = "fleet-manager-desired-state/2"
        with self.assertRaises(ModelError) as caught:
            documents.from_document(doc)
        self.assertIn("schema", str(caught.exception))

    def test_a_dangling_reference_is_refused(self):
        doc = _state_doc()
        doc["assignments"] = [
            {
                "assignment_id": "a-1",
                "request_id": "req-1",
                "pool_id": "phase1-linux",
                "host_id": "ghost",
                "issued_at": AT,
                "released_at": None,
            }
        ]
        with self.assertRaises(ModelError) as caught:
            documents.from_document(doc)
        self.assertIn("unknown host ghost", str(caught.exception))


class TestSuiteFloor(unittest.TestCase):
    def test_the_suite_still_has_its_expected_tests(self):
        discovered = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
        count = discovered.countTestCases()
        self.assertGreaterEqual(
            count, EXPECTED_TEST_COUNT, f"suite shrank: {count} < {EXPECTED_TEST_COUNT}"
        )
