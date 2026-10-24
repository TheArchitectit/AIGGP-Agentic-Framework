# spec: fleet-004-01, fleet-004-02, fleet-004-03, fleet-004-04, fleet-004-05
"""The outbound host-agent channel (FLEET-004, Sprint 3.1).

The suite is built from the failures the channel exists to prevent:

- a host agent that enrolls as a different host, or re-enrolls forever;
- a key that speaks for two hosts, so one host's signature is another's;
- a report whose signature verifies over bytes nobody agreed on;
- a captured report replayed, reordered, or kept alive past its window;
- a forged report that still uses up a sequence number or a nonce;
- an outbound connection from the manager, which FLEET-004 forbids.

The verifier here is a deterministic test double: this slice owns the protocol
(which key, which bytes, which checks, in what order), not the curve. The two
Ed25519 implementations in this repository are Gate-0 non-authorizing, so
picking one as the mandatory verifier is a security decision with a sign-off,
not something a module should do by default.
"""
import ast
import hashlib
import json
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager.channel import (  # noqa: E402
    CHANNEL_SCHEMA,
    MAX_BODY_BYTES,
    MAX_MESSAGE_LIFETIME,
    AgentChannel,
    ChannelEnvelope,
    ChannelError,
    CredentialStatus,
    envelope_from_document,
    envelope_to_document,
    key_id_for,
    signed_bytes,
)

EXPECTED_TEST_COUNT = 51

CHANNEL_SOURCE = PKG_ROOT / "fleet_manager" / "channel.py"
T0 = datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)


# --- test double for the provider interface --------------------------------


def _key(seed: int) -> bytes:
    return bytes([seed]) * 32


def _sign(public_key: bytes, message: bytes) -> bytes:
    """Deterministic, 64-byte, and derived from both inputs.

    Not cryptography: a protocol double. It fails for the right reasons here
    (wrong key, changed bytes) and makes no claim about signatures in general.
    """
    return hashlib.sha512(public_key + message).digest()


def _verifier(public_key: bytes, message: bytes, signature: bytes) -> bool:
    return signature == _sign(public_key, message)


