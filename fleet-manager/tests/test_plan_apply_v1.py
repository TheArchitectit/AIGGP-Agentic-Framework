# spec: fleet-002-01, fleet-002-02, fleet-002-03, fleet-002-04
"""Plan, apply, idempotency, audit and authorization (FLEET-002, Sprint 2.2).

The shape of this suite follows the failure each rule exists to prevent:

- a plan that changes between two reviewers, or a plan edited after review;
- an apply that lands on a revision nobody planned against;
- a retry that becomes a second deploy;
- an audit log with a hole in it, or one that can be back-dated;
- a destructive change applied by a principal that may only read.

Runs from the boundary package alone (REPO-005): no network, no clock, no core
test tree. Every timestamp is a literal.
"""
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager import documents  # noqa: E402
from fleet_manager.apply import (  # noqa: E402
    ApplyError,
    ApplyRefused,
    IdempotencyLedger,
    apply_plan,
)
from fleet_manager.audit import AuditError, AuditEvent, AuditLog, Outcome  # noqa: E402
from fleet_manager.auth import AuthorizationError, Principal, PrincipalKind, Scope  # noqa: E402
from fleet_manager.model import DesiredState, ModelError  # noqa: E402
from fleet_manager.plan import (  # noqa: E402
    Change,
    ChangeKind,
    Plan,
    PlanError,
    build_plan,
    plan_id_for,
)

# This suite keeps its own floor; see the note in test_model_v1.py.
EXPECTED_TEST_COUNT = 44

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
        "schema": documents.DOCUMENT_SCHEMA,
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


def _assign(state: DesiredState, assignment_id: str = "a-1") -> DesiredState:
    return state.with_assignment(
        assignment_id=assignment_id,
        request_id="req-1",
        pool_id="phase1-linux",
        host_id="ucs03",
        at=AT,
    )


def _assign_change(assignment_id: str = "a-1") -> Change:
    return Change(
        kind=ChangeKind.ASSIGN,
        subject=assignment_id,
        parameters=(
            ("assignment_id", assignment_id),
            ("request_id", "req-1"),
            ("pool_id", "phase1-linux"),
            ("host_id", "ucs03"),
        ),
    )


def _release_change(assignment_id: str = "a-1") -> Change:
    return Change(kind=ChangeKind.RELEASE, subject=assignment_id)


def _drain_change(host_id: str = "ucs03") -> Change:
    return Change(
        kind=ChangeKind.DRAIN,
        subject=host_id,
        parameters=(("reason", "kernel upgrade"),),
    )


def _rollout_change(pool_id: str = "phase1-linux") -> Change:
    return Change(
        kind=ChangeKind.ROLLOUT,
        subject=pool_id,
        parameters=(("rollout_id", "r-1"), ("to_image_digest", DIGEST_B)),
    )


def _principal(principal_id: str, *scopes: Scope) -> Principal:
    return Principal(
        principal_id=principal_id,
        kind=PrincipalKind.OPERATOR,
        scopes=frozenset(scopes),
    )


READER = _principal("operator-read", Scope.FLEET_READ)
PLANNER = _principal("operator-plan", Scope.FLEET_PLAN)
APPLIER = _principal("operator-apply", Scope.FLEET_APPLY)
ADMIN = _principal("operator-admin", Scope.FLEET_ADMIN)


def _apply(state, plan, principal=APPLIER, at=AT, key="deploy-1", **kwargs):
    return apply_plan(
        state=state,
        plan=plan,
        principal=principal,
        at=at,
        idempotency_key=key,
        **kwargs,
    )


