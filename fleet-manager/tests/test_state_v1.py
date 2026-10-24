# spec: fleet-006-01, fleet-006-02, fleet-006-03
"""The manager's signed desired state (FLEET-006, Sprint 3.3).

Every test is one failure the envelope exists to prevent:

- a desired state that can be redirected at another host (audience is not a
  label; it is the authorization);
- a captured state played back later (sequence, expiry);
- a state whose signature covers bytes the consumer does not read;
- a forged or tampered state that is treated as configuration;
- a signature provider that fails and is silently replaced by a fallback.

The provider here is a deterministic test double. This slice owns the protocol
(which bytes, which checks, in what order), not the curve — the same decision
as the channel, for the same reason.
"""
import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager.documents import DOCUMENT_SCHEMA  # noqa: E402
from fleet_manager.model import DesiredState  # noqa: E402
from fleet_manager.state import (  # noqa: E402
    MAX_STATE_LIFETIME,
    STATE_SCHEMA,
    AcceptedState,
    SignedState,
    StateError,
    StateIssuer,
    accept_state,
    signed_bytes,
    state_from_document,
    state_to_document,
)

EXPECTED_TEST_COUNT = 46

STATE_SOURCE = PKG_ROOT / "fleet_manager" / "state.py"
T0 = datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)
MANAGER_KEY = bytes([7]) * 32


def _sign(key: bytes, message: bytes) -> bytes:
    """Deterministic, 64 bytes, derived from both inputs. Not cryptography."""
    return hashlib.sha512(key + message).digest()


def _signer(key: bytes):
    return lambda message: _sign(key, message)


def _verifier(public_key: bytes, message: bytes, signature: bytes) -> bool:
    return signature == _sign(public_key, message)


def _body(revision: int = 3) -> dict:
    # A no-op world at one revision: nothing in it, which is what a host that
    # is already correct should be asked to become.
    return {"schema": DOCUMENT_SCHEMA, "revision": revision}