def _body(value: dict) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _stamp(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ChannelCase(unittest.TestCase):
    """Shared setup: one enrolled host, and a way to build a signed report."""

    def enrolled(
        self,
        host: str = "ucs03",
        pools: tuple[str, ...] = ("phase1-linux",),
        seed: int = 1,
        channel: AgentChannel | None = None,
        at: datetime = T0,
    ):
        channel = channel if channel is not None else AgentChannel()
        token = channel.issue_token(host, pools, at=at, token_id=f"token-{host}")
        credential = channel.enroll(token.token_id, _key(seed), at=at)
        return channel, credential

    def envelope(
        self,
        credential,
        *,
        sequence: int = 1,
        nonce: str = "nonce-0001",
        at: datetime = T0,
        body: dict | None = None,
        sign_with: bytes | None = None,
        host_id: str | None = None,
        issued_offset: int = 0,
        lifetime: int = 300,
    ) -> ChannelEnvelope:
        issued = at + timedelta(seconds=issued_offset)
        unsigned = ChannelEnvelope(
            host_id=host_id or credential.host_id,
            key_id=credential.key_id,
            sequence=sequence,
            nonce=nonce,
            issued_at=_stamp(issued),
            expires_at=_stamp(issued + timedelta(seconds=lifetime)),
            body_json=_body(body if body is not None else {"observed_at": _stamp(issued)}),
            signature=bytes(64),
        )
        key = sign_with if sign_with is not None else credential.public_key
        return replace(unsigned, signature=_sign(key, signed_bytes(unsigned)))


class TestEnrollment(ChannelCase):
    """fleet-004-02: a token binds one host, is used once, and expires."""

    def test_a_token_enrolls_a_host_with_an_active_credential(self) -> None:
        channel, credential = self.enrolled()
        self.assertEqual("ucs03", credential.host_id)
        self.assertIs(CredentialStatus.ACTIVE, credential.status)
        self.assertEqual(1, credential.generation)
        self.assertEqual(credential.key_id, channel.active("ucs03").key_id)

    def test_a_token_cannot_be_redeemed_twice(self) -> None:
        channel, _ = self.enrolled()
        with self.assertRaises(ChannelError) as caught:
            channel.enroll("token-ucs03", _key(2), at=T0)
        self.assertIn("already been used", str(caught.exception))

    def test_an_unknown_token_is_refused_without_echoing_it(self) -> None:
        channel = AgentChannel()
        with self.assertRaises(ChannelError) as caught:
            channel.enroll("token-not-minted", _key(1), at=T0)
        self.assertIn("not known", str(caught.exception))
        self.assertNotIn("token-not-minted", str(caught.exception))

    def test_an_expired_token_is_refused(self) -> None:
        channel = AgentChannel()
        token = channel.issue_token(
            "ucs03", ("phase1-linux",), at=T0, ttl=timedelta(minutes=5),
            token_id="token-ucs03",
        )
        with self.assertRaises(ChannelError) as caught:
            channel.enroll(token.token_id, _key(1), at=T0 + timedelta(minutes=6))
        self.assertIn("expired", str(caught.exception))

    def test_a_token_cannot_be_redeemed_before_it_was_issued(self) -> None:
        channel = AgentChannel()
        token = channel.issue_token(
            "ucs03", ("phase1-linux",), at=T0, token_id="token-ucs03"
        )
        with self.assertRaises(ChannelError) as caught:
            channel.enroll(token.token_id, _key(1), at=T0 - timedelta(minutes=1))
        self.assertIn("before it was issued", str(caught.exception))

    def test_a_public_key_already_enrolled_is_refused_and_names_the_host(self) -> None:
        channel, _ = self.enrolled(host="ucs03", seed=1)
        token = channel.issue_token(
            "ucs04", ("phase1-linux",), at=T0, token_id="token-ucs04"
        )
        with self.assertRaises(ChannelError) as caught:
            channel.enroll(token.token_id, _key(1), at=T0)
        message = str(caught.exception)
        self.assertIn("already enrolled", message)
        self.assertIn("ucs03", message)

    def test_enrollment_refuses_a_key_that_is_not_32_bytes(self) -> None:
        channel = AgentChannel()
        channel.issue_token("ucs03", ("phase1-linux",), at=T0, token_id="t")
        cases = (
            (b"", "32 bytes"),
            (b"x" * 31, "32 bytes"),
            (b"x" * 33, "32 bytes"),
            ("x" * 32, "must be bytes"),
            (None, "must be bytes"),
        )
        for bad, expected in cases:
            with self.subTest(kind=type(bad).__name__):
                with self.assertRaises(ChannelError) as caught:
                    channel.enroll("t", bad, at=T0)
                self.assertIn(expected, str(caught.exception))


class TestTokenLifetimes(ChannelCase):
    def test_issuing_a_token_refuses_a_lifetime_over_the_maximum(self) -> None:
        channel = AgentChannel()
        with self.assertRaises(ChannelError) as caught:
            channel.issue_token(
                "ucs03", ("phase1-linux",), at=T0, ttl=timedelta(hours=2)
            )
        self.assertIn("exceeds", str(caught.exception))

    def test_issuing_a_token_refuses_a_host_that_already_holds_a_credential(self) -> None:
        channel, _ = self.enrolled()
        with self.assertRaises(ChannelError) as caught:
            channel.issue_token("ucs03", ("phase1-linux",), at=T0)
        self.assertIn("already holds a credential", str(caught.exception))

    def test_a_generated_token_id_is_random_and_out_of_repr(self) -> None:
        channel = AgentChannel()
        first = channel.issue_token("ucs03", ("phase1-linux",), at=T0)
        second = channel.issue_token("ucs04", ("phase1-linux",), at=T0)
        self.assertRegex(first.token_id, r"^token-[0-9a-f]{32}$")
        self.assertNotEqual(first.token_id, second.token_id)
        # A bearer secret that prints itself into a log leaks itself.
        self.assertNotIn(first.token_id, repr(first))
        self.assertNotIn(first.token_id, str(first))


class TestRotation(ChannelCase):
    """fleet-004-05: rotation overlaps for a bounded window, then refuses."""

    def test_rotation_activates_the_new_key_and_retires_the_old_for_a_window(
        self,
    ) -> None:
        channel, current = self.enrolled()
        active, retiring = channel.rotate(
            "ucs03", current.key_id, _key(2), at=T0 + timedelta(minutes=1)
        )
        self.assertIs(CredentialStatus.ACTIVE, active.status)
        self.assertEqual(2, active.generation)
        self.assertIs(CredentialStatus.RETIRING, retiring.status)
        self.assertEqual(current.key_id, retiring.key_id)
        self.assertEqual(
            _stamp(T0 + timedelta(minutes=11)), retiring.retires_at
        )
        self.assertEqual(active.key_id, channel.active("ucs03").key_id)

    def test_a_retiring_key_verifies_until_its_window_closes_then_it_does_not(
        self,
    ) -> None:
        channel, current = self.enrolled()
        rotated_at = T0 + timedelta(minutes=1)
        channel.rotate("ucs03", current.key_id, _key(2), at=rotated_at)
        inside = rotated_at + timedelta(minutes=5)
        report = self.envelope(current, at=inside, sequence=1)
        self.assertEqual("ucs03", channel.accept(report, at=inside, verifier=_verifier).host_id)
        after = rotated_at + timedelta(minutes=11)
        late = self.envelope(current, at=after, sequence=2)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(late, at=after, verifier=_verifier)
        self.assertIn("not usable", str(caught.exception))

    def test_a_credential_is_not_usable_past_its_absolute_lifetime(self) -> None:
        # Rotation overlap is bounded relative to the rotation; a credential
        # is also bounded absolutely, and the two are separate clocks.
        channel = AgentChannel(credential_lifetime=timedelta(hours=1))
        token = channel.issue_token("ucs03", ("phase1-linux",), at=T0, token_id="t")
        credential = channel.enroll(token.token_id, _key(1), at=T0)
        just_inside = T0 + timedelta(minutes=59)
        channel.accept(self.envelope(credential, at=just_inside),
                       at=just_inside, verifier=_verifier)
        just_after = T0 + timedelta(hours=1, seconds=1)
        report = self.envelope(credential, sequence=2, nonce="nonce-0002", at=just_after)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=just_after, verifier=_verifier)
        self.assertIn("not usable", str(caught.exception))

    def test_rotation_to_the_same_key_is_refused(self) -> None:
        channel, current = self.enrolled()
        with self.assertRaises(ChannelError) as caught:
            channel.rotate("ucs03", current.key_id, current.public_key, at=T0)
        self.assertIn("the new key is the current key", str(caught.exception))

    def test_a_revoked_credential_cannot_be_rotated(self) -> None:
        channel, current = self.enrolled()
        channel.revoke("ucs03", current.key_id, at=T0)
        with self.assertRaises(ChannelError) as caught:
            channel.rotate("ucs03", current.key_id, _key(2), at=T0)
        self.assertIn("revoked", str(caught.exception))

    def test_rotation_onto_a_key_enrolled_elsewhere_is_refused(self) -> None:
        channel, current = self.enrolled(host="ucs03", seed=1)
        token = channel.issue_token("ucs04", ("phase1-linux",), at=T0, token_id="t4")
        channel.enroll(token.token_id, _key(2), at=T0)
        with self.assertRaises(ChannelError) as caught:
            channel.rotate("ucs03", current.key_id, _key(2), at=T0)
        self.assertIn("already enrolled", str(caught.exception))

    def test_rotation_refuses_a_key_that_is_not_the_active_one(self) -> None:
        channel, current = self.enrolled()
        active, retiring = channel.rotate("ucs03", current.key_id, _key(2), at=T0)
        with self.assertRaises(ChannelError) as caught:
            channel.rotate("ucs03", retiring.key_id, _key(3), at=T0)
        self.assertIn("only the active credential", str(caught.exception))
        self.assertEqual(2, channel.active("ucs03").generation)