class TestAPlanIsDeterministicAndComplete(unittest.TestCase):
    """fleet-002-01 — the plan, and only the plan, says what an apply will do."""

    def test_the_same_base_and_changes_produce_the_same_plan_id(self):
        first = build_plan(_state(), [_assign_change()])
        second = build_plan(_state(), [_assign_change()])
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertEqual(first.document(), second.document())

    def test_a_different_base_revision_produces_a_different_plan_id(self):
        at_one = build_plan(_state(), [_assign_change("a-9")])
        at_two = build_plan(_assign(_state()), [_assign_change("a-9")])
        self.assertNotEqual(at_one.plan_id, at_two.plan_id)

    def test_a_plan_whose_id_no_longer_matches_its_changes_is_refused(self):
        changes = (_assign_change(),)
        with self.assertRaises(PlanError) as caught:
            Plan(
                plan_id="plan:" + "0" * 32,
                base_revision=1,
                changes=changes,
                impacts=(),
                resulting_revision=2,
            )
        self.assertIn("plan_id", str(caught.exception))

    def test_the_plan_names_the_revision_it_would_produce(self):
        plan = build_plan(_state(), [_assign_change("a-1"), _assign_change("a-2")])
        self.assertEqual(plan.base_revision, 1)
        self.assertEqual(plan.resulting_revision, 3)
        self.assertEqual(plan.document()["resulting_revision"], 3)

    def test_an_empty_plan_is_refused(self):
        with self.assertRaises(PlanError) as caught:
            build_plan(_state(), [])
        self.assertIn("at least one change", str(caught.exception))

    def test_the_capacity_impact_is_computed_from_the_simulation(self):
        plan = build_plan(_state(), [_assign_change()])
        self.assertEqual(len(plan.impacts), 1)
        impact = plan.impacts[0]
        self.assertEqual((impact.host_id, impact.before_free, impact.after_free), ("ucs03", 2, 1))
        self.assertEqual(impact.delta, -1)

    def test_a_plan_that_frees_a_slot_reports_it(self):
        state = _assign(_state())
        plan = build_plan(state, [_release_change()])
        self.assertEqual(plan.impacts[0].before_free, 1)
        self.assertEqual(plan.impacts[0].after_free, 2)
        self.assertEqual(plan.impacts[0].delta, 1)

    def test_an_impossible_change_is_refused_at_plan_time_with_its_index(self):
        state = _assign(_state())  # one of two slots free
        with self.assertRaises(PlanError) as caught:
            build_plan(state, [_assign_change("a-2"), _assign_change("a-3")])
        message = str(caught.exception)
        self.assertIn("change 1 (assign)", message)
        self.assertIn("at capacity", message)

    def test_destructive_is_a_property_of_the_change_kind(self):
        expected = {
            ChangeKind.ASSIGN: False,
            ChangeKind.RELEASE: True,
            ChangeKind.DRAIN: True,
            ChangeKind.COMPLETE_DRAIN: True,
            ChangeKind.RETURN_TO_SERVICE: False,
            ChangeKind.ROLLOUT: True,
        }
        for kind, destructive in expected.items():
            self.assertEqual(Change(kind=kind, subject="subject").destructive, destructive, kind.value)

    def test_a_plan_is_destructive_when_any_change_is(self):
        self.assertFalse(build_plan(_state(), [_assign_change()]).destructive)
        state = _assign(_state())
        self.assertTrue(build_plan(state, [_assign_change("a-2"), _release_change()]).destructive)

    def test_the_plan_document_carries_the_changes_in_order_and_the_impact(self):
        plan = build_plan(_state(), [_assign_change("a-1"), _assign_change("a-2")])
        document = plan.document()
        self.assertEqual(document["schema"], "fleet-manager-plan/1")
        self.assertEqual([change["subject"] for change in document["changes"]], ["a-1", "a-2"])
        self.assertEqual(document["capacity_impact"][0]["after_free"], 0)
        self.assertFalse(document["destructive"])

    def test_planning_does_not_touch_the_state_it_reads(self):
        state = _state()
        snapshot = documents.to_document(state)
        build_plan(state, [_assign_change(), _drain_change()])
        self.assertEqual(documents.to_document(state), snapshot)
        self.assertEqual(state.revision, 1)


