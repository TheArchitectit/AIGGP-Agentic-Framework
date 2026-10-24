# spec: fleet-003-01, fleet-003-02, fleet-003-03, fleet-003-04
"""Reconciliation fixtures and bounded convergence (FLEET-003, Sprint 2.3).

The suite is built the same way the earlier ones are: from the failure each
rule prevents. Here that is

- a reconciliation that differs between two runs of the same fixtures;
- a reconciler that fixes everything at once and turns one incident into a fleet;
- a reconciler that completes a drain over a runner it never observed finishing;
- a diff that can be edited after it was computed, or whose order depends on
  iteration;
- a report that is silently adopted, or two reports that are silently merged.

The case data is in `fixtures/reconcile/cases.json`. Each case's expected
drifts, changes and deferrals were written by hand; the test compares them
exactly, including their order. Runs from the boundary package alone (REPO-005).
"""
import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager import documents  # noqa: E402
from fleet_manager.model import DesiredState  # noqa: E402
from fleet_manager.observation import Observation, ObservedRunner  # noqa: E402
from fleet_manager.plan import Change, ChangeKind, build_plan  # noqa: E402
from fleet_manager.reconcile import (  # noqa: E402
    RECONCILIATION_SCHEMA,
    ConvergenceLimits,
    DriftKind,
    ReconcileError,
    Reconciliation,
    bound_candidates,
    observation_from_document,
    observation_to_document,
    reconcile,
    reconciliation_id_for,
)

# This suite keeps its own floor; see the note in test_model_v1.py.
EXPECTED_TEST_COUNT = 29

CASES_PATH = Path(__file__).resolve().parent / "fixtures" / "reconcile" / "cases.json"
REPO_ROOT = PKG_ROOT.parent


def _cases() -> dict:
    doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return {case["name"]: case for case in doc["cases"]}


def _state(case: dict) -> DesiredState:
    return documents.from_document(case["state"])


def _observations(case: dict) -> tuple[Observation, ...]:
    return tuple(
        observation_from_document(item) for item in case["observations"]
    )


def _limits(case: dict) -> ConvergenceLimits:
    return ConvergenceLimits(**case["limits"])


def _run(case: dict) -> Reconciliation:
    return reconcile(
        _state(case),
        _observations(case),
        limits=_limits(case),
        halted=case["halted"],
    )


def _ran(case: dict) -> dict:
    return _run(case).document()


def _drain_state(*host_ids: str) -> DesiredState:
    """The drain-completable fixture's state, with one draining host per id."""
    base = _cases()["drain-completable"]["state"]
    template = base["hosts"][0]
    hosts = [dict(template, host_id=host_id, labels={"host": host_id}) for host_id in host_ids]
    drains = [dict(base["drains"][0], host_id=host_id) for host_id in host_ids]
    return documents.from_document(dict(base, hosts=hosts, drains=drains))


def _complete_drain(host_id: str) -> Change:
    return Change(kind=ChangeKind.COMPLETE_DRAIN, subject=host_id)


def _rollout(rollout_id: str) -> Change:
    return Change(
        kind=ChangeKind.ROLLOUT,
        subject="phase1-linux",
        parameters=(
            ("rollout_id", rollout_id),
            ("to_image_digest", "sha256:" + "c" * 64),
        ),
    )