class TestRevocation(ChannelCase):
    def test_revocation_refuses_the_active_key_immediately(self) -> None:
        channel, current = self.enrolled()
        channel.revoke("ucs03", current.key_id, at=T0)
        report = self.envelope(current)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=_verifier)
        self.assertIn("not usable", str(caught.exception))

    def test_revocation_refuses_a_retiring_key_immediately(self) -> None:
        channel, current = self.enrolled()
        channel.rotate("ucs03", current.key_id, _key(2), at=T0)
        channel.revoke("ucs03", current.key_id, at=T0 + timedelta(seconds=1))
        at = T0 + timedelta(seconds=2)
        report = self.envelope(current, at=at)
        with self.assertRaises(ChannelError):
            channel.accept(report, at=at, verifier=_verifier)

    def test_a_revoked_key_cannot_be_enrolled_again_anywhere(self) -> None:
        # Revocation that frees the key for re-enrollment is not revocation.
        channel, current = self.enrolled(host="ucs03", seed=1)
        channel.revoke("ucs03", current.key_id, at=T0)
        token = channel.issue_token("ucs04", ("phase1-linux",), at=T0, token_id="t4")
        with self.assertRaises(ChannelError) as caught:
            channel.enroll(token.token_id, _key(1), at=T0)
        self.assertIn("already enrolled", str(caught.exception))

    def test_revoking_twice_is_refused(self) -> None:
        channel, current = self.enrolled()
        channel.revoke("ucs03", current.key_id, at=T0)
        with self.assertRaises(ChannelError) as caught:
            channel.revoke("ucs03", current.key_id, at=T0)
        self.assertIn("already revoked", str(caught.exception))


