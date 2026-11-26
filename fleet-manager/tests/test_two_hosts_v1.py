# spec: fleet-006-04
"""Two test hosts, a signed no-op desired state, and the failure fixtures.

This is Sprint 3's exit criterion run as a suite rather than described as a
plan: "two test hosts reconcile signed no-op desired state; compromised/replayed
commands fail closed." The world is in `fixtures/two-hosts/world.json` — two
enrolled hosts, one pool, one warm runner each, already converged — and the
failure and revocation cases are in `fixtures/two-hosts/cases.json` with
hand-written expectations.

Each case names a scenario and the rule it must fail closed on. The scenario
code is here because the interesting part is the *protocol run* (keys,
signatures, sequences), which a JSON file cannot honestly hold: a signature in
a fixture would be a signature nobody verified. What the fixture does hold is
what must happen and the exact rule the refusal must name.

The signature provider is the same deterministic double as the channel suite.
This slice owns the protocol, not the curve.
"""
import hashlib
import json
import re
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager.channel import (  # noqa: E402
    ChannelEnvelope,
    ChannelError,
    AgentChannel,
    signed_bytes as channel_signed_bytes,
)
from fleet_manager.documents import from_document  # noqa: E402
from fleet_manager.model import Runtime  # noqa: E402
from fleet_manager.operations import (  # noqa: E402
    AgentCapabilities,
    Operation,
    OperationKind,
    OperationLedger,
    OperationRefused,
    Subject,
    SubjectKind,
)
from fleet_manager.reconcile import (  # noqa: E402
    ConvergenceLimits,
    observation_from_document,
    reconcile,
)
from fleet_manager.state import (  # noqa: E402
    SignedState,
    StateError,
    StateIssuer,
    accept_state,
    state_from_document,
    state_to_document,
)

EXPECTED_TEST_COUNT = 8

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "two-hosts"
T0 = datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)
MANAGER_KEY = bytes([7]) * 32

WORLD = json.loads((FIXTURES / "world.json").read_text(encoding="utf-8"))
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]


def _sign(key: bytes, message: bytes) -> bytes:
    """Deterministic, 64 bytes, derived from both inputs. Not cryptography."""
    return hashlib.sha512(key + message).digest()


def _verifier(public_key: bytes, message: bytes, signature: bytes) -> bool:
    return signature == _sign(public_key, message)


def _signer(key: bytes):
    return lambda message: _sign(key, message)


class TwoHostWorld:
    """One two-host world, rebuilt per scenario so a case cannot leak state."""

    def __init__(self) -> None:
        self.state = from_document(WORLD["state"])
        self.observations = tuple(
            observation_from_document(item) for item in WORLD["observations"]
        )
        self.limits = ConvergenceLimits(**WORLD["limits"])
        self.halted = WORLD["halted"]
        self.channel = AgentChannel()
        self.issuer = StateIssuer()
        self.ledger = OperationLedger()
        self.keys = {
            "host-a": bytes([1]) * 32,
            "host-b": bytes([2]) * 32,
        }
        self.key_ids: dict[str, str] = {}
        for host_id, public_key in self.keys.items():
            token = self.channel.issue_token(
                host_id, ("phase1-linux",), at=T0,
                token_id=f"token-{host_id}",
            )
            credential = self.channel.enroll(token.token_id, public_key, at=T0)
            self.key_ids[host_id] = credential.key_id

    # --- reports: the host -> manager direction ----------------------------

    def report(
        self,
        host_id: str,
        *,
        sequence: int = 1,
        nonce: str | None = None,
        sign_with: bytes | None = None,
        signature: bytes | None = None,
    ) -> ChannelEnvelope:
        """One signed report carrying exactly this host's observation."""
        body = next(
            item for item in WORLD["observations"] if item["host_id"] == host_id
        )
        body_json = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        unsigned = ChannelEnvelope(
            host_id=host_id,
            key_id=self.key_ids[host_id],
            sequence=sequence,
            nonce=nonce or f"nonce-{host_id}-{sequence:04d}",
            issued_at="2026-10-24T06:00:00Z",
            expires_at="2026-10-24T06:04:00Z",
            body_json=body_json,
            signature=bytes(64),
        )
        key = self.keys[host_id] if sign_with is None else sign_with
        return replace(
            unsigned,
            signature=signature if signature is not None
            else _sign(key, channel_signed_bytes(unsigned)),
        )

    def accept(self, host_id: str, envelope: ChannelEnvelope, *, at: datetime = T0):
        return self.channel.accept(envelope, at=at, verifier=_verifier)

    # --- desired state: the manager -> host direction ----------------------

    def desired_state(self, host_id: str, *, at: datetime = T0,
                      ttl: timedelta = timedelta(minutes=5)) -> SignedState:
        return self.issuer.issue(
            WORLD["state"], audience=host_id, issued_at=at,
            signer=_signer(MANAGER_KEY), ttl=ttl,
        )

    def host_accepts(self, state: SignedState, host_id: str, *,
                     at: datetime = T0, last_sequence: int | None = None):
        return accept_state(
            state, at=at, verifier=_verifier, public_key=MANAGER_KEY,
            audience=host_id, last_sequence=last_sequence,
        )