class TestTheDiffIsDeterministic(unittest.TestCase):
    """fleet-003-01: same revision and reports, same reconciliation, byte for byte."""

    def test_every_fixture_matches_its_hand_written_expectation(self) -> None:
        for name, case in _cases().items():
            with self.subTest(case=name):
                document = _ran(case)
                self.assertEqual(case["expect"]["drifts"], document["drifts"])
                self.assertEqual(case["expect"]["changes"], document["changes"])
                self.assertEqual(case["expect"]["deferred"], document["deferred"])
                self.assertEqual(case["expect"]["converged"], document["converged"])

    def test_a_reconciliation_is_reproducible_byte_for_byte(self) -> None:
        for name, case in _cases().items():
            with self.subTest(case=name):
                first = json.dumps(_ran(case), sort_keys=True)
                second = json.dumps(_ran(case), sort_keys=True)
                self.assertEqual(first, second)

    def test_the_id_is_a_digest_of_the_revision_the_reports_and_the_limits(self) -> None:
        case = _cases()["warm-shortfall"]
        state = _state(case)
        reports = _observations(case)
        limits = _limits(case)
        document = _run(case).document()
        self.assertEqual(
            document["reconciliation_id"],
            reconciliation_id_for(state.revision, reports, limits, False),
        )
        self.assertNotEqual(
            document["reconciliation_id"],
            reconciliation_id_for(state.revision, reports, limits, True),
        )
        self.assertNotEqual(
            document["reconciliation_id"],
            reconciliation_id_for(
                state.revision, reports, ConvergenceLimits(max_host_mutations=3), False
            ),
        )

    def test_the_id_is_stable_across_hash_seeds(self) -> None:
        # A new process each time, with a different hash seed: if any part of
        # the id depended on set or dict iteration order, the two would differ.
        code = (
            "import json, sys\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            f"sys.path.insert(0, {str(PKG_ROOT)!r})\n"
            "from fleet_manager import documents\n"
            "from fleet_manager.reconcile import (\n"
            "    ConvergenceLimits, observation_from_document, reconcile,\n"
            ")\n"
            f"doc = json.load(open({str(CASES_PATH)!r}))\n"
            "out = []\n"
            "for case in doc['cases']:\n"
            "    state = documents.from_document(case['state'])\n"
            "    reports = [observation_from_document(x) for x in case['observations']]\n"
            "    limits = ConvergenceLimits(**case['limits'])\n"
            "    out.append(reconcile(state, reports, limits=limits,\n"
            "                         halted=case['halted']).reconciliation_id)\n"
            "print(json.dumps(out))\n"
        )
        ids = []
        for seed in ("0", "1"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(REPO_ROOT))
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            ids.append(result.stdout)
        self.assertEqual(ids[0], ids[1])

    def test_a_reconciliation_cannot_be_edited(self) -> None:
        result = _run(_cases()["warm-shortfall"])
        with self.assertRaises(ReconcileError) as caught:
            replace(result, reconciliation_id="reconciliation:" + "0" * 32)
        self.assertIn("reconciliation_id", str(caught.exception))

    def test_drifts_out_of_their_total_order_are_refused(self) -> None:
        result = _run(_cases()["drain-completable"])
        self.assertEqual(2, len(result.drifts))
        with self.assertRaises(ReconcileError) as caught:
            replace(result, drifts=tuple(reversed(result.drifts)))
        self.assertIn("order", str(caught.exception))

    def test_changes_must_be_the_candidates_that_were_not_deferred(self) -> None:
        result = _run(_cases()["bounded-by-host-mutations"])
        self.assertEqual(3, len(result.candidates))
        self.assertEqual(2, len(result.changes))
        self.assertEqual(1, len(result.deferred))
        # Swapping a kept change for the deferred one keeps every count equal,
        # so only the "changes are the kept candidates" rule can refuse this.
        tampered = (result.changes[0], result.deferred[0].change)
        with self.assertRaises(ReconcileError) as caught:
            replace(result, changes=tampered)
        self.assertIn("candidates", str(caught.exception))