class TestSignature(ChannelCase):
    """fleet-004-03: one frozen canonical profile, verified before anything else."""

    def test_a_signed_report_is_accepted_and_returns_its_body(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current, body={"observed_at": _stamp(T0), "runners": 2})
        accepted = channel.accept(report, at=T0, verifier=_verifier)
        self.assertEqual("ucs03", accepted.host_id)
        self.assertEqual(1, accepted.sequence)
        self.assertEqual({"observed_at": _stamp(T0), "runners": 2}, accepted.body())
        self.assertEqual(1, channel.last_sequence("ucs03", current.key_id))

    def test_a_forged_report_is_refused_and_does_not_consume_its_sequence(self) -> None:
        channel, current = self.enrolled()
        genuine = self.envelope(current, sequence=5)
        forged = replace(genuine, signature=bytes(64))
        with self.assertRaises(ChannelError) as caught:
            channel.accept(forged, at=T0, verifier=_verifier)
        self.assertIn("does not verify", str(caught.exception))
        # If the forgery had advanced the replay state, this would be refused.
        self.assertIsNone(channel.last_sequence("ucs03", current.key_id))
        self.assertEqual(5, channel.accept(genuine, at=T0, verifier=_verifier).sequence)

    def test_a_report_for_an_unknown_key_is_refused(self) -> None:
        channel, current = self.enrolled()
        report = replace(self.envelope(current), key_id="key-" + "0" * 16)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=_verifier)
        self.assertIn("no credential", str(caught.exception))

    def test_a_report_signed_by_a_key_of_another_host_is_refused(self) -> None:
        channel, current = self.enrolled(host="ucs03", seed=1)
        token = channel.issue_token("ucs04", ("phase1-linux",), at=T0, token_id="t4")
        other = channel.enroll(token.token_id, _key(9), at=T0)
        # The envelope names ucs03's key, but it is signed with ucs04's.
        report = self.envelope(current, sign_with=other.public_key)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=_verifier)
        self.assertIn("does not verify", str(caught.exception))

    def test_a_verifier_that_raises_is_a_refusal_not_a_crash(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current)

        def broken(public_key, message, signature):
            raise RuntimeError("provider is unavailable")

        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=broken)
        message = str(caught.exception)
        self.assertIn("provider refused", message)
        self.assertIn("does not fall back", message)
        self.assertIsNone(channel.last_sequence("ucs03", current.key_id))

    def test_a_verifier_returning_a_truthy_non_bool_is_refused(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=lambda *a: 1)
        self.assertIn("does not verify", str(caught.exception))

    def test_the_signed_bytes_are_the_frozen_canonical_profile(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current, body={"b": 2, "a": 1})
        expected = (
            b'{"body":{"a":1,"b":2},"expires_at":"2026-10-24T06:05:00Z",'
            b'"host_id":"ucs03","issued_at":"2026-10-24T06:00:00Z",'
            b'"key_id":"' + current.key_id.encode() + b'",'
            b'"nonce":"nonce-0001","schema":"fleet-manager-agent-envelope/1",'
            b'"sequence":1}'
        )
        self.assertEqual(expected, signed_bytes(report))
        # Sorted keys, no whitespace, and stable across construction paths.
        self.assertEqual(signed_bytes(report), signed_bytes(replace(report)))

    def test_the_signed_bytes_exclude_the_signature(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current)
        other = replace(report, signature=bytes([7]) * 64)
        self.assertEqual(signed_bytes(report), signed_bytes(other))
        self.assertNotIn(b"signature", signed_bytes(report))