def _issue_work(world: TwoHostWorld, host_id: str):
    """Turn an accepted report into one typed operation.

    Capabilities here are wide enough to permit it, so a refusal would have to
    come from an earlier stage — which is the property the pipeline case tests.
    """
    return world.ledger.issue(
        Operation(
            operation_key=f"op-{host_id}", host_id=host_id,
            kind=OperationKind.CREATE_RUNNER,
            subject=Subject(kind=SubjectKind.RUNNER, subject_id=f"runner-{host_id}"),
            issued_at="2026-10-24T06:00:00Z",
            parameters=(
                ("pool_id", "phase1-linux"),
                ("registration_ref", "ref:registration-1"),
                ("runner_name", f"runner-{host_id}"),
            ),
        ),
        AgentCapabilities(
            adapters=frozenset({Runtime.PODMAN}),
            operations=frozenset({OperationKind.CREATE_RUNNER}),
        ),
    )


def _scenario(name: str, world: TwoHostWorld) -> tuple[str, str]:
    """Run one fixture scenario. Returns (outcome, message)."""
    try:
        if name == "replayed-report":
            envelope = world.report("host-a")
            world.accept("host-a", envelope)
            world.accept("host-a", envelope)

        elif name == "reordered-report":
            world.accept("host-a", world.report("host-a", sequence=2,
                                                nonce="nonce-first-0002"))
            world.accept("host-a", world.report("host-a", sequence=1,
                                                nonce="nonce-late-0001"))

        elif name == "wrong-host-report":
            # host-a's identity on the wire, host-b's key in the signature: a
            # compromised key for one host must not speak for another.
            world.accept("host-a", world.report("host-a", sign_with=world.keys["host-b"]))

        elif name == "forged-report":
            envelope = world.report("host-a", signature=bytes(64))
            world.accept("host-a", envelope)

        elif name == "revoked-report":
            world.channel.revoke("host-a", world.key_ids["host-a"], at=T0)
            world.accept("host-a", world.report("host-a", sequence=2))

        elif name == "revoked-key-not-reusable":
            revoked = world.keys["host-a"]
            world.channel.revoke("host-a", world.key_ids["host-a"], at=T0)
            token = world.channel.issue_token(
                "host-c", ("phase1-linux",), at=T0, token_id="token-host-c"
            )
            world.channel.enroll(token.token_id, revoked, at=T0)

        elif name == "compromised-host-pipeline":
            # The whole pipeline, in order: a report the channel refuses must
            # never become work. The capability set below would issue it, so
            # the scenario only reaches "accepted" if the channel let a revoked
            # host through.
            world.channel.revoke("host-a", world.key_ids["host-a"], at=T0)
            world.accept("host-a", world.report("host-a", sequence=2))
            _issue_work(world, "host-a")
            return "accepted", "a revoked host's report became work"

        elif name == "replayed-state":
            state = world.desired_state("host-a")
            accepted = world.host_accepts(state, "host-a")
            world.host_accepts(state, "host-a", last_sequence=accepted.sequence)

        elif name == "wrong-audience-state":
            state = world.desired_state("host-a")
            world.host_accepts(state, "host-b")

        elif name == "tampered-state":
            state = world.desired_state("host-a")
            document = state_to_document(state)
            document["body"]["revision"] = 99
            world.host_accepts(state_from_document(document), "host-a")

        elif name == "forged-state":
            state = world.desired_state("host-a")
            world.host_accepts(replace(state, signature="00" * 64), "host-a")

        elif name == "expired-state":
            state = world.desired_state("host-a", ttl=timedelta(seconds=60))
            world.host_accepts(state, "host-a",
                               at=T0 + timedelta(seconds=61))

        elif name == "revoked-host-state-still-verifies":
            # Revocation cuts the host's voice, not the manager's. The host can
            # still read what it was asked to become, and that is not a way in.
            state = world.desired_state("host-a")
            world.channel.revoke("host-a", world.key_ids["host-a"], at=T0)
            accepted = world.host_accepts(state, "host-a")
            return "accepted", accepted.audience

        else:
            return "unknown", f"no scenario named {name!r}"
    except (ChannelError, StateError, OperationRefused) as exc:
        return "refused", str(exc)
    return "accepted", ""


