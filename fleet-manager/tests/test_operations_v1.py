# spec: fleet-005-01, fleet-005-02, fleet-005-03, fleet-005-04, fleet-005-05
"""The operation allowlist and receipts (FLEET-005, Sprint 3.2).

Every test is one failure this module exists to prevent:

- an operation that smuggles in a command, argv, script or environment, which
  is what "no general-purpose remote shell API" (D4) means in code;
- an agent given work it never declared, or `cancel_or_timeout` without the
  explicit policy that authorizes it;
- a parameter that carries a secret value instead of a reference (SEC-001);
- a receipt for work that was never issued, or from the wrong host;
- a completion with nothing to show for it;
- a second receipt that quietly rewrites the first;
- an agent receipt forwarded as the authoritative document, instead of being
  mapped into the contract vocabulary by the manager.
"""
import json
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager.model import Runtime  # noqa: E402
from fleet_manager.operations import (  # noqa: E402
    OPERATION_SCHEMA,
    READ_ONLY,
    RECEIPT_SCHEMA,
    AgentCapabilities,
    AgentReceipt,
    Evidence,
    Operation,
    OperationKind,
    OperationLedger,
    OperationRefused,
    ReceiptOutcome,
    RUNNER_ENROLL_MIGRATION,
    Subject,
    SubjectKind,
    permit,
)

EXPECTED_TEST_COUNT = 58

OPERATIONS_SOURCE = PKG_ROOT / "fleet_manager" / "operations.py"
RECEIPT_SCHEMA_PATH = PKG_ROOT / "contracts" / "v1" / "operation-receipt.schema.json"
ENROLL_SCRIPT = PKG_ROOT.parent / "scripts" / "runner-enroll.sh"

STAMP = "2026-10-24T06:00:00Z"
LATER = "2026-10-24T06:05:00Z"
DIGEST = "sha256:" + "ab" * 32
OTHER_DIGEST = "sha256:" + "cd" * 32


def _subject(kind: SubjectKind = SubjectKind.RUNNER, name: str = "runner-a") -> Subject:
    return Subject(kind=kind, subject_id=name)


def _operation(
    kind: OperationKind = OperationKind.CREATE_RUNNER,
    *,
    key: str = "op-1",
    host: str = "host-a",
    subject: Subject | None = None,
    parameters: tuple[tuple[str, str], ...] = (),
) -> Operation:
    return Operation(
        operation_key=key,
        host_id=host,
        kind=kind,
        subject=subject if subject is not None else _subject(),
        issued_at=STAMP,
        parameters=parameters,
    )


CREATE_PARAMETERS = (
    ("registration_ref", "ref:registration-1"),
    ("runner_name", "runner-a"),
    ("pool_id", "pool-a"),
)


def _create(key: str = "op-1", host: str = "host-a") -> Operation:
    return _operation(OperationKind.CREATE_RUNNER, key=key, host=host,
                      parameters=CREATE_PARAMETERS)


CAPS = AgentCapabilities(
    adapters=frozenset({Runtime.PODMAN}),
    operations=frozenset({OperationKind.CREATE_RUNNER, OperationKind.DESTROY_RUNNER}),
)

EVIDENCE = Evidence(digest=DIGEST, location="sha256/ab/log")