class TestAnApplyIsBoundToItsRevision(unittest.TestCase):
    """fleet-002-02 — reviewed against one revision, applied to that revision."""

    def test_apply_produces_the_planned_revision(self):
        plan = build_plan(_state(), [_assign_change()])
        result = _apply(_state(), plan)
        self.assertEqual(result.state.revision, 2)
        self.assertEqual(result.state.revision, plan.resulting_revision)
        self.assertFalse(result.replayed)
        self.assertEqual(len(result.state.assignments), 1)

    def test_a_stale_plan_is_refused_naming_both_revisions(self):
        plan = build_plan(_state(), [_assign_change("a-1")])
        moved_on = _assign(_state(), "a-2")
        with self.assertRaises(ApplyRefused) as caught:
            _apply(moved_on, plan)
        message = str(caught.exception)
        self.assertIn("stale plan", message)
        self.assertIn("revision 1", message)
        self.assertIn("revision 2", message)

    def test_apply_requires_the_apply_scope(self):
        plan = build_plan(_state(), [_assign_change()])
        with self.assertRaises(ApplyRefused) as caught:
            _apply(_state(), plan, principal=PLANNER)
        self.assertIn("fleet.apply", str(caught.exception))

    def test_a_destructive_plan_requires_admin(self):
        state = _assign(_state())
        plan = build_plan(state, [_release_change()])
        with self.assertRaises(ApplyRefused) as caught:
            _apply(state, plan, principal=APPLIER)
        self.assertIn("fleet.admin", str(caught.exception))

    def test_a_reader_cannot_apply(self):
        plan = build_plan(_state(), [_assign_change()])
        with self.assertRaises(ApplyRefused) as caught:
            _apply(_state(), plan, principal=READER)
        self.assertIn("fleet.apply", str(caught.exception))

    def test_an_admin_may_apply_a_destructive_plan(self):
        state = _assign(_state())
        plan = build_plan(state, [_release_change()])
        result = _apply(state, plan, principal=ADMIN)
        self.assertEqual(result.state.revision, 3)
        self.assertEqual(result.state.assignments[0].released_at, AT)

    def test_apply_emits_one_audit_event_per_change_in_order(self):
        plan = build_plan(_state(), [_assign_change("a-1"), _assign_change("a-2")])
        result = _apply(_state(), plan)
        events = result.audit_log.events
        self.assertEqual([event.seq for event in events], [1, 2])
        self.assertEqual([event.action for event in events], ["assign", "assign"])
        self.assertEqual([event.subject for event in events], ["a-1", "a-2"])
        self.assertTrue(all(event.outcome is Outcome.APPLIED for event in events))
        self.assertTrue(all(event.plan_id == plan.plan_id for event in events))
        self.assertTrue(all(event.actor is APPLIER for event in events))
        self.assertTrue(all(event.at == AT for event in events))

    def test_apply_leaves_the_log_it_was_given_unchanged(self):
        seed = AuditLog().append(
            at=AT,
            actor=READER,
            action="plan",
            subject="read-only",
            outcome=Outcome.APPLIED,
        )
        plan = build_plan(_state(), [_assign_change()])
        result = _apply(_state(), plan, audit_log=seed)
        self.assertEqual(seed.head_seq, 1)
        self.assertEqual(result.audit_log.head_seq, 2)
        self.assertEqual(result.audit_log.events[0], seed.events[0])

    def test_apply_revalidates_a_plan_against_the_real_state(self):
        state = _assign(_assign(_state(), "a-1"), "a-2")  # saturated
        impossible = (_assign_change("a-3"),)
        # A hand-built plan at the right revision: self-consistent, but the
        # change it names cannot happen. Apply is the authority, not the plan.
        plan = Plan(
            plan_id=plan_id_for(state.revision, impossible),
            base_revision=state.revision,
            changes=impossible,
            impacts=(),
            resulting_revision=state.revision + 1,
        )
        with self.assertRaises(ApplyRefused) as caught:
            _apply(state, plan)
        self.assertIn("change 0 (assign) is not possible", str(caught.exception))

    def test_a_failure_mid_plan_is_a_refusal_and_the_log_says_so(self):
        # Two changes, the second a duplicate of the first: the plan is
        # self-consistent, the apply cannot finish, and nothing is half-applied.
        changes = (_assign_change("a-1"), _assign_change("a-1"))
        state = _state()
        plan = Plan(
            plan_id=plan_id_for(state.revision, changes),
            base_revision=state.revision,
            changes=changes,
            impacts=(),
            resulting_revision=state.revision + 2,
        )
        with self.assertRaises(ApplyRefused) as caught:
            _apply(state, plan)
        refusal = caught.exception
        self.assertIn("change 1 (assign)", str(refusal))
        self.assertIs(refusal.event.outcome, Outcome.REFUSED)
        self.assertEqual(refusal.audit_log.head_seq, 1)

    def test_a_bad_timestamp_is_refused_before_any_change(self):
        plan = build_plan(_state(), [_assign_change()])
        with self.assertRaises(ApplyError) as caught:
            _apply(_state(), plan, at="yesterday")
        self.assertNotIsInstance(caught.exception, ApplyRefused)
        self.assertIn("ISO-8601", str(caught.exception))

    def test_a_malformed_idempotency_key_is_refused(self):
        plan = build_plan(_state(), [_assign_change()])
        for key in ("", "has space", "x" * 200, "-leading-dash"):
            with self.assertRaises(ApplyError) as caught:
                _apply(_state(), plan, key=key)
            self.assertIn("idempotency_key", str(caught.exception))