class TestConvergenceIsBounded(unittest.TestCase):
    """fleet-003-02: caps on drains, replacements and host mutations; deferrals speak."""

    def test_a_zero_cap_submits_nothing_and_still_keeps_the_diff(self) -> None:
        case = _cases()["warm-shortfall"]
        result = reconcile(
            _state(case),
            _observations(case),
            limits=ConvergenceLimits(max_drains=0, max_replacements=0, max_host_mutations=0),
        )
        self.assertEqual((), result.changes)
        self.assertEqual(2, len(result.deferred))
        self.assertEqual(1, len(result.drifts))
        for item in result.deferred:
            self.assertIn("host-mutation cap (0)", item.reason)

    def test_the_drain_cap_defers_the_rest(self) -> None:
        state = _drain_state("ucs03", "ucs04")
        submitted, deferred = bound_candidates(
            state,
            [_complete_drain("ucs03"), _complete_drain("ucs04")],
            limits=ConvergenceLimits(max_drains=1, max_host_mutations=2),
        )
        self.assertEqual(("ucs03",), tuple(change.subject for change in submitted))
        self.assertEqual(1, len(deferred))
        self.assertIn("drain cap (1)", deferred[0].reason)
        self.assertEqual("ucs04", deferred[0].change.subject)

    def test_the_replacement_cap_defers_the_rest(self) -> None:
        state = _drain_state("ucs03")
        submitted, deferred = bound_candidates(
            state,
            [_rollout("ro-1"), _rollout("ro-2")],
            limits=ConvergenceLimits(max_replacements=1),
        )
        self.assertEqual(1, len(submitted))
        self.assertEqual(1, len(deferred))
        self.assertIn("replacement cap (1)", deferred[0].reason)
        self.assertEqual("ro-2", deferred[0].change.parameter("rollout_id"))

    def test_a_pool_disruption_budget_caps_destructive_changes(self) -> None:
        state = _drain_state("ucs03", "ucs04")
        self.assertEqual(1, state.pool("phase1-linux").disruption_budget.max_parallel)
        submitted, deferred = bound_candidates(
            state,
            [_complete_drain("ucs03"), _complete_drain("ucs04")],
            limits=ConvergenceLimits(max_drains=5, max_host_mutations=5),
        )
        self.assertEqual(1, len(submitted))
        self.assertIn("phase1-linux disruption budget (1)", deferred[0].reason)

    def test_every_candidate_is_submitted_or_deferred_never_both(self) -> None:
        state = _drain_state("ucs03", "ucs04")
        candidates = [
            _complete_drain("ucs03"),
            _complete_drain("ucs04"),
            _rollout("ro-1"),
        ]
        submitted, deferred = bound_candidates(
            state, candidates, limits=ConvergenceLimits(max_drains=1, max_replacements=1)
        )
        self.assertEqual(len(candidates), len(submitted) + len(deferred))
        self.assertEqual(set(candidates), set(submitted) | {item.change for item in deferred})

    def test_a_malformed_candidate_is_refused_with_its_index(self) -> None:
        state = _drain_state("ucs03")
        malformed = Change(
            kind=ChangeKind.ASSIGN,
            subject="rec.phase1-linux.9",
            parameters=(
                ("assignment_id", "rec.phase1-linux.9"),
                ("request_id", "reconcile.phase1-linux.9"),
                ("pool_id", "phase1-linux"),
            ),
        )
        with self.assertRaises(ReconcileError) as caught:
            bound_candidates(state, [malformed])
        message = str(caught.exception)
        self.assertIn("candidates[0]", message)
        self.assertIn("host_id", message)


class TestRunningWorkIsNeverDisturbed(unittest.TestCase):
    """fleet-003-03: no destructive change against work that is not proven finished."""

    def test_an_unmanaged_runner_is_reported_and_left_alone(self) -> None:
        result = _run(_cases()["unmanaged-runner-is-left-alone"])
        self.assertEqual((), result.changes)
        self.assertEqual((), result.deferred)
        self.assertEqual(
            [("unmanaged_runner", 2)],
            [(drift.kind.value, drift.count) for drift in result.drifts],
        )

    def test_a_silent_host_gets_no_assignment(self) -> None:
        result = _run(_cases()["silent-host-gets-no-assignment"])
        hosts = {change.parameter("host_id") for change in result.changes}
        self.assertEqual({"ucs03"}, hosts)
        self.assertIn(
            DriftKind.HOST_NOT_REPORTING, {drift.kind for drift in result.drifts}
        )

    def test_a_drain_with_an_observed_runner_is_not_completed(self) -> None:
        result = _run(_cases()["drain-blocked-by-observed-runner"])
        self.assertEqual((), result.changes)
        blocked = [d for d in result.drifts if d.kind is DriftKind.DRAIN_BLOCKED]
        self.assertEqual(1, len(blocked))
        self.assertEqual(1, blocked[0].count)
        self.assertNotIn(ChangeKind.COMPLETE_DRAIN, {c.kind for c in result.changes})

    def test_a_drain_with_nothing_left_is_completed(self) -> None:
        result = _run(_cases()["drain-completable"])
        self.assertEqual(
            [ChangeKind.COMPLETE_DRAIN], [change.kind for change in result.changes]
        )

    def test_an_unknown_host_is_reported_and_not_adopted(self) -> None:
        case = _cases()["converged"]
        stray = Observation(
            host_id="zz-unknown",
            observed_at="2026-10-24T06:00:00+00:00",
            runners=(ObservedRunner(
                runner_id="r-9", pool_id="phase1-linux",
                started_at="2026-10-24T06:00:00+00:00",
            ),),
        )
        result = reconcile(_state(case), (*_observations(case), stray))
        self.assertIn(
            (DriftKind.UNKNOWN_HOST, "zz-unknown"),
            {(drift.kind, drift.host_id) for drift in result.drifts},
        )
        self.assertEqual((), result.changes)

    def test_two_reports_for_one_host_are_refused(self) -> None:
        case = _cases()["converged"]
        report = _observations(case)[0]
        with self.assertRaises(ReconcileError) as caught:
            reconcile(_state(case), (report, report))
        self.assertIn("two reports", str(caught.exception))