class TestReplay(ChannelCase):
    """fleet-004-04: strict sequence, unique nonce, bounded lifetime, fresh."""

    def test_the_same_report_twice_is_refused_as_a_replay(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current)
        channel.accept(report, at=T0, verifier=_verifier)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=_verifier)
        self.assertIn("not new", str(caught.exception))

    def test_a_lower_sequence_is_refused(self) -> None:
        channel, current = self.enrolled()
        channel.accept(self.envelope(current, sequence=5, nonce="nonce-0005"),
                       at=T0, verifier=_verifier)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(self.envelope(current, sequence=4, nonce="nonce-0004"),
                           at=T0, verifier=_verifier)
        self.assertIn("not new", str(caught.exception))

    def test_a_gap_in_the_sequence_is_accepted(self) -> None:
        # At-least-once: a report that never arrived is not an attack, and
        # refusing the next one would turn packet loss into an outage.
        channel, current = self.enrolled()
        channel.accept(self.envelope(current, sequence=1, nonce="nonce-0001"),
                       at=T0, verifier=_verifier)
        accepted = channel.accept(
            self.envelope(current, sequence=7, nonce="nonce-0007"),
            at=T0, verifier=_verifier,
        )
        self.assertEqual(7, accepted.sequence)
        self.assertEqual(7, channel.last_sequence("ucs03", current.key_id))

    def test_a_new_sequence_reusing_a_nonce_is_refused(self) -> None:
        channel, current = self.enrolled()
        channel.accept(self.envelope(current, sequence=1, nonce="nonce-0001"),
                       at=T0, verifier=_verifier)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(self.envelope(current, sequence=2, nonce="nonce-0001"),
                           at=T0, verifier=_verifier)
        self.assertIn("nonce was already used", str(caught.exception))

    def test_a_report_older_than_its_lifetime_is_refused(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current)
        late = T0 + MAX_MESSAGE_LIFETIME + timedelta(seconds=1)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=late, verifier=_verifier)
        self.assertIn("expired", str(caught.exception))

    def test_a_report_issued_beyond_the_clock_skew_is_refused(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current, issued_offset=120)
        with self.assertRaises(ChannelError) as caught:
            channel.accept(report, at=T0, verifier=_verifier)
        self.assertIn("clock skew", str(caught.exception))

    def test_a_report_whose_lifetime_exceeds_the_maximum_is_refused(self) -> None:
        channel, current = self.enrolled()
        with self.assertRaises(ChannelError) as caught:
            ChannelEnvelope(
                host_id="ucs03", key_id=current.key_id, sequence=1,
                nonce="nonce-0001", issued_at=_stamp(T0),
                expires_at=_stamp(T0 + timedelta(seconds=301)),
                body_json=_body({}), signature=bytes(64),
            )
        self.assertIn("lifetime exceeds", str(caught.exception))

    def test_replay_state_is_per_key_so_rotation_starts_a_fresh_sequence(self) -> None:
        channel, current = self.enrolled()
        channel.accept(self.envelope(current, sequence=9, nonce="nonce-0009"),
                       at=T0, verifier=_verifier)
        active, _ = channel.rotate("ucs03", current.key_id, _key(2), at=T0)
        # Sequence 1 under the new key is new state, not a regression.
        at = T0 + timedelta(seconds=1)
        accepted = channel.accept(
            self.envelope(active, sequence=1, nonce="nonce-0001", at=at),
            at=at, verifier=_verifier,
        )
        self.assertEqual(1, accepted.sequence)
        self.assertEqual(9, channel.last_sequence("ucs03", current.key_id))