def _stamp(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _state(
    *,
    audience: str = "host-a",
    revision: int = 3,
    sequence: int = 1,
    body: dict | None = None,
    signature: str = "ab" * 64,
    issued_at: datetime = T0,
    expires_at: datetime | None = None,
) -> SignedState:
    return SignedState(
        audience=audience,
        revision=revision,
        sequence=sequence,
        issued_at=_stamp(issued_at),
        expires_at=_stamp(expires_at or (issued_at + timedelta(seconds=300))),
        body_json=json.dumps(
            body if body is not None else _body(revision),
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ),
        signature=signature,
    )


class TestEnvelope(unittest.TestCase):
    def test_the_schema_is_the_declared_wire_name(self) -> None:
        self.assertEqual("fleet-manager-signed-state/1", STATE_SCHEMA)

    def test_an_envelope_names_exactly_one_audience(self) -> None:
        with self.assertRaises(StateError):
            _state(audience="Host A")
        with self.assertRaises(StateError):
            _state(audience="")

    def test_the_revision_and_sequence_start_at_one(self) -> None:
        for name in ("revision", "sequence"):
            with self.subTest(name=name):
                with self.assertRaises(StateError):
                    _state(**{name: 0})
                with self.assertRaises(StateError):
                    _state(**{name: True})

    def test_the_sequence_is_bounded(self) -> None:
        # An out-of-range integer is not a sequence, and a value that cannot be
        # compared is not replay protection.
        with self.assertRaises(StateError) as caught:
            _state(sequence=2**63)
        self.assertIn("out of range", str(caught.exception))

    def test_a_body_beyond_the_limit_is_refused(self) -> None:
        envelope = _state()
        huge = json.dumps(
            {"schema": DOCUMENT_SCHEMA, "revision": 1, "pad": "a" * (256 * 1024)},
            sort_keys=True, separators=(",", ":"),
        )
        with self.assertRaises(StateError) as caught:
            SignedState(
                audience=envelope.audience, revision=1, sequence=1,
                issued_at=envelope.issued_at, expires_at=envelope.expires_at,
                body_json=huge, signature=envelope.signature,
            )
        self.assertIn("byte limit", str(caught.exception))

    def test_the_lifetime_is_bounded(self) -> None:
        with self.assertRaises(StateError) as caught:
            _state(expires_at=T0 + MAX_STATE_LIFETIME + timedelta(seconds=1))
        self.assertIn("lifetime exceeds", str(caught.exception))
        with self.assertRaises(StateError):
            _state(expires_at=T0 - timedelta(seconds=1))

    def test_the_body_must_be_a_desired_state_document(self) -> None:
        with self.assertRaises(StateError) as caught:
            _state(body={"schema": DOCUMENT_SCHEMA})
        self.assertIn("desired-state document", str(caught.exception))

    def test_the_body_must_be_its_canonical_text(self) -> None:
        padded = json.dumps(_body(), sort_keys=True, separators=(", ", ": "))
        envelope = _state()
        with self.assertRaises(StateError) as caught:
            SignedState(
                audience=envelope.audience,
                revision=envelope.revision,
                sequence=envelope.sequence,
                issued_at=envelope.issued_at,
                expires_at=envelope.expires_at,
                body_json=padded,
                signature=envelope.signature,
            )
        self.assertIn("canonical", str(caught.exception))

    def test_the_signature_is_64_bytes_of_lowercase_hex(self) -> None:
        with self.assertRaises(StateError):
            _state(signature="zz" * 64)
        with self.assertRaises(StateError):
            _state(signature="ab" * 32)
        with self.assertRaises(StateError):
            _state(signature=("AB" * 64))

    def test_a_timestamp_without_an_offset_is_refused(self) -> None:
        with self.assertRaises(StateError) as caught:
            SignedState(
                audience="host-a", revision=1, sequence=1,
                issued_at="2026-10-24T06:00:00",
                expires_at=_stamp(T0 + timedelta(minutes=5)),
                body_json=json.dumps(_body(), sort_keys=True, separators=(",", ":")),
                signature="ab" * 64,
            )
        self.assertIn("offset", str(caught.exception))

    def test_the_body_and_the_signature_stay_out_of_repr(self) -> None:
        # A value that prints its signature into a log leaks it.
        shown = repr(_state())
        self.assertNotIn("ab" * 64, shown)
        self.assertNotIn("body_json", shown)


class TestSignedBytes(unittest.TestCase):
    def test_the_profile_is_pinned_byte_for_byte(self) -> None:
        envelope = _state()
        self.assertEqual(
            b'{"audience":"host-a","body":{"revision":3,"schema":"fleet-manager-desired-state/1"}'
            b',"expires_at":"2026-10-24T06:05:00Z","issued_at":"2026-10-24T06:00:00Z"'
            b',"revision":3,"schema":"fleet-manager-signed-state/1","sequence":1}',
            signed_bytes(envelope),
        )

    def test_the_signature_field_is_not_covered(self) -> None:
        one = _state(signature="ab" * 64)
        two = _state(signature="cd" * 64)
        self.assertEqual(signed_bytes(one), signed_bytes(two))

    def test_every_other_field_is_covered(self) -> None:
        base = _state()
        variants = {
            "audience": _state(audience="host-b"),
            "revision": _state(revision=4),
            "sequence": _state(sequence=2),
            "issued_at": _state(issued_at=T0 + timedelta(seconds=1)),
            "expires_at": _state(expires_at=T0 + timedelta(seconds=301)),
            "body": _state(body=_body(revision=8), revision=8),
        }
        for name, changed in variants.items():
            with self.subTest(field=name):
                self.assertNotEqual(signed_bytes(base), signed_bytes(changed))


class TestDocuments(unittest.TestCase):
    def test_the_wire_form_round_trips(self) -> None:
        envelope = _state()
        self.assertEqual(envelope, state_from_document(state_to_document(envelope)))

    def test_a_missing_field_is_named(self) -> None:
        document = state_to_document(_state())
        del document["audience"]
        with self.assertRaises(StateError) as caught:
            state_from_document(document)
        self.assertIn("missing audience", str(caught.exception))

    def test_an_unknown_field_is_refused(self) -> None:
        document = state_to_document(_state())
        document["command"] = "rm -rf /"
        with self.assertRaises(StateError) as caught:
            state_from_document(document)
        self.assertIn("unknown command", str(caught.exception))

    def test_the_declared_schema_is_required(self) -> None:
        document = state_to_document(_state())
        document["schema"] = "something-else/1"
        with self.assertRaises(StateError) as caught:
            state_from_document(document)
        self.assertIn("signed-state/1", str(caught.exception))


class TestIssuer(unittest.TestCase):
    def setUp(self) -> None:
        self.issuer = StateIssuer()

    def test_sequences_increase_per_audience(self) -> None:
        first = self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                                  signer=_signer(MANAGER_KEY))
        second = self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                                   signer=_signer(MANAGER_KEY))
        other = self.issuer.issue(_body(), audience="host-b", issued_at=T0,
                                  signer=_signer(MANAGER_KEY))
        self.assertEqual((1, 2, 1), (first.sequence, second.sequence, other.sequence))
        self.assertEqual(2, self.issuer.last_sequence("host-a"))
        self.assertEqual(1, self.issuer.last_sequence("host-b"))
        self.assertIsNone(self.issuer.last_sequence("host-c"))

    def test_an_issued_state_verifies(self) -> None:
        state = self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                                  signer=_signer(MANAGER_KEY))
        accepted = accept_state(
            state, at=T0, verifier=_verifier, public_key=MANAGER_KEY,
            audience="host-a", last_sequence=None,
        )
        self.assertEqual(3, accepted.state().revision)

    def test_the_revision_comes_from_the_document(self) -> None:
        state = self.issuer.issue(_body(revision=9), audience="host-a",
                                  issued_at=T0, signer=_signer(MANAGER_KEY))
        self.assertEqual(9, state.revision)

    def test_a_signer_that_raises_is_a_refusal_not_a_fallback(self) -> None:
        def broken(message: bytes) -> bytes:
            raise RuntimeError("key store unavailable")

        with self.assertRaises(StateError) as caught:
            self.issuer.issue(_body(), audience="host-a", issued_at=T0, signer=broken)
        self.assertIn("does not fall back", str(caught.exception))

    def test_a_signer_that_returns_something_else_is_refused(self) -> None:
        with self.assertRaises(StateError):
            self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                              signer=lambda message: "signed")

    def test_a_signer_that_is_not_callable_is_refused(self) -> None:
        # A provider that is not a function would fail inside the sign call
        # anyway; naming it here is what makes the refusal the first thing the
        # caller learns.
        for value in (None, "sign", b"sign"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(StateError) as caught:
                    self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                                      signer=value)
                self.assertIn("must be callable", str(caught.exception))

    def test_a_ttl_that_is_not_positive_is_refused(self) -> None:
        for value in (timedelta(0), timedelta(seconds=-1), 300):
            with self.subTest(value=repr(value)):
                with self.assertRaises(StateError) as caught:
                    self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                                      signer=_signer(MANAGER_KEY), ttl=value)
                self.assertIn("positive timedelta", str(caught.exception))

    def test_a_ttl_beyond_the_maximum_is_refused(self) -> None:
        with self.assertRaises(StateError):
            self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                              signer=_signer(MANAGER_KEY),
                              ttl=MAX_STATE_LIFETIME + timedelta(seconds=1))

    def test_the_expires_at_is_the_issue_instant_plus_the_ttl(self) -> None:
        state = self.issuer.issue(_body(), audience="host-a", issued_at=T0,
                                  signer=_signer(MANAGER_KEY),
                                  ttl=timedelta(seconds=60))
        self.assertEqual("2026-10-24T06:01:00Z", state.expires_at)
        self.assertEqual("2026-10-24T06:00:00Z", state.issued_at)


