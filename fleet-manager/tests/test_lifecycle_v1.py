# spec: fleet-008-01, fleet-008-02, fleet-008-03, fleet-008-04, fleet-008-05
"""The one-job lifecycle (FLEET-008, Sprint 4.2).

Every test is one failure the lifecycle exists to prevent:

- an instance that takes a second job, or a job state that walks back into the
  warm pool;
- a replacement admitted while nobody can say what happened to the resources
  the previous instance owned;
- a cleanup "proof" that is silent about a failed disposal, borrows another
  instance's proof, or reports an interval that runs backwards;
- an instance that is neither proved clean nor quarantined and has quietly
  stopped being counted;
- a failure that arrives as a bare exception, or under a ninth error kind.

The values here are built rather than observed. Nothing in this module runs a
container: the disposal results and timestamps are what a host will report in
the next slice, and these tests exercise the rules that will judge them.
"""
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager.adapters import (  # noqa: E402
    WARM_STATES,
    AdapterContractError,
    AdapterError,
    ErrorKind,
    InstanceState,
    WarmInstance,
    WarmPool,
    classify,
)
from fleet_manager.lifecycle import (  # noqa: E402
    TERMINAL_JOB_STATES,
    AdmissionGate,
    CleanupEvidence,
    Disposal,
    JobLifecycle,
    JobState,
    Quarantine,
    admit_replacement,
    next_states,
)
from fleet_manager.model import DisruptionBudget, Pool, Runtime, TrustClass  # noqa: E402

EXPECTED_TEST_COUNT = 64

DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
STARTED = "2026-10-24T09:00:00+00:00"
FINISHED = "2026-10-24T09:01:00+00:00"


def _pool(**overrides) -> Pool:
    fields = dict(
        pool_id="phase1-linux",
        revision=1,
        trust_class=TrustClass.PUBLIC,
        required_labels=(("pool", "phase1"),),
        runtime=Runtime.PODMAN,
        image_digest=DIGEST,
        architectures=("x86_64",),
        warm_min=1,
        warm_max=2,
        scale_ceiling=3,
        idle_timeout_seconds=300,
        job_timeout_seconds=3600,
        cleanup_timeout_seconds=120,
        network_profile="egress-proxy",
        filesystem_profile="ephemeral-root",
        secret_profile="phase1-job-secrets",
        update_channel="stable",
        rollback_image_digest=OTHER_DIGEST,
        maintenance_window="sun 02:00-04:00",
        disruption_budget=DisruptionBudget(max_parallel=1),
        owner="platform",
        escalation="platform-oncall",
        allowed_repositories=("TheArchitectit/AIGGP-Agentic-Framework",),
    )
    fields.update(overrides)
    return Pool(**fields)


def _evidence(**overrides) -> CleanupEvidence:
    fields = dict(
        instance_id="job-1",
        image_digest=DIGEST,
        volume_disposal=Disposal.DISPOSED,
        network_disposal=Disposal.DISPOSED,
        started_at=STARTED,
        finished_at=FINISHED,
    )
    fields.update(overrides)
    return CleanupEvidence(**fields)


def _quarantine(**overrides) -> Quarantine:
    fields = dict(
        instance_id="job-1",
        failure_kind="cleanup_failure",
        quarantined_at=FINISHED,
    )
    fields.update(overrides)
    return Quarantine(**fields)


def _lifecycle(**overrides) -> JobLifecycle:
    fields = dict(instance_id="job-1", image_digest=DIGEST)
    fields.update(overrides)
    return JobLifecycle(**fields)


def _warm(instance_id: str = "job-1", **overrides) -> WarmInstance:
    fields = dict(
        instance_id=instance_id,
        pool_id="phase1-linux",
        image_digest=DIGEST,
        state=InstanceState.PREPULLED,
    )
    fields.update(overrides)
    return WarmInstance(**fields)


def _destroyed() -> JobLifecycle:
    return _lifecycle().offer("run-7").start().finish(JobState.COMPLETED).destroy()