class TestTheReconciliationIsAValueNotAState(unittest.TestCase):
    """The diff feeds plan/apply; it never produces a revision itself."""

    def test_reconciling_does_not_change_the_state(self) -> None:
        case = _cases()["warm-shortfall"]
        state = _state(case)
        before = documents.to_document(state)
        result = reconcile(state, _observations(case), limits=_limits(case))
        self.assertEqual(before, documents.to_document(state))
        self.assertEqual(case["state"]["revision"], state.revision)
        self.assertEqual(case["state"]["revision"], result.base_revision)

    def test_the_changes_are_the_changes_plan_takes(self) -> None:
        case = _cases()["warm-shortfall"]
        state = _state(case)
        result = reconcile(state, _observations(case), limits=_limits(case))
        plan = build_plan(state, result.changes)
        self.assertEqual(state.revision, plan.base_revision)
        self.assertEqual(state.revision + 2, plan.resulting_revision)

    def test_a_batch_with_two_kinds_is_submitted_in_its_documented_order(self) -> None:
        # The shortfall is found per pool and the drain afterwards, so this is
        # the case where generation order and the documented total order differ.
        base = _cases()["drain-completable"]["state"]
        hosts = [
            dict(base["hosts"][0]),
            dict(base["hosts"][0], host_id="ucs04", labels={"host": "ucs04"},
                 state="active"),
        ]
        state = documents.from_document(dict(base, hosts=hosts))
        report_ucs04 = Observation(
            host_id="ucs04", observed_at="2026-10-24T06:00:00+00:00", runners=()
        )
        result = reconcile(
            state, (report_ucs04,), limits=ConvergenceLimits(max_host_mutations=2)
        )
        self.assertEqual(
            [ChangeKind.COMPLETE_DRAIN, ChangeKind.ASSIGN],
            [change.kind for change in result.candidates],
        )
        self.assertEqual(
            [ChangeKind.COMPLETE_DRAIN, ChangeKind.ASSIGN],
            [change.kind for change in result.changes],
        )

    def test_a_converged_fixture_says_so_and_offers_nothing(self) -> None:
        document = _ran(_cases()["converged"])
        self.assertTrue(document["converged"])
        self.assertEqual([], document["changes"])
        self.assertEqual([], document["deferred"])


class TestObservationDocuments(unittest.TestCase):
    """Fixtures are data, so the report wire form is closed and validated."""

    def test_a_report_round_trips(self) -> None:
        for case in _cases().values():
            for item in case["observations"]:
                with self.subTest(case=case["name"], host=item["host_id"]):
                    parsed = observation_from_document(item)
                    self.assertEqual(item, observation_to_document(parsed))

    def test_a_missing_field_is_named(self) -> None:
        with self.assertRaises(ReconcileError) as caught:
            observation_from_document({"host_id": "ucs03", "runners": []})
        self.assertIn("observed_at", str(caught.exception))

    def test_an_unknown_field_is_refused(self) -> None:
        with self.assertRaises(ReconcileError) as caught:
            observation_from_document(
                {"host_id": "ucs03", "observed_at": "2026-10-24T06:00:00+00:00",
                 "runners": [], "token": "x"}
            )
        self.assertIn("token", str(caught.exception))

    def test_a_non_document_is_refused_not_crashed_on(self) -> None:
        for hostile in (None, "report", [], 7):
            with self.subTest(value=type(hostile).__name__):
                with self.assertRaises(ReconcileError):
                    observation_from_document(hostile)

    def test_the_document_declares_its_schema(self) -> None:
        self.assertEqual(RECONCILIATION_SCHEMA, _ran(_cases()["converged"])["schema"])


class TestSuiteFloor(unittest.TestCase):
    def test_this_suite_runs_all_of_its_tests(self) -> None:
        discovered = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        self.assertEqual(EXPECTED_TEST_COUNT, discovered.countTestCases())


if __name__ == "__main__":
    unittest.main()