class TestAccept(unittest.TestCase):
    def _signed(self, **kwargs) -> SignedState:
        issuer = StateIssuer()
        return issuer.issue(kwargs.pop("body", _body()),
                            audience=kwargs.pop("audience", "host-a"),
                            issued_at=kwargs.pop("issued_at", T0),
                            signer=_signer(MANAGER_KEY))

    def _accept(self, state: SignedState, **kwargs) -> AcceptedState:
        return accept_state(
            state,
            at=kwargs.pop("at", T0),
            verifier=kwargs.pop("verifier", _verifier),
            public_key=kwargs.pop("public_key", MANAGER_KEY),
            audience=kwargs.pop("audience", "host-a"),
            last_sequence=kwargs.pop("last_sequence", None),
        )

    def test_a_good_state_is_accepted(self) -> None:
        accepted = self._accept(self._signed())
        self.assertEqual("host-a", accepted.audience)
        self.assertEqual(1, accepted.sequence)
        self.assertEqual({"schema": DOCUMENT_SCHEMA, "revision": 3},
                         json.loads(accepted.body_json))

    def test_a_state_for_another_audience_is_refused(self) -> None:
        state = self._signed()
        with self.assertRaises(StateError) as caught:
            self._accept(state, audience="host-b")
        self.assertIn("different audience", str(caught.exception))

    def test_the_audience_is_checked_before_the_signature(self) -> None:
        # A redirected state must be refused even if it would also fail
        # verification: the first thing a host learns is that it is not for it.
        forged = SignedState(
            audience="host-b", revision=3, sequence=1,
            issued_at=_stamp(T0), expires_at=_stamp(T0 + timedelta(minutes=5)),
            body_json=json.dumps(_body(), sort_keys=True, separators=(",", ":")),
            signature="00" * 64,
        )
        with self.assertRaises(StateError) as caught:
            self._accept(forged, audience="host-a")
        self.assertIn("different audience", str(caught.exception))

    def test_an_expired_state_is_refused(self) -> None:
        state = self._signed()
        with self.assertRaises(StateError) as caught:
            self._accept(state, at=T0 + MAX_STATE_LIFETIME + timedelta(seconds=1))
        self.assertIn("expired", str(caught.exception))

    def test_a_state_issued_beyond_the_clock_skew_is_refused(self) -> None:
        state = self._signed()
        with self.assertRaises(StateError) as caught:
            self._accept(state, at=T0 - timedelta(seconds=61))
        self.assertIn("clock skew", str(caught.exception))

    def test_a_forged_signature_is_refused(self) -> None:
        forged = SignedState(
            audience="host-a", revision=3, sequence=1,
            issued_at=_stamp(T0), expires_at=_stamp(T0 + timedelta(minutes=5)),
            body_json=json.dumps(_body(), sort_keys=True, separators=(",", ":")),
            signature="cd" * 64,
        )
        with self.assertRaises(StateError) as caught:
            self._accept(forged)
        self.assertIn("did not verify", str(caught.exception))

    def test_a_tampered_body_is_refused(self) -> None:
        # The body is the configuration: changing it must break the signature.
        signed = self._signed()
        tampered = SignedState(
            audience=signed.audience, revision=signed.revision,
            sequence=signed.sequence, issued_at=signed.issued_at,
            expires_at=signed.expires_at,
            body_json=json.dumps(_body(revision=4), sort_keys=True,
                                 separators=(",", ":")),
            signature=signed.signature,
        )
        with self.assertRaises(StateError) as caught:
            self._accept(tampered)
        self.assertIn("did not verify", str(caught.exception))

    def test_a_verifier_that_is_not_callable_is_refused(self) -> None:
        for value in (None, "verify", b"verify"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(StateError) as caught:
                    accept_state(self._signed(), at=T0, verifier=value,
                                 public_key=MANAGER_KEY, audience="host-a")
                self.assertIn("must be callable", str(caught.exception))

    def test_a_verifier_that_raises_is_a_refusal_not_a_fallback(self) -> None:
        def broken(public_key, message, signature) -> bool:
            raise RuntimeError("provider unavailable")

        with self.assertRaises(StateError) as caught:
            self._accept(self._signed(), verifier=broken)
        self.assertIn("does not fall back", str(caught.exception))

    def test_only_exactly_true_verifies(self) -> None:
        for value in (1, "true", [], object()):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(StateError):
                    self._accept(self._signed(),
                                 verifier=lambda *args, _v=value: _v)

    def test_a_replayed_sequence_is_refused(self) -> None:
        state = self._signed()
        accepted = self._accept(state)
        self.assertEqual(1, accepted.sequence)
        with self.assertRaises(StateError) as caught:
            self._accept(state, last_sequence=accepted.sequence)
        self.assertIn("replayed", str(caught.exception))
        with self.assertRaises(StateError):
            self._accept(state, last_sequence=state.sequence)

    def test_a_last_sequence_that_is_not_an_integer_is_refused(self) -> None:
        # The comparison is the replay protection; a value that is not an
        # integer would either raise somewhere else or compare wrongly.
        for value in ("2", True, 1.5):
            with self.subTest(value=repr(value)):
                with self.assertRaises(StateError):
                    self._accept(self._signed(), last_sequence=value)

    def test_a_gap_in_the_sequence_is_accepted(self) -> None:
        # The state stream is at-least-once like the channel: "state 2 never
        # arrived" is not evidence of an attack.
        issuer = StateIssuer()
        for _ in range(2):
            issuer.issue(_body(), audience="host-a", issued_at=T0,
                         signer=_signer(MANAGER_KEY))
        newer = issuer.issue(_body(), audience="host-a", issued_at=T0,
                             signer=_signer(MANAGER_KEY))
        self.assertEqual(3, self._accept(newer, last_sequence=1).sequence)

    def test_the_body_is_a_desired_state_value(self) -> None:
        accepted = self._accept(self._signed(body={
            "schema": DOCUMENT_SCHEMA,
            "revision": 12,
            "hosts": [],
        }))
        state = accepted.state()
        self.assertIsInstance(state, DesiredState)
        self.assertEqual(12, state.revision)

    def test_accept_is_a_pure_check_and_leaves_nothing_behind(self) -> None:
        # No sequence is advanced here: the host advances it after accepting,
        # so a forged envelope cannot burn a sequence number.
        state = self._signed()
        self._accept(state)
        self._accept(state)
        self.assertEqual(1, state.sequence)


class TestTheModule(unittest.TestCase):
    ALLOWED_IMPORTS = {"__future__", "json", "re", "dataclasses", "datetime", "typing"}

    def test_the_module_imports_only_what_it_declares(self) -> None:
        import ast
        imports = set()
        tree = ast.parse(STATE_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imports.add(node.module.split(".")[0])
        self.assertEqual(self.ALLOWED_IMPORTS, imports)

    def test_the_module_never_reads_the_wall_clock(self) -> None:
        source = STATE_SOURCE.read_text(encoding="utf-8")
        for forbidden in (".now(", ".utcnow(", ".today(", "time.time(", "monotonic("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_module_has_no_way_to_execute_anything(self) -> None:
        source = STATE_SOURCE.read_text(encoding="utf-8")
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