def _in(state: JobState) -> JobLifecycle:
    """A lifecycle that reached `state` by transitions, never by construction."""

    if state is JobState.PREPULLED:
        return _lifecycle()
    if state is JobState.ASSIGNED:
        return _lifecycle().offer("run-7")
    if state is JobState.RUNNING:
        return _lifecycle().offer("run-7").start()
    if state is JobState.REFUSED:
        return _lifecycle().offer("run-7").refuse()
    if state in TERMINAL_JOB_STATES:
        return _lifecycle().offer("run-7").start().finish(state)
    if state is JobState.DESTROYED:
        return _destroyed()
    if state is JobState.PROVEN_CLEAN:
        return _destroyed().prove(_evidence())
    return _destroyed().quarantine(_quarantine())


class OneJobPerInstanceTests(unittest.TestCase):
    """fleet-008-01."""

    def test_a_fresh_instance_is_prepulled_and_names_no_job(self) -> None:
        lifecycle = _lifecycle()
        self.assertIs(JobState.PREPULLED, lifecycle.state)
        self.assertIsNone(lifecycle.job_id)

    def test_an_offered_job_moves_it_to_assigned(self) -> None:
        lifecycle = _lifecycle().offer("run-7")
        self.assertIs(JobState.ASSIGNED, lifecycle.state)
        self.assertEqual("run-7", lifecycle.job_id)

    def test_a_second_job_is_a_policy_denial_and_changes_nothing(self) -> None:
        for state in (JobState.ASSIGNED, JobState.RUNNING):
            with self.subTest(state=state.value):
                lifecycle = _in(state)
                with self.assertRaises(AdapterError) as caught:
                    lifecycle.offer("run-8")
                self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)
                self.assertIn("one job per instance", str(caught.exception))
                self.assertIs(state, lifecycle.state)
                self.assertEqual("run-7", lifecycle.job_id)

    def test_a_finished_instance_cannot_take_another_job(self) -> None:
        for state in TERMINAL_JOB_STATES:
            with self.subTest(state=state.value):
                with self.assertRaises(AdapterError) as caught:
                    _in(state).offer("run-8")
                self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)

    def test_a_job_identity_that_is_not_an_identifier_is_refused(self) -> None:
        for bad in ("", None, "run 7", 7):
            with self.subTest(value=bad):
                with self.assertRaises(AdapterError) as caught:
                    _lifecycle().offer(bad)
                self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)

    def test_the_terminal_states_are_the_four_the_spec_names(self) -> None:
        self.assertEqual(
            {"completed", "timed_out", "cancelled", "disconnected"},
            {state.value for state in TERMINAL_JOB_STATES},
        )

    def test_a_running_job_reaches_each_terminal_state(self) -> None:
        for outcome in TERMINAL_JOB_STATES:
            with self.subTest(outcome=outcome.value):
                lifecycle = _lifecycle().offer("run-7").start().finish(outcome)
                self.assertIs(outcome, lifecycle.state)
                self.assertIn(lifecycle.state, TERMINAL_JOB_STATES)

    def test_finish_refuses_an_outcome_that_is_not_terminal(self) -> None:
        running = _lifecycle().offer("run-7").start()
        for outcome in (
            JobState.ASSIGNED,
            JobState.DESTROYED,
            JobState.PROVEN_CLEAN,
            "completed",
            None,
        ):
            with self.subTest(outcome=outcome):
                with self.assertRaises(AdapterError) as caught:
                    running.finish(outcome)
                self.assertIs(ErrorKind.UNKNOWN_STATE, caught.exception.kind)

    def test_every_terminal_state_leads_to_destruction(self) -> None:
        for outcome in TERMINAL_JOB_STATES:
            with self.subTest(outcome=outcome.value):
                destroyed = _lifecycle().offer("run-7").start().finish(
                    outcome).destroy()
                self.assertIs(JobState.DESTROYED, destroyed.state)

    def test_there_is_no_transition_back_to_warm(self) -> None:
        for state in TERMINAL_JOB_STATES | {JobState.DESTROYED}:
            with self.subTest(state=state.value):
                lifecycle = _in(state)
                for warm in (JobState.PREPULLED, InstanceState.STOPPED_CLEAN,
                             InstanceState.PREPULLED):
                    with self.subTest(warm=str(warm), state=state.value):
                        with self.assertRaises(AdapterError) as caught:
                            lifecycle.move(warm)
                        self.assertIs(
                            ErrorKind.UNKNOWN_STATE, caught.exception.kind
                        )
                        self.assertIn(state.value, str(caught.exception))
                        self.assertIn(
                            getattr(warm, "value", str(warm)),
                            str(caught.exception),
                        )

    def test_the_two_final_states_have_no_way_out(self) -> None:
        for state in (JobState.PROVEN_CLEAN, JobState.QUARANTINED):
            with self.subTest(state=state.value):
                self.assertEqual(frozenset(), next_states(state))
                lifecycle = _in(state)
                for wanted in JobState:
                    with self.subTest(wanted=wanted.value):
                        with self.assertRaises(AdapterError):
                            lifecycle.move(wanted)

    def test_the_machine_is_closed_and_has_a_row_for_every_state(self) -> None:
        for state in JobState:
            with self.subTest(state=state.value):
                transitions = next_states(state)
                self.assertIsInstance(transitions, frozenset)
                for target in transitions:
                    self.assertIsInstance(target, JobState)
                if state in (JobState.PROVEN_CLEAN, JobState.QUARANTINED):
                    self.assertEqual(frozenset(), transitions)
                else:
                    self.assertTrue(
                        transitions, f"{state.value} is a dead end it should not be"
                    )

    def test_no_terminal_job_state_is_a_warm_instance_state(self) -> None:
        terminal = {state.value for state in TERMINAL_JOB_STATES}
        warm = {state.value for state in WARM_STATES}
        self.assertEqual(set(), terminal & warm)

    def test_a_lifecycle_in_a_job_state_must_name_its_job(self) -> None:
        for state in (JobState.ASSIGNED, JobState.RUNNING, JobState.COMPLETED):
            with self.subTest(state=state.value):
                with self.assertRaises(AdapterError) as caught:
                    _lifecycle(state=state)
                self.assertIs(ErrorKind.UNKNOWN_STATE, caught.exception.kind)
                self.assertIn("job_id", str(caught.exception))

    def test_a_prepulled_lifecycle_cannot_name_a_job(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _lifecycle(job_id="run-7")
        self.assertIn("no job identity", str(caught.exception))

    def test_refused_and_cancelled_both_end_in_destruction(self) -> None:
        refused = _lifecycle().offer("run-7").refuse().destroy()
        self.assertIs(JobState.DESTROYED, refused.state)
        cancelled = _lifecycle().offer("run-7").finish(
            JobState.CANCELLED).destroy()
        self.assertIs(JobState.DESTROYED, cancelled.state)

    def test_a_prepulled_instance_is_destroyed_without_a_job(self) -> None:
        self.assertIs(JobState.DESTROYED, _lifecycle().destroy().state)

    def test_a_transition_out_of_order_is_refused(self) -> None:
        for label, lifecycle, step in (
            ("start before offer", _lifecycle(), lambda value: value.start()),
            ("refuse before offer", _lifecycle(), lambda value: value.refuse()),
            (
                "finish before running",
                _lifecycle().offer("run-7"),
                lambda value: value.finish(JobState.COMPLETED),
            ),
            (
                "destroy twice",
                _lifecycle().destroy(),
                lambda value: value.destroy(),
            ),
        ):
            with self.subTest(step=label):
                with self.assertRaises(AdapterError) as caught:
                    step(lifecycle)
                self.assertIs(ErrorKind.UNKNOWN_STATE, caught.exception.kind)

    def test_next_states_refuses_something_that_is_not_a_job_state(self) -> None:
        for value in ("prepulled", None, InstanceState.PREPULLED):
            with self.subTest(value=value):
                with self.assertRaises(AdapterError) as caught:
                    next_states(value)
                self.assertIs(ErrorKind.UNKNOWN_STATE, caught.exception.kind)


class CleanupEvidenceTests(unittest.TestCase):
    """fleet-008-02, the proof value."""

    def test_the_disposal_set_is_closed(self) -> None:
        self.assertEqual(
            {"disposed", "absent", "failed"}, {item.value for item in Disposal}
        )

    def test_a_proof_carries_the_five_things_run_002_names(self) -> None:
        document = _evidence().document()
        self.assertEqual(
            {
                "instance_id",
                "image_digest",
                "volume_disposal",
                "network_disposal",
                "started_at",
                "finished_at",
            },
            set(document),
        )

    def test_every_field_but_job_identity_is_required(self) -> None:
        for field in (
            "instance_id",
            "image_digest",
            "volume_disposal",
            "network_disposal",
            "started_at",
            "finished_at",
        ):
            with self.subTest(field=field):
                arguments = dict(
                    instance_id="job-1",
                    image_digest=DIGEST,
                    volume_disposal=Disposal.DISPOSED,
                    network_disposal=Disposal.DISPOSED,
                    started_at=STARTED,
                    finished_at=FINISHED,
                )
                del arguments[field]
                with self.assertRaises(AdapterError) as caught:
                    CleanupEvidence(**arguments)
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
                self.assertIn(field, str(caught.exception))
                self.assertIn("required", str(caught.exception))

    def test_a_proof_without_a_job_identity_is_still_a_proof(self) -> None:
        evidence = _evidence()
        self.assertIsNone(evidence.job_id)
        self.assertTrue(evidence.admissible)
        self.assertNotIn("job_id", evidence.document())
        with_job = _evidence(job_id="run-7")
        self.assertEqual("run-7", with_job.document()["job_id"])

    def test_a_failed_disposal_is_recorded_but_is_not_admissible(self) -> None:
        for field in ("volume_disposal", "network_disposal"):
            with self.subTest(field=field):
                evidence = _evidence(**{field: Disposal.FAILED})
                self.assertFalse(evidence.admissible)
                self.assertEqual("failed", evidence.document()[field])

    def test_an_absent_disposal_is_admissible(self) -> None:
        evidence = _evidence(
            volume_disposal=Disposal.ABSENT, network_disposal=Disposal.ABSENT
        )
        self.assertTrue(evidence.admissible)

    def test_a_disposal_that_is_not_a_disposal_is_refused(self) -> None:
        for value in ("disposed", None, True):
            with self.subTest(value=value):
                with self.assertRaises(AdapterError) as caught:
                    _evidence(volume_disposal=value)
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
                self.assertIn("volume_disposal", str(caught.exception))

    def test_a_timestamp_must_carry_an_offset(self) -> None:
        for field in ("started_at", "finished_at"):
            with self.subTest(field=field):
                with self.assertRaises(AdapterError) as caught:
                    _evidence(**{field: "2026-10-24T09:00:00"})
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
                self.assertIn("offset", str(caught.exception))

    def test_a_timestamp_that_is_not_a_timestamp_is_refused(self) -> None:
        for value in ("yesterday", "", 42):
            with self.subTest(value=value):
                with self.assertRaises(AdapterError) as caught:
                    _evidence(started_at=value)
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)

    def test_an_interval_that_runs_backwards_is_refused(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _evidence(started_at=FINISHED, finished_at=STARTED)
        self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
        self.assertIn("backwards", str(caught.exception))

    def test_proving_before_destruction_is_refused(self) -> None:
        for state in (JobState.PREPULLED, JobState.RUNNING,
                      JobState.COMPLETED):
            with self.subTest(state=state.value):
                with self.assertRaises(AdapterError) as caught:
                    _in(state).prove(_evidence())
                self.assertIs(ErrorKind.UNKNOWN_STATE, caught.exception.kind)

    def test_a_proof_for_another_instance_cannot_be_transplanted(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _destroyed().prove(_evidence(instance_id="job-2"))
        self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
        self.assertIn("transplanted", str(caught.exception))

    def test_a_proof_for_another_image_cannot_be_transplanted(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _destroyed().prove(_evidence(image_digest=OTHER_DIGEST))
        self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
        self.assertIn("another image", str(caught.exception))

    def test_an_inadmissible_proof_leaves_the_instance_unproven(self) -> None:
        destroyed = _destroyed()
        with self.assertRaises(AdapterError):
            destroyed.prove(_evidence(network_disposal=Disposal.FAILED))
        self.assertIs(JobState.DESTROYED, destroyed.state)

    def test_an_admissible_proof_marks_the_instance_proven_clean(self) -> None:
        self.assertIs(JobState.PROVEN_CLEAN, _destroyed().prove(_evidence()).state)

    def test_prove_refuses_anything_that_is_not_evidence(self) -> None:
        for value in (None, _evidence().document(), "clean"):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(AdapterError) as caught:
                    _destroyed().prove(value)
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)


class QuarantineTests(unittest.TestCase):
    """fleet-008-03."""

    def test_a_quarantine_names_the_instance_the_failure_and_the_time(self) -> None:
        self.assertEqual(
            {
                "instance_id": "job-1",
                "failure_kind": "cleanup_failure",
                "quarantined_at": FINISHED,
            },
            _quarantine().document(),
        )

    def test_every_quarantine_field_is_required(self) -> None:
        for field in ("instance_id", "failure_kind", "quarantined_at"):
            with self.subTest(field=field):
                arguments = dict(
                    instance_id="job-1",
                    failure_kind="cleanup_failure",
                    quarantined_at=FINISHED,
                )
                del arguments[field]
                with self.assertRaises(AdapterError) as caught:
                    Quarantine(**arguments)
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
                self.assertIn(field, str(caught.exception))
                self.assertIn("required", str(caught.exception))

    def test_a_quarantine_must_name_a_failure(self) -> None:
        for value in ("", 7):
            with self.subTest(value=value):
                with self.assertRaises(AdapterError) as caught:
                    _quarantine(failure_kind=value)
                self.assertIn("failure_kind", str(caught.exception))

    def test_a_quarantine_reason_is_bounded(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _quarantine(failure_kind="x" * 600)
        self.assertIn("exceeds", str(caught.exception))

    def test_a_quarantine_time_must_carry_an_offset(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _quarantine(quarantined_at="2026-10-24T09:01:00")
        self.assertIn("offset", str(caught.exception))

    def test_a_failed_proof_quarantines_rather_than_dropping_the_instance(self) -> None:
        destroyed = _destroyed()
        with self.assertRaises(AdapterError):
            destroyed.prove(_evidence(volume_disposal=Disposal.FAILED))
        quarantined = destroyed.quarantine(_quarantine())
        self.assertIs(JobState.QUARANTINED, quarantined.state)
        self.assertEqual("job-1", quarantined.instance_id)
        self.assertEqual("cleanup_failure", _quarantine().failure_kind)

    def test_a_quarantine_for_another_instance_is_refused(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            _destroyed().quarantine(_quarantine(instance_id="job-2"))
        self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)

    def test_a_quarantine_cannot_be_applied_before_destruction(self) -> None:
        for state in (JobState.PREPULLED, JobState.DISCONNECTED,
                      JobState.COMPLETED):
            with self.subTest(state=state.value):
                with self.assertRaises(AdapterError) as caught:
                    _in(state).quarantine(_quarantine())
                self.assertIs(ErrorKind.UNKNOWN_STATE, caught.exception.kind)

    def test_quarantine_refuses_anything_that_is_not_a_quarantine(self) -> None:
        for value in (None, _quarantine().document(), "quarantined"):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(AdapterError) as caught:
                    _destroyed().quarantine(value)
                self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)

    def test_quarantined_stock_is_not_warm(self) -> None:
        self.assertNotIn(InstanceState.QUARANTINED, WARM_STATES)
        self.assertEqual(
            "quarantined", InstanceState.QUARANTINED.value
        )
        self.assertEqual("quarantined", JobState.QUARANTINED.value)


class AdmissionTests(unittest.TestCase):
    """fleet-008-02, the replacement rule."""

    def test_a_destroyed_instance_shortens_the_pool_until_it_is_accounted_for(
        self,
    ) -> None:
        gate = AdmissionGate().destroyed("job-1")
        self.assertEqual(1, gate.shortfall)
        self.assertFalse(gate.can_admit)
        self.assertEqual((), AdmissionGate().unaccounted)
        self.assertTrue(AdmissionGate().can_admit)

    def test_a_replacement_is_not_admitted_while_the_predecessor_is_unaccounted(
        self,
    ) -> None:
        gate = AdmissionGate().destroyed("job-1")
        with self.assertRaises(AdapterError) as caught:
            admit_replacement(
                gate, WarmPool(pool=_pool()), _warm("job-2"), replacing="job-1"
            )
        self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)
        self.assertIn("job-1", str(caught.exception))
        self.assertIn("neither proven nor quarantined", str(caught.exception))

    def test_a_replacement_is_admitted_once_the_predecessor_is_proved_clean(
        self,
    ) -> None:
        gate = AdmissionGate().destroyed("job-1").prove(_evidence())
        self.assertEqual(0, gate.shortfall)
        pool = admit_replacement(
            gate, WarmPool(pool=_pool()), _warm("job-2"), replacing="job-1"
        )
        self.assertEqual(1, pool.warm_count)

    def test_a_replacement_is_admitted_once_the_predecessor_is_quarantined(
        self,
    ) -> None:
        gate = AdmissionGate().destroyed("job-1").quarantine(_quarantine())
        self.assertEqual(0, gate.shortfall)
        self.assertEqual(1, len(gate.quarantined))
        pool = admit_replacement(
            gate, WarmPool(pool=_pool()), _warm("job-2"), replacing="job-1"
        )
        self.assertEqual(1, pool.warm_count)

    def test_new_capacity_is_not_held_up_by_another_instances_accounting(
        self,
    ) -> None:
        gate = AdmissionGate().destroyed("job-1")
        pool = admit_replacement(gate, WarmPool(pool=_pool()), _warm("job-2"))
        self.assertEqual(1, pool.warm_count)

    def test_the_gate_proves_only_what_it_is_awaiting(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            AdmissionGate().prove(_evidence())
        self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
        self.assertIn("not awaiting", str(caught.exception))

    def test_the_gate_quarantines_only_what_it_is_awaiting(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            AdmissionGate().quarantine(_quarantine())
        self.assertIs(ErrorKind.CLEANUP_FAILURE, caught.exception.kind)
        self.assertIn("not awaiting", str(caught.exception))

    def test_the_gate_refuses_to_record_a_destruction_twice(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            AdmissionGate().destroyed("job-1").destroyed("job-1")
        self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)
        self.assertIn("already unaccounted", str(caught.exception))

    def test_the_gate_refuses_a_duplicate_identity_in_its_own_record(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            AdmissionGate(unaccounted=("job-1", "job-1"))
        self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)
        self.assertIn("twice", str(caught.exception))

    def test_the_gate_refuses_records_that_are_not_records(self) -> None:
        for field, value in (
            ("proven", (_evidence().document(),)),
            ("quarantined", (_quarantine().document(),)),
        ):
            with self.subTest(field=field):
                with self.assertRaises(AdapterError) as caught:
                    AdmissionGate(**{field: value})
                self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)
                self.assertIn(field, str(caught.exception))

    def test_a_pool_at_its_ceiling_is_capacity_exhaustion(self) -> None:
        full = WarmPool(
            pool=_pool(warm_max=1), instances=(_warm("job-2"),)
        )
        with self.assertRaises(AdapterError) as caught:
            admit_replacement(AdmissionGate(), full, _warm("job-3"))
        self.assertIs(ErrorKind.CAPACITY_EXHAUSTION, caught.exception.kind)
        self.assertIn("warm_max", str(caught.exception))

    def test_admitting_something_that_is_not_warm_stock_is_a_desired_state_error(
        self,
    ) -> None:
        with self.assertRaises(AdapterError) as caught:
            admit_replacement(AdmissionGate(), WarmPool(pool=_pool()), "job-2")
        self.assertIs(
            ErrorKind.INVALID_DESIRED_STATE, caught.exception.kind
        )

    def test_admission_requires_a_gate(self) -> None:
        with self.assertRaises(AdapterError) as caught:
            admit_replacement(None, WarmPool(pool=_pool()), _warm("job-2"))
        self.assertIs(ErrorKind.POLICY_DENIAL, caught.exception.kind)


class TypedErrorTests(unittest.TestCase):
    """fleet-008-05: the closed taxonomy, and no bare exception."""

    def test_every_lifecycle_failure_lands_in_a_named_kind(self) -> None:
        running = _in(JobState.RUNNING)
        destroyed = _destroyed()
        full = WarmPool(pool=_pool(warm_max=1), instances=(_warm("job-2"),))
        cases = (
            ("second offer", lambda: running.offer("run-8"),
             ErrorKind.POLICY_DENIAL),
            ("bad job identity", lambda: _lifecycle().offer("run 7"),
             ErrorKind.POLICY_DENIAL),
            ("bad transition", lambda: _lifecycle().move(JobState.COMPLETED),
             ErrorKind.UNKNOWN_STATE),
            ("bad outcome", lambda: running.finish(JobState.ASSIGNED),
             ErrorKind.UNKNOWN_STATE),
            ("proof before destroy",
             lambda: _in(JobState.COMPLETED).prove(_evidence()),
             ErrorKind.UNKNOWN_STATE),
            ("transplanted proof",
             lambda: destroyed.prove(_evidence(instance_id="job-2")),
             ErrorKind.CLEANUP_FAILURE),
            ("incomplete proof", lambda: _evidence(finished_at=None),
             ErrorKind.CLEANUP_FAILURE),
            ("bad disposal", lambda: _evidence(volume_disposal="gone"),
             ErrorKind.CLEANUP_FAILURE),
            ("bad quarantine", lambda: _quarantine(failure_kind=None),
             ErrorKind.CLEANUP_FAILURE),
            ("gate proof unknown",
             lambda: AdmissionGate().prove(_evidence()),
             ErrorKind.CLEANUP_FAILURE),
            ("blocked replacement",
             lambda: admit_replacement(
                 AdmissionGate().destroyed("job-1"), WarmPool(pool=_pool()),
                 _warm("job-2"), replacing="job-1"),
             ErrorKind.POLICY_DENIAL),
            ("pool at ceiling",
             lambda: admit_replacement(AdmissionGate(), full, _warm("job-3")),
             ErrorKind.CAPACITY_EXHAUSTION),
            ("unusable stock",
             lambda: admit_replacement(
                 AdmissionGate(), WarmPool(pool=_pool()), "job-2"),
             ErrorKind.INVALID_DESIRED_STATE),
            ("bad lifecycle identity", lambda: _lifecycle(instance_id="Job 1"),
             ErrorKind.INVALID_DESIRED_STATE),
        )
        for label, step, kind in cases:
            with self.subTest(case=label):
                with self.assertRaises(AdapterError) as caught:
                    step()
                self.assertIs(kind, caught.exception.kind)

    def test_a_lifecycle_call_never_propagates_a_contract_error(self) -> None:
        cases = (
            lambda: _lifecycle(instance_id="Job 1"),
            lambda: _lifecycle(image_digest="latest"),
            lambda: _lifecycle().offer("run 7"),
            lambda: _evidence(instance_id="Job 1"),
            lambda: _evidence(image_digest="latest"),
            lambda: _quarantine(instance_id="Job 1"),
            lambda: AdmissionGate().destroyed("Job 1"),
            lambda: admit_replacement(
                AdmissionGate(), WarmPool(pool=_pool()), _warm("job-2"),
                replacing="Job 1"),
        )
        for index, step in enumerate(cases):
            with self.subTest(case=index):
                try:
                    step()
                except AdapterContractError as exc:  # pragma: no cover
                    self.fail(f"contract error escaped a lifecycle call: {exc}")
                except AdapterError:
                    continue
                self.fail(f"case {index} did not fail at all")

    def test_the_taxonomy_is_still_the_eight_kinds(self) -> None:
        self.assertEqual(8, len(ErrorKind))
        self.assertEqual(
            {
                "invalid_desired_state",
                "unavailable_host",
                "registration_failure",
                "runtime_failure",
                "cleanup_failure",
                "capacity_exhaustion",
                "policy_denial",
                "unknown_state",
            },
            {kind.value for kind in ErrorKind},
        )

    def test_an_unexpected_exception_is_classified_by_type_only(self) -> None:
        failure = ValueError("some message with a value in it")
        classified = classify(failure)
        self.assertIs(ErrorKind.RUNTIME_FAILURE, classified.kind)
        self.assertEqual("ValueError", classified.detail)
        self.assertNotIn("some message", str(classified))

    def test_classify_returns_an_adapter_error_unchanged(self) -> None:
        original = AdapterError(ErrorKind.UNKNOWN_STATE, "lifecycle")
        self.assertIs(original, classify(original))


class TestSuiteFloor(unittest.TestCase):
    def test_this_suite_runs_all_of_its_tests(self) -> None:
        discovered = unittest.defaultTestLoader.loadTestsFromModule(
            sys.modules[__name__]
        )
        self.assertEqual(EXPECTED_TEST_COUNT, discovered.countTestCases())


if __name__ == "__main__":
    unittest.main()