class TestTwoHosts(unittest.TestCase):
    def test_the_world_is_two_hosts_already_converged(self) -> None:
        world = TwoHostWorld()
        document = reconcile(
            world.state, world.observations,
            limits=world.limits, halted=world.halted,
        ).document()
        self.assertEqual(WORLD["expect"]["drifts"], document["drifts"])
        self.assertEqual(WORLD["expect"]["changes"], document["changes"])
        self.assertEqual(WORLD["expect"]["deferred"], document["deferred"])
        self.assertEqual(WORLD["expect"]["converged"], document["converged"])

    def test_two_test_hosts_reconcile_a_signed_no_op_desired_state(self) -> None:
        """Sprint 3's exit, end to end, in one test.

        Both hosts enroll, both sign a report, both are accepted, the manager
        signs each host its own no-op desired state, both hosts verify it, and
        the reconciliation of the two reports against that state is a no-op.
        """
        world = TwoHostWorld()
        accepted_reports = {}
        for host_id in ("host-a", "host-b"):
            accepted_reports[host_id] = world.accept(
                host_id, world.report(host_id)
            )
            self.assertEqual(1, accepted_reports[host_id].sequence)
            # The manager reconciles the body the host signed, not the fixture.
            self.assertEqual(
                next(item for item in WORLD["observations"]
                     if item["host_id"] == host_id),
                accepted_reports[host_id].body(),
            )

        # Each host gets its own envelope, its own sequence, signed by the
        # manager, and each host's checks accept it.
        sequences = {}
        for host_id in ("host-a", "host-b"):
            state = world.desired_state(host_id)
            accepted = world.host_accepts(state, host_id)
            sequences[host_id] = accepted.sequence
            self.assertEqual(7, accepted.state().revision)
        self.assertEqual({"host-a": 1, "host-b": 1}, sequences)

        # The second round of state is a new sequence for each host, and a
        # replay of the first is refused — which is what makes "no-op" mean
        # *this* world and not any world.
        for host_id in ("host-a", "host-b"):
            again = world.desired_state(host_id)
            self.assertEqual(2, world.host_accepts(again, host_id).sequence)
            with self.assertRaises(StateError):
                world.host_accepts(again, host_id, last_sequence=2)

        document = reconcile(
            world.state,
            tuple(
                observation_from_document(accepted_reports[host_id].body())
                for host_id in ("host-a", "host-b")
            ),
            limits=world.limits, halted=world.halted,
        ).document()
        self.assertTrue(document["converged"])
        self.assertEqual([], document["drifts"])
        self.assertEqual([], document["changes"])

    def test_a_forged_report_costs_the_real_host_nothing(self) -> None:
        # The forgery is refused *before* the replay state advances, so the
        # host's own next report is still accepted at its next sequence.
        world = TwoHostWorld()
        with self.assertRaises(ChannelError):
            world.accept("host-a", world.report("host-a", signature=bytes(64)))
        self.assertIsNone(world.channel.last_sequence("host-a", world.key_ids["host-a"]))
        world.accept("host-a", world.report("host-a"))
        self.assertEqual(1, world.channel.last_sequence("host-a", world.key_ids["host-a"]))

    def test_a_healthy_hosts_report_becomes_work(self) -> None:
        # The pair for the compromised case: the same pipeline, the same
        # capabilities, and the only difference is whether the channel accepted
        # the report. Without this the refusal above could be anything.
        world = TwoHostWorld()
        world.accept("host-a", world.report("host-a"))
        issued = _issue_work(world, "host-a")
        self.assertEqual("host-a", issued.host_id)
        self.assertEqual(OperationKind.CREATE_RUNNER, issued.kind)
        self.assertEqual(issued, world.ledger.issued(issued.operation_key))

    def test_every_failure_fixture_fails_closed_on_the_rule_it_names(self) -> None:
        for case in CASES:
            with self.subTest(case=case["name"]):
                outcome, message = _scenario(case["scenario"], TwoHostWorld())
                self.assertEqual(
                    case["expect"], outcome,
                    f"{case['name']}: expected {case['expect']}, got "
                    f"{outcome} ({message})",
                )
                if case["expect_contains"]:
                    self.assertIn(case["expect_contains"], message)

    def test_the_failure_fixtures_cover_both_directions(self) -> None:
        # Reports (host -> manager) and desired state (manager -> host) are two
        # halves of the same pull model; the fixture set must not silently drop
        # one of them.
        scenarios = {case["scenario"] for case in CASES}
        for required in (
            "replayed-report", "revoked-report", "forged-report",
            "replayed-state", "tampered-state", "wrong-audience-state",
        ):
            with self.subTest(scenario=required):
                self.assertIn(required, scenarios)

    def test_the_fixtures_carry_no_signature_of_their_own(self) -> None:
        # A fixture that shipped a signature would be a signature nobody
        # verified in this suite. The signs here are computed at run time, so
        # the case files carry expectations only: a closed key set, and no
        # value that looks like signature material.
        allowed = {"name", "why", "scenario", "expect", "expect_contains"}
        hex_run = re.compile(r"[0-9a-fA-F]{32,}")
        for case in CASES:
            with self.subTest(case=case["name"]):
                self.assertEqual(allowed, set(case))
                for key, value in case.items():
                    self.assertIsInstance(value, str)
                    self.assertNotRegex(value, hex_run)
        raw = (FIXTURES / "world.json").read_text(encoding="utf-8")
        self.assertNotIn("signature", json.dumps(WORLD["state"]))
        self.assertNotIn("signature", raw)


class TestSuiteFloor(unittest.TestCase):
    def test_this_suite_runs_all_of_its_tests(self) -> None:
        discovered = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        self.assertEqual(EXPECTED_TEST_COUNT, discovered.countTestCases())


if __name__ == "__main__":
    unittest.main()