class TestAnIdempotencyKeyMakesRetrySafe(unittest.TestCase):
    """fleet-002-03 — a retry is the same work, or it is refused."""

    def test_a_replay_returns_the_recorded_result_and_changes_nothing(self):
        plan = build_plan(_state(), [_assign_change()])
        first = _apply(_state(), plan)
        replay = _apply(_state(), plan, ledger=first.ledger)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.state.revision, 1, "a replay must not apply again")
        self.assertEqual(replay.resulting_revision, first.resulting_revision)
        self.assertEqual(replay.ledger.entries, first.ledger.entries)
        self.assertIs(replay.audit_log.events[-1].outcome, Outcome.REPLAYED)

    def test_a_replay_after_the_state_moved_on_is_still_a_replay(self):
        plan = build_plan(_state(), [_assign_change()])
        first = _apply(_state(), plan)
        # The plan is now stale, but the key is not: the work already happened.
        replay = _apply(first.state, plan, ledger=first.ledger)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.resulting_revision, 2)

    def test_a_key_cannot_be_reused_for_a_different_plan(self):
        plan_one = build_plan(_state(), [_assign_change("a-1")])
        plan_two = build_plan(_state(), [_assign_change("a-2")])
        self.assertNotEqual(plan_one.plan_id, plan_two.plan_id)
        first = _apply(_state(), plan_one)
        with self.assertRaises(ApplyRefused) as caught:
            _apply(_state(), plan_two, ledger=first.ledger)
        message = str(caught.exception)
        self.assertIn("already used for plan", message)
        self.assertIn(plan_one.plan_id, message)

    def test_a_second_key_for_the_same_plan_is_a_stale_apply(self):
        plan = build_plan(_state(), [_assign_change()])
        first = _apply(_state(), plan, key="deploy-1")
        with self.assertRaises(ApplyRefused) as caught:
            _apply(first.state, plan, key="deploy-2")
        self.assertIn("stale plan", str(caught.exception))

    def test_the_ledger_records_the_key_the_plan_and_the_revision(self):
        plan = build_plan(_state(), [_assign_change()])
        result = _apply(_state(), plan)
        self.assertEqual(result.ledger.entries, (("deploy-1", plan.plan_id, 2),))

    def test_the_ledger_is_append_only(self):
        plan = build_plan(_state(), [_assign_change()])
        result = _apply(_state(), plan)
        with self.assertRaises(ApplyError) as caught:
            result.ledger.with_applied(
                idempotency_key="deploy-1",
                plan_id=plan.plan_id,
                resulting_revision=99,
            )
        self.assertIn("never rewritten", str(caught.exception))

    def test_a_ledger_cannot_hold_the_same_key_twice(self):
        with self.assertRaises(ApplyError) as caught:
            IdempotencyLedger(
                entries=(
                    ("deploy-1", "plan:" + "a" * 32, 2),
                    ("deploy-1", "plan:" + "b" * 32, 3),
                )
            )
        self.assertIn("appears twice", str(caught.exception))