class TestOperations(unittest.TestCase):
    def test_the_catalogue_is_the_declared_set_of_eight(self) -> None:
        self.assertEqual(
            {
                "ensure_image", "create_runner", "mark_drain", "destroy_runner",
                "cancel_or_timeout", "observe_runner", "prove_cleanup",
                "rollback_adapter",
            },
            {kind.value for kind in OperationKind},
        )

    def test_an_unknown_operation_kind_is_refused(self) -> None:
        with self.assertRaises(OperationRefused):
            _operation(kind="run_shell")  # type: ignore[arg-type]

    def test_a_shell_shaped_parameter_name_is_refused(self) -> None:
        # The rule is by *name*, so a host that asks is refused before the value
        # is ever looked at. Nothing here can express "run this".
        for name in ("command", "cmd", "argv", "args", "shell", "script", "exec",
                     "entrypoint", "env", "environment", "stdin", "sh", "bash",
                     "commands", "stdout"):
            with self.subTest(name=name):
                with self.assertRaises(OperationRefused) as caught:
                    _operation(OperationKind.DESTROY_RUNNER,
                               parameters=((name, "rm -rf /"),))
                self.assertIn("remote shell", str(caught.exception))
                self.assertNotIn("rm -rf", str(caught.exception))

    def test_a_parameter_that_is_not_of_this_kind_is_refused(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            _operation(OperationKind.DESTROY_RUNNER,
                       parameters=(("image_digest", DIGEST),))
        self.assertIn("is not a parameter of destroy_runner", str(caught.exception))

    def test_a_missing_required_parameter_is_refused(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            _operation(parameters=(("runner_name", "runner-a"),))
        self.assertIn("registration_ref", str(caught.exception))
        self.assertIn("pool_id", str(caught.exception))

    def test_a_parameter_given_twice_is_refused(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            _operation(parameters=CREATE_PARAMETERS + (("runner_name", "runner-b"),))
        self.assertIn("is given twice", str(caught.exception))

    def test_create_runner_needs_all_three_parameters(self) -> None:
        operation = _create()
        self.assertEqual("ref:registration-1", operation.parameter("registration_ref"))
        self.assertEqual("runner-a", operation.parameter("runner_name"))
        self.assertEqual("pool-a", operation.parameter("pool_id"))
        self.assertIsNone(operation.parameter("command"))

    def test_ensure_image_needs_an_immutable_digest(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            _operation(OperationKind.ENSURE_IMAGE,
                       subject=_subject(SubjectKind.HOST, "host-a"),
                       parameters=(("image_digest", "docker.io/library/debian:latest"),))
        self.assertIn("immutable", str(caught.exception))
        operation = _operation(OperationKind.ENSURE_IMAGE,
                               subject=_subject(SubjectKind.HOST, "host-a"),
                               parameters=(("image_digest", DIGEST),))
        self.assertEqual(DIGEST, operation.parameter("image_digest"))

    def test_a_registration_reference_is_a_reference_not_the_material(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            _operation(parameters=(
                ("registration_ref", "ghp_0123456789abcdef0123456789abcdef0123"),
                ("runner_name", "runner-a"),
                ("pool_id", "pool-a"),
            ))
        message = str(caught.exception)
        self.assertIn("references", message)
        # The refusal names the rule; it does not repeat the credential.
        self.assertNotIn("ghp_0123456789abcdef", message)
        # A registration reference is opaque and named, never the material:
        # a bare name is refused as not-a-reference even when it is no secret.
        with self.assertRaises(OperationRefused) as caught:
            _operation(parameters=(
                ("registration_ref", "registration-1"),
                ("runner_name", "runner-a"),
                ("pool_id", "pool-a"),
            ))
        self.assertIn("ref:", str(caught.exception))

    def test_a_parameter_value_that_looks_like_a_credential_is_refused(self) -> None:
        # SEC-001: references and metadata, never secret values. `reason` is
        # free text, which is exactly where a secret would otherwise land.
        with self.assertRaises(OperationRefused) as caught:
            _operation(OperationKind.MARK_DRAIN,
                       parameters=(("reason", "token github_pat_0123456789abcdef0123456789"),))
        self.assertNotIn("github_pat_0123456789abcdef", str(caught.exception))
        self.assertIn("references, never secrets", str(caught.exception))

    def test_a_parameter_value_beyond_the_cap_is_refused(self) -> None:
        with self.assertRaises(OperationRefused):
            _operation(OperationKind.MARK_DRAIN,
                       parameters=(("reason", "x" * 513),))

    def test_parameters_are_stored_sorted_so_equal_is_equal(self) -> None:
        forward = _operation(parameters=CREATE_PARAMETERS)
        backward = _operation(parameters=tuple(reversed(CREATE_PARAMETERS)))
        self.assertEqual(forward, backward)
        self.assertEqual(
            ("pool_id", "registration_ref", "runner_name"),
            tuple(name for name, _ in forward.parameters),
        )

    def test_an_operation_acts_only_on_the_subjects_it_names(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            _operation(OperationKind.CREATE_RUNNER,
                       subject=_subject(SubjectKind.HOST, "host-a"),
                       parameters=CREATE_PARAMETERS)
        self.assertIn("acts on runner", str(caught.exception))
        # mark_drain may name a host or a runner: both are built without error.
        for kind, name in ((SubjectKind.HOST, "host-a"), (SubjectKind.RUNNER, "runner-a")):
            with self.subTest(kind=kind.value):
                _operation(OperationKind.MARK_DRAIN, subject=_subject(kind, name),
                           parameters=(("reason", "scheduled"),))

    def test_the_ids_carry_their_own_forms(self) -> None:
        with self.assertRaises(OperationRefused):
            _operation(key="not a key!")
        with self.assertRaises(OperationRefused):
            _operation(host="Host A")
        with self.assertRaises(OperationRefused):
            _operation(kind=OperationKind.CREATE_RUNNER,
                       subject=Subject(kind=SubjectKind.RUNNER, subject_id="Runner A"),
                       parameters=CREATE_PARAMETERS)

    def test_a_timestamp_without_an_offset_is_refused(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            Operation(
                operation_key="op-1", host_id="host-a", kind=OperationKind.DESTROY_RUNNER,
                subject=_subject(), issued_at="2026-10-24T06:00:00",
            )
        self.assertIn("offset", str(caught.exception))

    def test_read_only_is_a_property_of_the_kind(self) -> None:
        self.assertTrue(
            _operation(OperationKind.OBSERVE_RUNNER,
                       subject=_subject(), parameters=()).read_only
        )
        self.assertFalse(_create().read_only)
        self.assertEqual(
            {OperationKind.OBSERVE_RUNNER, OperationKind.PROVE_CLEANUP}, READ_ONLY
        )


class TestCapabilities(unittest.TestCase):
    def test_an_empty_capability_set_permits_nothing(self) -> None:
        # Deny by default: an agent that declares nothing may be given nothing.
        # An adapter installed is not an allowlist; it is a prerequisite.
        capabilities = AgentCapabilities(adapters=frozenset({Runtime.PODMAN}))
        with self.assertRaises(OperationRefused) as caught:
            permit(_create(), capabilities)
        self.assertIn("not in this agent's allowlist", str(caught.exception))
        self.assertFalse(capabilities.permits(OperationKind.CREATE_RUNNER))
        with self.assertRaises(OperationRefused):
            permit(_create(), AgentCapabilities())

    def test_a_declared_operation_with_an_adapter_is_permitted(self) -> None:
        permit(_create(), CAPS)

    def test_an_agent_with_no_adapter_may_not_be_given_work(self) -> None:
        capabilities = AgentCapabilities(
            operations=frozenset({OperationKind.CREATE_RUNNER}),
        )
        with self.assertRaises(OperationRefused) as caught:
            permit(_create(), capabilities)
        self.assertIn("no runtime adapter", str(caught.exception))

    def test_cancel_or_timeout_needs_the_explicit_policy(self) -> None:
        operation = _operation(OperationKind.CANCEL_OR_TIMEOUT,
                               subject=_subject(),
                               parameters=(("reason", "hung"),))
        declared = AgentCapabilities(
            adapters=frozenset({Runtime.PODMAN}),
            operations=frozenset({OperationKind.CANCEL_OR_TIMEOUT}),
        )
        with self.assertRaises(OperationRefused) as caught:
            permit(operation, declared)
        self.assertIn("explicit policy", str(caught.exception))
        granted = AgentCapabilities(
            adapters=frozenset({Runtime.PODMAN}),
            operations=frozenset({OperationKind.CANCEL_OR_TIMEOUT}),
            allow_cancel_or_timeout=True,
        )
        permit(operation, granted)

    def test_a_read_only_operation_is_still_denied_by_default(self) -> None:
        # Observation is not a free action: it goes through the same allowlist.
        operation = _operation(OperationKind.OBSERVE_RUNNER, subject=_subject())
        with self.assertRaises(OperationRefused):
            permit(operation, CAPS)
        permit(
            operation,
            AgentCapabilities(
                adapters=frozenset({Runtime.PODMAN}),
                operations=frozenset({OperationKind.OBSERVE_RUNNER}),
            ),
        )

    def test_capabilities_refuse_a_non_runtime_adapter(self) -> None:
        with self.assertRaises(OperationRefused):
            AgentCapabilities(adapters=frozenset({"podman"}))  # type: ignore[arg-type]

    def test_capabilities_refuse_a_non_operation_kind(self) -> None:
        with self.assertRaises(OperationRefused):
            AgentCapabilities(operations=frozenset({"create_runner"}))  # type: ignore[arg-type]

    def test_the_policy_flag_must_be_a_bool(self) -> None:
        with self.assertRaises(OperationRefused):
            AgentCapabilities(allow_cancel_or_timeout="yes")  # type: ignore[arg-type]

    def test_permit_refuses_a_non_operation(self) -> None:
        with self.assertRaises(OperationRefused):
            permit({"kind": "create_runner"}, CAPS)  # type: ignore[arg-type]


class TestReceipts(unittest.TestCase):
    def test_a_completion_without_evidence_is_not_a_receipt(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            AgentReceipt(
                operation_key="op-1", host_id="host-a",
                outcome=ReceiptOutcome.COMPLETED, finished_at=LATER,
            )
        self.assertIn("without evidence", str(caught.exception))

    def test_a_failure_may_be_recorded_without_evidence(self) -> None:
        receipt = AgentReceipt(
            operation_key="op-1", host_id="host-a",
            outcome=ReceiptOutcome.FAILED, finished_at=LATER,
            detail="the image was not in the cache",
        )
        self.assertIsNone(receipt.evidence)

    def test_the_evidence_digest_must_be_an_immutable_digest(self) -> None:
        with self.assertRaises(OperationRefused):
            Evidence(digest="sha1:" + "ab" * 20, location="sha256/ab/log")
        with self.assertRaises(OperationRefused):
            Evidence(digest=DIGEST, location="")

    def test_a_detail_that_looks_like_a_credential_is_refused(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            AgentReceipt(
                operation_key="op-1", host_id="host-a",
                outcome=ReceiptOutcome.REJECTED, finished_at=LATER,
                detail="refused with AKIA0123456789ABCDEF still in the message",
            )
        self.assertNotIn("AKIA0123456789ABCDEF", str(caught.exception))
        self.assertIn("never secrets", str(caught.exception))

    def test_a_detail_beyond_the_cap_is_refused(self) -> None:
        with self.assertRaises(OperationRefused):
            AgentReceipt(
                operation_key="op-1", host_id="host-a",
                outcome=ReceiptOutcome.REJECTED, finished_at=LATER,
                detail="x" * 513,
            )

    def test_the_outcome_comes_from_the_enum(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            AgentReceipt(
                operation_key="op-1", host_id="host-a",
                outcome="done", finished_at=LATER,  # type: ignore[arg-type]
            )
        self.assertIn("completed, failed, rejected", str(caught.exception))

    def test_the_ids_carry_their_own_forms(self) -> None:
        with self.assertRaises(OperationRefused):
            AgentReceipt(
                operation_key="not a key!", host_id="host-a",
                outcome=ReceiptOutcome.REJECTED, finished_at=LATER,
            )
        with self.assertRaises(OperationRefused):
            AgentReceipt(
                operation_key="op-1", host_id="Host A",
                outcome=ReceiptOutcome.REJECTED, finished_at=LATER,
            )

    def test_a_receipt_timestamp_without_an_offset_is_refused(self) -> None:
        with self.assertRaises(OperationRefused):
            AgentReceipt(
                operation_key="op-1", host_id="host-a",
                outcome=ReceiptOutcome.REJECTED, finished_at="2026-10-24T06:05:00",
            )

    def test_the_schemas_are_the_declared_wire_names(self) -> None:
        self.assertEqual("fleet-manager-agent-operation/1", OPERATION_SCHEMA)
        self.assertEqual("fleet-manager-agent-receipt/1", RECEIPT_SCHEMA)

    def test_evidence_round_trips_as_the_contract_shape(self) -> None:
        self.assertEqual(
            {"digest": DIGEST, "location": "sha256/ab/log"}, EVIDENCE.document()
        )


class TestLedger(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = OperationLedger()

    def _receipt(self, key: str = "op-1", host: str = "host-a", *,
                 outcome: ReceiptOutcome = ReceiptOutcome.COMPLETED,
                 digest: str = DIGEST, detail: str | None = None) -> AgentReceipt:
        return AgentReceipt(
            operation_key=key,
            host_id=host,
            outcome=outcome,
            finished_at=LATER,
            evidence=Evidence(digest=digest, location="sha256/ab/log")
            if outcome is ReceiptOutcome.COMPLETED else None,
            detail=detail,
        )

    def test_issuing_stores_the_operation(self) -> None:
        issued = self.ledger.issue(_create(), CAPS)
        self.assertIs(issued, self.ledger.issued("op-1"))

    def test_issuing_the_same_key_again_is_a_retry_not_a_second_wish(self) -> None:
        first = self.ledger.issue(_create(), CAPS)
        again = self.ledger.issue(_create(), CAPS)
        self.assertIs(first, again)

    def test_a_key_cannot_be_widened(self) -> None:
        self.ledger.issue(_create(), CAPS)
        widened = _operation(
            OperationKind.CREATE_RUNNER, key="op-1",
            parameters=(
                ("registration_ref", "ref:registration-1"),
                ("runner_name", "runner-b"),
                ("pool_id", "pool-a"),
            ),
        )
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.issue(widened, CAPS)
        self.assertIn("cannot be widened", str(caught.exception))

    def test_work_that_was_never_permitted_is_never_issued(self) -> None:
        with self.assertRaises(OperationRefused):
            self.ledger.issue(
                _operation(OperationKind.ROLLBACK_ADAPTER, key="op-9",
                           subject=_subject(SubjectKind.HOST, "host-a"),
                           parameters=(("image_digest", OTHER_DIGEST),)),
                CAPS,
            )
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.issued("op-9")
        self.assertIn("no operation was issued", str(caught.exception))

    def test_a_receipt_for_an_unissued_key_is_refused(self) -> None:
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.record(self._receipt())
        self.assertIn("no operation was issued", str(caught.exception))

    def test_a_receipt_from_the_wrong_host_is_refused(self) -> None:
        self.ledger.issue(_create(), CAPS)
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.record(self._receipt(host="host-b"))
        self.assertIn("different host", str(caught.exception))

    def test_one_receipt_is_accepted(self) -> None:
        self.ledger.issue(_create(), CAPS)
        receipt = self.ledger.record(self._receipt())
        self.assertIs(receipt, self.ledger.receipt("op-1"))

    def test_the_same_receipt_twice_is_idempotent(self) -> None:
        self.ledger.issue(_create(), CAPS)
        first = self.ledger.record(self._receipt())
        second = self.ledger.record(self._receipt())
        self.assertIs(first, second)

    def test_a_second_receipt_that_says_something_else_is_refused(self) -> None:
        self.ledger.issue(_create(), CAPS)
        self.ledger.record(self._receipt())
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.record(self._receipt(digest=OTHER_DIGEST))
        self.assertIn("the first answer is the answer", str(caught.exception))

    def test_a_read_only_operation_has_nothing_to_attest(self) -> None:
        self.ledger.issue(
            _operation(OperationKind.OBSERVE_RUNNER, subject=_subject()),
            AgentCapabilities(
                adapters=frozenset({Runtime.PODMAN}),
                operations=frozenset({OperationKind.OBSERVE_RUNNER}),
            ),
        )
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.record(self._receipt(outcome=ReceiptOutcome.REJECTED))
        self.assertIn("nothing to attest", str(caught.exception))

    def test_the_authoritative_receipt_needs_a_recorded_claim(self) -> None:
        self.ledger.issue(_create(), CAPS)
        with self.assertRaises(OperationRefused) as caught:
            self.ledger.authoritative_receipt(
                "op-1", receipt_id="rcpt-1", issued_at=LATER,
            )
        self.assertIn("no receipt was recorded", str(caught.exception))

    def test_a_kind_with_no_declared_contract_operation_is_refused(self) -> None:
        # The mapping is a table, and a table can be missing a row. That must
        # fail closed with a refusal, not with a KeyError from a dict lookup.
        import fleet_manager.operations as operations
        saved = operations._CONTRACT_OPERATION.pop(OperationKind.CREATE_RUNNER)
        try:
            self.ledger.issue(_create(), CAPS)
            self.ledger.record(self._receipt())
            with self.assertRaises(OperationRefused) as caught:
                self.ledger.authoritative_receipt(
                    "op-1", receipt_id="rcpt-1", issued_at=LATER,
                )
            self.assertIn("no declared contract operation", str(caught.exception))
        finally:
            operations._CONTRACT_OPERATION[OperationKind.CREATE_RUNNER] = saved

    def test_the_authoritative_receipt_is_built_not_forwarded(self) -> None:
        self.ledger.issue(_create(), CAPS)
        self.ledger.record(self._receipt(detail="created and healthy"))
        document = self.ledger.authoritative_receipt(
            "op-1", receipt_id="rcpt-1", issued_at=LATER,
        )
        self.assertEqual(1, document["contract_version"])
        self.assertEqual("rcpt-1", document["receipt_id"])
        self.assertEqual("assign", document["operation"])
        self.assertEqual("completed", document["outcome"])
        self.assertEqual({"kind": "runner", "id": "runner-a"}, document["subject"])
        self.assertEqual({"kind": "host_agent", "id": "fleet-manager"}, document["actor"])
        self.assertEqual({"digest": DIGEST, "location": "sha256/ab/log"},
                         document["evidence"])
        self.assertEqual("created and healthy", document["detail"])
        self.assertIn("issued_at", document)

    def test_the_agent_claim_is_not_the_authoritative_vocabulary(self) -> None:
        # The agent said `create_runner`; the evidence plane reads `assign`.
        self.ledger.issue(_create(), CAPS)
        self.ledger.record(self._receipt())
        document = self.ledger.authoritative_receipt(
            "op-1", receipt_id="rcpt-1", issued_at=LATER,
        )
        self.assertNotIn("create_runner", json.dumps(document))

    def test_every_mutating_kind_maps_into_the_contract_vocabulary(self) -> None:
        expected = {
            OperationKind.ENSURE_IMAGE: "apply",
            OperationKind.CREATE_RUNNER: "assign",
            OperationKind.MARK_DRAIN: "drain",
            OperationKind.DESTROY_RUNNER: "release",
            OperationKind.CANCEL_OR_TIMEOUT: "release",
            OperationKind.ROLLBACK_ADAPTER: "apply",
        }
        for kind, contract_name in expected.items():
            with self.subTest(kind=kind.value):
                parameters = (
                    (("image_digest", DIGEST),) if kind in (
                        OperationKind.ENSURE_IMAGE, OperationKind.ROLLBACK_ADAPTER
                    ) else
                    (("reason", "scheduled"),) if kind in (
                        OperationKind.MARK_DRAIN, OperationKind.CANCEL_OR_TIMEOUT
                    ) else
                    CREATE_PARAMETERS if kind is OperationKind.CREATE_RUNNER else ()
                )
                subject_kind = (
                    SubjectKind.HOST if kind in (
                        OperationKind.ENSURE_IMAGE, OperationKind.ROLLBACK_ADAPTER
                    ) else SubjectKind.RUNNER
                )
                ledger = OperationLedger()
                ledger.issue(
                    _operation(kind, key="op-x", subject=_subject(subject_kind),
                               parameters=parameters),
                    AgentCapabilities(
                        adapters=frozenset({Runtime.PODMAN}),
                        operations=frozenset({kind}),
                        allow_cancel_or_timeout=True,
                    ),
                )
                ledger.record(AgentReceipt(
                    operation_key="op-x", host_id="host-a",
                    outcome=ReceiptOutcome.REJECTED, finished_at=LATER,
                ))
                document = ledger.authoritative_receipt(
                    "op-x", receipt_id="rcpt-x", issued_at=LATER,
                )
                self.assertEqual(contract_name, document["operation"])
                self.assertEqual("rejected", document["outcome"])

    def test_the_mapped_operations_are_in_the_contract_s_enumeration(self) -> None:
        # The contract is the authority for its own vocabulary: read it from
        # the schema rather than restating the enum here and drifting.
        schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
        allowed = set(schema["properties"]["operation"]["enum"])
        for kind in OperationKind:
            if kind in READ_ONLY:
                with self.subTest(kind=kind.value):
                    self.assertNotIn(kind.value, allowed)
                continue
            with self.subTest(kind=kind.value):
                ledger = OperationLedger()
                ledger.issue(
                    _operation(
                        kind,
                        key="op-map",
                        subject=_subject(
                            SubjectKind.HOST if kind in (
                                OperationKind.ENSURE_IMAGE,
                                OperationKind.ROLLBACK_ADAPTER,
                            ) else SubjectKind.RUNNER
                        ),
                        parameters=(
                            (("image_digest", DIGEST),)
                            if kind in (OperationKind.ENSURE_IMAGE,
                                        OperationKind.ROLLBACK_ADAPTER)
                            else (("reason", "scheduled"),)
                            if kind in (OperationKind.MARK_DRAIN,
                                        OperationKind.CANCEL_OR_TIMEOUT)
                            else CREATE_PARAMETERS
                            if kind is OperationKind.CREATE_RUNNER else ()
                        ),
                    ),
                    AgentCapabilities(
                        adapters=frozenset({Runtime.PODMAN}),
                        operations=frozenset({kind}),
                        allow_cancel_or_timeout=True,
                    ),
                )
                ledger.record(AgentReceipt(
                    operation_key="op-map", host_id="host-a",
                    outcome=ReceiptOutcome.FAILED, finished_at=LATER,
                ))
                document = ledger.authoritative_receipt(
                    "op-map", receipt_id="rcpt-map", issued_at=LATER,
                )
                self.assertIn(document["operation"], allowed)


class TestRunnerEnrollMigration(unittest.TestCase):
    def test_the_script_s_options_are_all_accounted_for(self) -> None:
        # A skip-guarded compatibility check: if the enrollment script is not
        # in this tree, this says so rather than pretending it passed.
        if not ENROLL_SCRIPT.exists():
            self.skipTest("scripts/runner-enroll.sh is not in this tree")
        import re
        source = ENROLL_SCRIPT.read_text(encoding="utf-8")
        options = {
            "--" + name
            for name in re.findall(r"^#   --([a-z-]+)", source, flags=re.MULTILINE)
        }
        self.assertTrue(options, "the enrollment script's option list was not found")
        self.assertEqual(options, set(RUNNER_ENROLL_MIGRATION))

    def test_every_migration_names_where_the_duty_went(self) -> None:
        for option, (destination, why) in RUNNER_ENROLL_MIGRATION.items():
            with self.subTest(option=option):
                self.assertTrue(destination.strip())
                self.assertTrue(why.strip())

    def test_the_table_is_keyed_by_the_script_s_option_names(self) -> None:
        for option in RUNNER_ENROLL_MIGRATION:
            self.assertRegex(option, r"^--[a-z-]+$")


class TestTheModule(unittest.TestCase):
    ALLOWED_IMPORTS = {
        "__future__", "re", "dataclasses", "enum",
    }

    def test_the_module_imports_only_what_it_declares(self) -> None:
        import ast
        imports = set()
        tree = ast.parse(OPERATIONS_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imports.add(node.module.split(".")[0])
        self.assertEqual(self.ALLOWED_IMPORTS, imports)

    def test_the_module_never_reads_the_wall_clock(self) -> None:
        source = OPERATIONS_SOURCE.read_text(encoding="utf-8")
        for forbidden in (".now(", ".utcnow(", ".today(", "time.time(", "monotonic("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_module_has_no_way_to_execute_anything(self) -> None:
        # Belt and braces on D4: not just no shell-shaped parameter name, but
        # nothing in the module that could run a process at all.
        source = OPERATIONS_SOURCE.read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "os.popen", "eval(", "exec(",
                          "popen(", "importlib"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class TestSuiteFloor(unittest.TestCase):
    def test_this_suite_runs_all_of_its_tests(self) -> None:
        discovered = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        self.assertEqual(EXPECTED_TEST_COUNT, discovered.countTestCases())


if __name__ == "__main__":
    unittest.main()