class TestDocuments(ChannelCase):
    """A report is data on a wire, so its form is closed in both directions."""

    def test_an_envelope_round_trips(self) -> None:
        channel, current = self.enrolled()
        report = self.envelope(current, body={"runners": [], "observed_at": _stamp(T0)})
        document = envelope_to_document(report)
        self.assertEqual(CHANNEL_SCHEMA, document["schema"])
        self.assertEqual(report, envelope_from_document(document))
        self.assertEqual(document, envelope_to_document(envelope_from_document(document)))

    def test_a_missing_field_is_named(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        del document["nonce"]
        with self.assertRaises(ChannelError) as caught:
            envelope_from_document(document)
        self.assertIn("nonce", str(caught.exception))

    def test_an_unknown_field_is_refused(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        document["token"] = "secret-looking"
        with self.assertRaises(ChannelError) as caught:
            envelope_from_document(document)
        self.assertIn("token", str(caught.exception))
        self.assertNotIn("secret-looking", str(caught.exception))

    def test_a_signature_that_is_not_hex_is_refused(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        for bad in ("zz" * 64, "AB" * 32, str(document["signature"]) + " ", 7):
            with self.subTest(kind=type(bad).__name__):
                document["signature"] = bad
                with self.assertRaises(ChannelError) as caught:
                    envelope_from_document(document)
                self.assertIn("hex", str(caught.exception))

    def test_a_schema_other_than_v1_is_refused(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        document["schema"] = "fleet-manager-agent-envelope/2"
        with self.assertRaises(ChannelError) as caught:
            envelope_from_document(document)
        self.assertIn("schema", str(caught.exception))

    def test_a_body_that_is_not_an_object_is_refused(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        for bad in ([], "body", 7, None):
            with self.subTest(kind=type(bad).__name__):
                document["body"] = bad
                with self.assertRaises(ChannelError) as caught:
                    envelope_from_document(document)
                self.assertIn("body", str(caught.exception))

    def test_a_body_carrying_nan_is_refused(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        document["body"] = {"value": float("nan")}
        with self.assertRaises(ChannelError) as caught:
            envelope_from_document(document)
        self.assertIn("JSON-serializable", str(caught.exception))

    def test_a_body_that_is_not_canonical_text_is_refused(self) -> None:
        # The signature covers the canonical bytes; a stored body spelled
        # differently would be a different document than the one signed.
        channel, current = self.enrolled()
        report = self.envelope(current)
        with self.assertRaises(ChannelError) as caught:
            replace(report, body_json='{"observed_at": "2026-10-24T06:00:00Z"}')
        self.assertIn("canonical", str(caught.exception))
        with self.assertRaises(ChannelError) as caught:
            replace(report, body_json='{"b":1,"a":2}')
        self.assertIn("canonical", str(caught.exception))

    def test_a_body_over_the_size_limit_is_refused(self) -> None:
        channel, current = self.enrolled()
        document = envelope_to_document(self.envelope(current))
        document["body"] = {"padding": "x" * (MAX_BODY_BYTES + 1)}
        with self.assertRaises(ChannelError) as caught:
            envelope_from_document(document)
        self.assertIn("limit", str(caught.exception))

    def test_a_non_document_is_refused_not_crashed_on(self) -> None:
        for hostile in (None, "report", [], 7, b"{}"):
            with self.subTest(kind=type(hostile).__name__):
                with self.assertRaises(ChannelError):
                    envelope_from_document(hostile)


class TestTheChannelHasNoTransport(ChannelCase):
    """fleet-004-01: the manager never initiates. Tested against the source."""

    ALLOWED_IMPORTS = {
        "__future__", "hashlib", "json", "re", "secrets",
        "dataclasses", "datetime", "enum", "typing",
    }

    def test_the_module_imports_only_what_it_declares(self) -> None:
        # No socket, no urllib, no http, no requests, and no crypto provider:
        # an import added here changes what the channel is allowed to be.
        imports = set()
        tree = ast.parse(CHANNEL_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imports.add(node.module.split(".")[0])
        self.assertEqual(self.ALLOWED_IMPORTS, imports)

    def test_the_module_never_reads_the_wall_clock(self) -> None:
        source = CHANNEL_SOURCE.read_text(encoding="utf-8")
        for forbidden in (".now(", ".utcnow(", ".today(", "time.time(", "monotonic("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_key_id_is_derived_from_the_key(self) -> None:
        self.assertEqual(key_id_for(_key(1)), key_id_for(_key(1)))
        self.assertNotEqual(key_id_for(_key(1)), key_id_for(_key(2)))
        self.assertRegex(key_id_for(_key(1)), r"^key-[0-9a-f]{16}$")
        with self.assertRaises(ChannelError):
            key_id_for(b"short")


class TestSuiteFloor(unittest.TestCase):
    def test_this_suite_runs_all_of_its_tests(self) -> None:
        discovered = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        self.assertEqual(EXPECTED_TEST_COUNT, discovered.countTestCases())


if __name__ == "__main__":
    unittest.main()