class TestTheAuditLogIsAppendOnly(unittest.TestCase):
    """fleet-002-04 — a log with a hole in it is not evidence."""

    def test_append_returns_a_new_log_with_a_contiguous_sequence(self):
        empty = AuditLog()
        one = empty.append(
            at=AT, actor=APPLIER, action="apply", subject="s", outcome=Outcome.APPLIED
        )
        two = one.append(
            at=LATER, actor=APPLIER, action="apply", subject="s", outcome=Outcome.REFUSED
        )
        self.assertEqual(empty.head_seq, 0)
        self.assertEqual(one.head_seq, 1)
        self.assertEqual([event.seq for event in two.events], [1, 2])

    def test_a_gap_in_the_sequence_is_refused(self):
        event = AuditEvent(
            seq=2, at=AT, actor=APPLIER, action="apply", subject="s", outcome=Outcome.APPLIED
        )
        with self.assertRaises(AuditError) as caught:
            AuditLog(events=(event,))
        self.assertIn("contiguous", str(caught.exception))

    def test_a_log_that_runs_backwards_is_refused(self):
        earlier = AuditEvent(
            seq=1, at=LATER, actor=APPLIER, action="apply", subject="s", outcome=Outcome.APPLIED
        )
        later = AuditEvent(
            seq=2, at=AT, actor=APPLIER, action="apply", subject="s", outcome=Outcome.APPLIED
        )
        with self.assertRaises(AuditError) as caught:
            AuditLog(events=(earlier, later))
        self.assertIn("does not run backwards", str(caught.exception))

    def test_a_non_principal_actor_is_refused(self):
        with self.assertRaises(AuditError) as caught:
            AuditEvent(
                seq=1, at=AT, actor="ucs03", action="apply", subject="s", outcome=Outcome.APPLIED
            )
        self.assertIn("must be a Principal", str(caught.exception))

    def test_an_event_document_names_the_actor_and_the_plan(self):
        plan = build_plan(_state(), [_assign_change()])
        result = _apply(_state(), plan)
        document = result.audit_log.events[0].document()
        self.assertEqual(document["actor"], {"kind": "operator", "id": "operator-apply"})
        self.assertEqual(document["plan_id"], plan.plan_id)
        self.assertEqual(document["outcome"], "applied")
        self.assertEqual(document["idempotency_key"], "deploy-1")

    def test_for_plan_filters_without_reordering(self):
        plan = build_plan(_state(), [_assign_change()])
        result = _apply(_state(), plan)
        self.assertEqual(result.audit_log.for_plan(plan.plan_id), result.audit_log.events)
        self.assertEqual(result.audit_log.for_plan("plan:" + "0" * 32), ())

    def test_a_reason_that_looks_like_a_credential_is_refused_without_echoing(self):
        shaped = "ghp_" + "a" * 36
        with self.assertRaises(AuditError) as caught:
            AuditEvent(
                seq=1,
                at=AT,
                actor=APPLIER,
                action="apply",
                subject="s",
                outcome=Outcome.REFUSED,
                reason=f"failed with {shaped}",
            )
        self.assertIn("secret value", str(caught.exception))
        self.assertNotIn(shaped, str(caught.exception))

    def test_an_action_that_is_not_a_lowercase_token_is_refused(self):
        for action in ("Assign", "assign!", ""):
            with self.assertRaises(AuditError):
                AuditEvent(
                    seq=1, at=AT, actor=APPLIER, action=action, subject="s", outcome=Outcome.APPLIED
                )


class TestAuthorizationIsADecision(unittest.TestCase):
    """fleet-002-02 — one ladder, and it is written down."""

    def test_the_scope_ladder(self):
        self.assertTrue(ADMIN.holds(Scope.FLEET_APPLY))
        self.assertTrue(ADMIN.holds(Scope.FLEET_READ))
        self.assertTrue(APPLIER.holds(Scope.FLEET_PLAN))
        self.assertFalse(APPLIER.holds(Scope.FLEET_ADMIN))
        self.assertTrue(PLANNER.holds(Scope.FLEET_READ))
        self.assertFalse(PLANNER.holds(Scope.FLEET_APPLY))
        self.assertFalse(READER.holds(Scope.FLEET_PLAN))

    def test_a_scope_string_is_not_a_scope(self):
        with self.assertRaises(AuthorizationError) as caught:
            Principal(
                principal_id="operator-x",
                kind=PrincipalKind.OPERATOR,
                scopes=frozenset({"fleet.apply"}),
            )
        self.assertIn("not a Scope", str(caught.exception))

    def test_a_principal_id_must_be_a_request_id(self):
        with self.assertRaises(AuthorizationError) as caught:
            Principal(principal_id="", kind=PrincipalKind.SYSTEM)
        self.assertIn("principal_id", str(caught.exception))

    def test_a_refusal_names_the_scope_and_the_held_scopes(self):
        with self.assertRaises(AuthorizationError) as caught:
            READER.require(Scope.FLEET_APPLY)
        message = str(caught.exception)
        self.assertIn("fleet.apply", message)
        self.assertIn("fleet.read", message)


class TestSuiteFloor(unittest.TestCase):
    def test_the_suite_still_has_its_expected_tests(self):
        # Count this module, not the directory: a floor that counts its
        # neighbours cannot tell whether this file lost tests.
        discovered = unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]
        )
        count = discovered.countTestCases()
        self.assertGreaterEqual(
            count, EXPECTED_TEST_COUNT, f"suite shrank: {count} < {EXPECTED_TEST_COUNT}"
        )
