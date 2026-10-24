# spec: fleet-004-01, fleet-004-02, fleet-004-03, fleet-004-04, fleet-004-05
"""The outbound host-agent channel: enrollment, rotation, and signed reports.

FLEET-004 is one sentence — Phase 1 host agents initiate outbound communication
and the manager SHALL NOT require an inbound path to home-lab hosts — and it
has an architectural consequence that is easy to lose in an API layer: **the
manager never dials a host**. This module is the manager's side of that channel
as values and checks, with no transport in it at all. There is no socket, no
HTTP client, no URL, and no address anywhere in the file; the import list is
pinned by a test so "it only reads and writes documents" stays true. An agent
calls in; the manager answers. (Box 3.2 adds what an answer may contain.)

Five properties, each one a rule that fails closed:

1. **Enrollment is one-time and bound.** A token names exactly one host (and
   the pools it may serve), has a bounded lifetime, and is consumed by the
   first redemption. The host identity comes from the token, never from the
   request, so an agent cannot enroll as somebody else by asking to. A token is
   a bearer secret: it is kept out of `repr()`, has no document form, and is
   never echoed in an error.
2. **A key belongs to exactly one host.** Enrollment records the keys it has
   seen; redeeming or rotating onto a key another host already holds is refused.
   Accepting it would make one host's signature indistinguishable from
   another's, which is the whole point of the key.
3. **Every report is signed over one frozen profile.** The signed bytes are the
   canonical JSON of the envelope without its `signature` field: sorted keys,
   no whitespace, UTF-8, no NaN/Infinity. The profile is a constant, pinned
   byte for byte by a test, because a signature over "roughly this" verifies
   nothing.
4. **Replay protection is stateful and strict.** Per (host, key): the sequence
   must strictly increase, the nonce must be unused, lifetime is bounded, and
   freshness is judged against a caller-supplied instant, never the host clock.
   Gaps are accepted — the channel is at-least-once, and "message 7 never
   arrived" is not evidence of an attack. State advances only *after* the
   signature verifies, so a forged report cannot burn a sequence number.
5. **Rotation overlaps for a bounded window, revocation does not.** A rotated
   key retires at a fixed instant so a report signed just before the agent saw
   the acknowledgement still verifies; after that instant it is refused.
   Revocation refuses immediately, including a still-retiring key.

HONEST SCOPE — what this module does not decide:

- **It does not choose a signature provider.** `accept()` takes a `verifier`
  callable `(public_key: bytes, message: bytes, signature: bytes) -> bool`.
  The repository has two Ed25519 implementations and *both* are Gate-0
  non-authorizing (`hub.coherence.ed25519` is a reference implementation,
  `hub.coherence.ed25519_vetted` wraps PyCA `cryptography` but is still
  quarantined pending independent review). Wiring either as the mandatory
  verifier is a deployment decision with a security sign-off; this module is
  provider-agnostic precisely so that choice is not made by accident here, and
  the import list below has no crypto in it.
- **No transport, no session, no storage.** Nothing here opens a connection or
  persists a credential; `AgentChannel` is in-memory state that a store will
  later hold.
- **No operations.** The body is opaque to this layer; what an agent may be
  told to do is box 3.2.

The clock: every method takes an explicit timezone-aware `at`, and nothing in
the file reads the wall clock (a test reads this file and fails if that
changes). Freshness is a decision about a supplied instant, not a fact about
the process.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

CHANNEL_SCHEMA = "fleet-manager-agent-envelope/1"

# A report is useful for a short window or not at all: it carries observed
# state, and reconciling against a five-minute-old report is reconciling
# against a guess. Short enough to bound replay, long enough to survive a retry.
MAX_MESSAGE_LIFETIME = timedelta(seconds=300)
# How far ahead of the manager's instant a report may be issued. The agent and
# the manager do not share a clock; this is the size of the disagreement the
# channel tolerates, not a permission.
MAX_CLOCK_SKEW = timedelta(seconds=60)
# How long a rotated key keeps verifying. It has to outlive the round trip that
# tells the agent it was rotated, and no longer than that.
ROTATION_OVERLAP = timedelta(seconds=600)
# An enrollment token is redeemed once, by hand or by bootstrap script, soon
# after it is issued. An hour is generous.
MAX_TOKEN_LIFETIME = timedelta(seconds=3600)
# A report is a report, not an upload.
MAX_BODY_BYTES = 64 * 1024

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_NONCE = re.compile(r"^[a-z0-9-]{8,64}$")
_HEX = re.compile(r"^[0-9a-f]+$")
_PUBLIC_KEY_SIZE = 32
_SIGNATURE_SIZE = 64
_MAX_SEQUENCE = 2**63 - 1


class ChannelError(ValueError):
    """A host-agent message was refused. Names the rule, never key material."""


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    RETIRING = "retiring"
    REVOKED = "revoked"


def _identifier(value: object, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.match(value):
        raise ChannelError(f"{where}: must be a lowercase identifier")
    return value


def _timestamp(value: object, where: str) -> datetime:
    """Parse an ISO-8601 instant that carries an offset.

    A timestamp without an offset is refused rather than assumed: the same
    lesson as the desired-state model, where comparing timestamps as strings
    was correct only while every one of them shared an offset.
    """
    if not isinstance(value, str) or not value:
        raise ChannelError(f"{where}: must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ChannelError(f"{where}: is not an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ChannelError(f"{where}: must carry a UTC offset (naive is refused)")
    return parsed


def _instant(value: object, where: str) -> datetime:
    """A caller-supplied instant. Aware, and never read from the wall clock."""
    if not isinstance(value, datetime):
        raise ChannelError(f"{where}: must be a timezone-aware datetime")
    if value.tzinfo is None:
        raise ChannelError(f"{where}: must carry a UTC offset (naive is refused)")
    return value


def _stamp(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public_key(value: object, where: str) -> bytes:
    if not isinstance(value, bytes):
        raise ChannelError(f"{where}: must be bytes")
    if len(value) != _PUBLIC_KEY_SIZE:
        raise ChannelError(
            f"{where}: must be exactly {_PUBLIC_KEY_SIZE} bytes "
            f"(got {len(value)})"
        )
    return value


def key_id_for(public_key: bytes) -> str:
    """The identifier a report names. Derived from the key, so it is stable.

    Deriving it (instead of minting one) means the same key always has the same
    id on every manager, which is what makes "this key is already enrolled to
    another host" a check rather than a hope.
    """
    _public_key(public_key, "channel.public_key")
    return "key-" + hashlib.sha256(public_key).hexdigest()[:16]


def _body_json(value: object, where: str) -> str:
    """Validate an opaque body and return it in canonical form.

    The body is stored as canonical text rather than a dict: a value type that
    holds a mutable dict is not immutable, and the text is exactly what the
    signature covers.
    """
    if not isinstance(value, dict):
        raise ChannelError(f"{where}: must be an object")
    for name in value:
        if not isinstance(name, str):
            raise ChannelError(f"{where}: field names must be strings")
    try:
        text = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        raise ChannelError(
            f"{where}: must be JSON-serializable (no NaN, Infinity, or bytes)"
        ) from None
    if len(text.encode("utf-8")) > MAX_BODY_BYTES:
        raise ChannelError(f"{where}: exceeds the {MAX_BODY_BYTES}-byte limit")
    return text


@dataclass(frozen=True, slots=True, kw_only=True)
class EnrollmentToken:
    """A one-time bearer secret that binds one host to one key.

    `token_id` is left out of `repr()` on purpose: a value that prints itself
    into a log is a value that leaks itself. There is deliberately no document
    form for a token.
    """

    host_id: str
    pools: tuple[str, ...]
    issued_at: str
    expires_at: str
    token_id: str = field(repr=False)

    def __post_init__(self) -> None:
        _identifier(self.host_id, "enrollment_token.host_id")
        if not isinstance(self.pools, tuple) or not self.pools:
            raise ChannelError("enrollment_token.pools: must be a non-empty tuple")
        for index, pool in enumerate(self.pools):
            _identifier(pool, f"enrollment_token.pools[{index}]")
        if len(set(self.pools)) != len(self.pools):
            raise ChannelError("enrollment_token.pools: must not name a pool twice")
        issued = _timestamp(self.issued_at, "enrollment_token.issued_at")
        expires = _timestamp(self.expires_at, "enrollment_token.expires_at")
        if expires <= issued:
            raise ChannelError("enrollment_token.expires_at: must be after issued_at")
        if expires - issued > MAX_TOKEN_LIFETIME:
            raise ChannelError(
                "enrollment_token.expires_at: lifetime exceeds "
                f"{int(MAX_TOKEN_LIFETIME.total_seconds())}s"
            )
        if not isinstance(self.token_id, str) or not self.token_id:
            raise ChannelError("enrollment_token.token_id: must be a non-empty string")

    def expired(self, at: datetime) -> bool:
        return at > _timestamp(self.expires_at, "enrollment_token.expires_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class HostCredential:
    """One key, enrolled to one host, with its status at a given instant."""

    host_id: str
    key_id: str
    public_key: bytes = field(repr=False)
    issued_at: str
    not_after: str
    generation: int
    status: CredentialStatus = CredentialStatus.ACTIVE
    retires_at: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.host_id, "host_credential.host_id")
        _identifier(self.key_id, "host_credential.key_id")
        _public_key(self.public_key, "host_credential.public_key")
        if key_id_for(self.public_key) != self.key_id:
            raise ChannelError(
                "host_credential.key_id: does not match the public key it names"
            )
        issued = _timestamp(self.issued_at, "host_credential.issued_at")
        not_after = _timestamp(self.not_after, "host_credential.not_after")
        if not_after <= issued:
            raise ChannelError("host_credential.not_after: must be after issued_at")
        if not isinstance(self.generation, int) or isinstance(self.generation, bool):
            raise ChannelError("host_credential.generation: must be an integer")
        if self.generation < 1:
            raise ChannelError("host_credential.generation: must be 1 or greater")
        if not isinstance(self.status, CredentialStatus):
            options = ", ".join(status.value for status in CredentialStatus)
            raise ChannelError(f"host_credential.status: must be one of {options}")
        if self.status is CredentialStatus.RETIRING:
            if self.retires_at is None:
                raise ChannelError(
                    "host_credential.retires_at: a retiring credential needs the "
                    "instant it stops verifying"
                )
            _timestamp(self.retires_at, "host_credential.retires_at")
        elif self.retires_at is not None:
            raise ChannelError(
                "host_credential.retires_at: only a retiring credential carries one"
            )

    def usable_at(self, at: datetime) -> bool:
        if self.status is CredentialStatus.REVOKED:
            return False
        if at > _timestamp(self.not_after, "host_credential.not_after"):
            return False
        if self.status is CredentialStatus.RETIRING:
            return at <= _timestamp(self.retires_at, "host_credential.retires_at")
        return True


@dataclass(frozen=True, slots=True, kw_only=True)
class ChannelEnvelope:
    """One signed report from one host. The body is opaque canonical text."""

    host_id: str
    key_id: str
    sequence: int
    nonce: str
    issued_at: str
    expires_at: str
    body_json: str
    signature: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _identifier(self.host_id, "envelope.host_id")
        _identifier(self.key_id, "envelope.key_id")
        _sequence(self.sequence, "envelope.sequence")
        if not isinstance(self.nonce, str) or not _NONCE.match(self.nonce):
            raise ChannelError(
                "envelope.nonce: must be 8-64 lowercase letters, digits, or '-'"
            )
        issued = _timestamp(self.issued_at, "envelope.issued_at")
        expires = _timestamp(self.expires_at, "envelope.expires_at")
        if expires <= issued:
            raise ChannelError("envelope.expires_at: must be after issued_at")
        if expires - issued > MAX_MESSAGE_LIFETIME:
            raise ChannelError(
                "envelope.expires_at: lifetime exceeds "
                f"{int(MAX_MESSAGE_LIFETIME.total_seconds())}s"
            )
        if not isinstance(self.body_json, str) or not self.body_json:
            raise ChannelError("envelope.body_json: must be non-empty canonical text")
        try:
            re_canonical = _body_json(json.loads(self.body_json), "envelope.body_json")
        except ChannelError as exc:
            raise ChannelError(f"envelope.body_json: {exc}") from None
        except ValueError:
            raise ChannelError("envelope.body_json: is not JSON") from None
        if re_canonical != self.body_json:
            # The signature covers the canonical form. If the stored text were
            # a different spelling of the same body, the bytes a verifier
            # signed and the bytes a consumer reads would disagree.
            raise ChannelError(
                "envelope.body_json: must be canonical JSON (sorted keys, no "
                "whitespace); the signed bytes and the stored body must be the "
                "same text"
            )
        if not isinstance(self.signature, bytes):
            raise ChannelError("envelope.signature: must be bytes")
        if len(self.signature) != _SIGNATURE_SIZE:
            raise ChannelError(
                f"envelope.signature: must be exactly {_SIGNATURE_SIZE} bytes"
            )


def _sequence(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ChannelError(f"{where}: must be an integer")
    if value < 1 or value > _MAX_SEQUENCE:
        raise ChannelError(f"{where}: must be between 1 and {_MAX_SEQUENCE}")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class AcceptedReport:
    """A report that passed every check. Named as accepted, not as true."""

    host_id: str
    key_id: str
    sequence: int
    issued_at: str
    body_json: str

    def body(self) -> Any:
        return json.loads(self.body_json)


def signed_bytes(envelope: ChannelEnvelope) -> bytes:
    """The exact bytes a host signs and the manager verifies.

    Frozen profile: compact JSON, sorted keys, UTF-8, and everything except
    `signature`. `body` is already canonical text, so it is embedded as a
    parsed object to keep the outer canonicalization total.
    """
    document = {
        "schema": CHANNEL_SCHEMA,
        "host_id": envelope.host_id,
        "key_id": envelope.key_id,
        "sequence": envelope.sequence,
        "nonce": envelope.nonce,
        "issued_at": envelope.issued_at,
        "expires_at": envelope.expires_at,
        "body": json.loads(envelope.body_json),
    }
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def envelope_to_document(envelope: ChannelEnvelope) -> dict:
    """The wire form. `signature` is hex so the document is plain JSON."""
    return {
        "schema": CHANNEL_SCHEMA,
        "host_id": envelope.host_id,
        "key_id": envelope.key_id,
        "sequence": envelope.sequence,
        "nonce": envelope.nonce,
        "issued_at": envelope.issued_at,
        "expires_at": envelope.expires_at,
        "body": json.loads(envelope.body_json),
        "signature": envelope.signature.hex(),
    }


def envelope_from_document(doc: object, where: str = "envelope") -> ChannelEnvelope:
    """Parse one report. Closed shape: a missing field is named, an extra refused."""
    if not isinstance(doc, dict):
        raise ChannelError(f"{where}: must be an object")
    required = (
        "schema", "host_id", "key_id", "sequence", "nonce", "issued_at",
        "expires_at", "body", "signature",
    )
    for name in required:
        if name not in doc:
            raise ChannelError(f"{where}.{name}: is required")
    for name in doc:
        if name not in required:
            raise ChannelError(f"{where}.{name}: is not a field of an envelope")
    if doc["schema"] != CHANNEL_SCHEMA:
        raise ChannelError(
            f"{where}.schema: must be {CHANNEL_SCHEMA!r}"
        )
    signature_hex = doc["signature"]
    if not isinstance(signature_hex, str) or not _HEX.match(signature_hex):
        raise ChannelError(
            f"{where}.signature: must be a lowercase hex string"
        )
    signature = bytes.fromhex(signature_hex)
    try:
        return ChannelEnvelope(
            host_id=doc["host_id"],
            key_id=doc["key_id"],
            sequence=doc["sequence"],
            nonce=doc["nonce"],
            issued_at=doc["issued_at"],
            expires_at=doc["expires_at"],
            body_json=_body_json(doc["body"], f"{where}.body"),
            signature=signature,
        )
    except ChannelError as exc:
        raise ChannelError(f"{where}: {exc}") from None


class AgentChannel:
    """The manager's side: issued tokens, enrolled keys, and what it has seen.

    State, deliberately, and only this state. It is in memory; persistence is
    the store's job, and nothing here reads or writes a clock or a socket.
    """

    def __init__(
        self,
        *,
        rotation_overlap: timedelta = ROTATION_OVERLAP,
        credential_lifetime: timedelta = timedelta(days=90),
    ) -> None:
        if not isinstance(rotation_overlap, timedelta) or rotation_overlap <= timedelta():
            raise ChannelError("channel.rotation_overlap: must be a positive timedelta")
        if (
            not isinstance(credential_lifetime, timedelta)
            or credential_lifetime <= timedelta()
        ):
            raise ChannelError(
                "channel.credential_lifetime: must be a positive timedelta"
            )
        self._rotation_overlap = rotation_overlap
        self._credential_lifetime = credential_lifetime
        self._tokens: dict[str, EnrollmentToken] = {}
        self._consumed: set[str] = set()
        self._credentials: dict[tuple[str, str], HostCredential] = {}
        self._keys: dict[bytes, str] = {}
        self._last_sequence: dict[tuple[str, str], int] = {}
        self._nonces: dict[tuple[str, str], dict[str, datetime]] = {}

    # --- enrollment --------------------------------------------------------

    def issue_token(
        self,
        host_id: str,
        pools: tuple[str, ...],
        *,
        at: datetime,
        ttl: timedelta = timedelta(minutes=15),
        token_id: str | None = None,
    ) -> EnrollmentToken:
        """Mint a one-time token. `token_id` may be supplied so tests are exact.

        When it is not supplied the id is generated from the system CSPRNG:
        generating a bearer secret is this module's job, not the caller's, and
        a caller-chosen one repeats the moment somebody uses a counter.
        """
        instant = _instant(at, "channel.issue_token.at")
        _identifier(host_id, "channel.issue_token.host_id")
        if not isinstance(pools, tuple) or not pools:
            raise ChannelError("channel.issue_token.pools: must be a non-empty tuple")
        if not isinstance(ttl, timedelta) or ttl <= timedelta():
            raise ChannelError("channel.issue_token.ttl: must be a positive timedelta")
        if ttl > MAX_TOKEN_LIFETIME:
            raise ChannelError(
                "channel.issue_token.ttl: exceeds "
                f"{int(MAX_TOKEN_LIFETIME.total_seconds())}s"
            )
        if any(host == host_id for host, _ in self._credentials):
            # Re-enrolling a host that already holds a key would give it a
            # second identity, and the ledger would no longer say which key
            # speaks for it. Rotation is the path for that host.
            raise ChannelError(
                f"channel.issue_token: host {host_id!r} already holds a credential; "
                "rotate it, or revoke it first"
            )
        token = EnrollmentToken(
            host_id=host_id,
            pools=tuple(sorted(pools)),
            issued_at=_stamp(instant),
            expires_at=_stamp(instant + ttl),
            token_id=token_id if token_id is not None else "token-" + secrets.token_hex(16),
        )
        self._tokens[token.token_id] = token
        return token

    def enroll(self, token_id: str, public_key: bytes, *, at: datetime) -> HostCredential:
        """Redeem a token for a credential. One redemption, ever."""
        instant = _instant(at, "channel.enroll.at")
        _public_key(public_key, "channel.enroll.public_key")
        if not isinstance(token_id, str) or not token_id:
            raise ChannelError("channel.enroll.token_id: must be a non-empty string")
        if token_id in self._consumed:
            raise ChannelError(
                "channel.enroll: the enrollment token has already been used"
            )
        token = self._tokens.get(token_id)
        if token is None:
            # The value is not echoed: a token id is a bearer secret.
            raise ChannelError("channel.enroll: the enrollment token is not known")
        if token.expired(instant):
            raise ChannelError(
                "channel.enroll: the enrollment token has expired"
            )
        if instant < _timestamp(token.issued_at, "enrollment_token.issued_at"):
            raise ChannelError(
                "channel.enroll: the token cannot be redeemed before it was issued"
            )
        holder = self._keys.get(public_key)
        if holder is not None:
            raise ChannelError(
                "channel.enroll: this public key is already enrolled "
                f"(to host {holder!r}); a key identifies one host"
            )
        credential = HostCredential(
            host_id=token.host_id,
            key_id=key_id_for(public_key),
            public_key=public_key,
            issued_at=_stamp(instant),
            not_after=_stamp(instant + self._credential_lifetime),
            generation=1,
        )
        self._tokens.pop(token_id, None)
        self._consumed.add(token_id)
        self._credentials[(credential.host_id, credential.key_id)] = credential
        self._keys[public_key] = credential.host_id
        return credential

    # --- rotation and revocation ------------------------------------------

    def rotate(
        self, host_id: str, key_id: str, public_key: bytes, *, at: datetime
    ) -> tuple[HostCredential, HostCredential]:
        """Return (the new active credential, the old one, now retiring).

        The old key keeps verifying until `retires_at`, because the report in
        flight when the rotation happened was signed before the agent could
        know about it. After that instant it is refused, not forgotten.
        """
        instant = _instant(at, "channel.rotate.at")
        _public_key(public_key, "channel.rotate.public_key")
        current = self.credential(host_id, key_id, where="channel.rotate")
        if current.status is CredentialStatus.REVOKED:
            raise ChannelError(
                "channel.rotate: a revoked credential cannot be rotated; enroll a "
                "new token for this host"
            )
        if current.status is not CredentialStatus.ACTIVE:
            raise ChannelError(
                "channel.rotate: only the active credential can be rotated "
                f"(this one is {current.status.value})"
            )
        if instant < _timestamp(current.issued_at, "host_credential.issued_at"):
            raise ChannelError(
                "channel.rotate: cannot rotate before the credential was issued"
            )
        if public_key == current.public_key:
            raise ChannelError(
                "channel.rotate: the new key is the current key; a rotation that "
                "changes nothing must not silently re-authorize it"
            )
        holder = self._keys.get(public_key)
        if holder is not None:
            raise ChannelError(
                "channel.rotate: this public key is already enrolled "
                f"(to host {holder!r}); a key identifies one host"
            )
        retiring = HostCredential(
            host_id=current.host_id,
            key_id=current.key_id,
            public_key=current.public_key,
            issued_at=current.issued_at,
            not_after=current.not_after,
            generation=current.generation,
            status=CredentialStatus.RETIRING,
            retires_at=_stamp(instant + self._rotation_overlap),
        )
        active = HostCredential(
            host_id=current.host_id,
            key_id=key_id_for(public_key),
            public_key=public_key,
            issued_at=_stamp(instant),
            not_after=_stamp(instant + self._credential_lifetime),
            generation=current.generation + 1,
        )
        self._credentials[(retiring.host_id, retiring.key_id)] = retiring
        self._credentials[(active.host_id, active.key_id)] = active
        self._keys[public_key] = active.host_id
        return active, retiring

    def revoke(self, host_id: str, key_id: str, *, at: datetime) -> HostCredential:
        """Refuse this key from this instant, with no overlap."""
        instant = _instant(at, "channel.revoke.at")
        current = self.credential(host_id, key_id, where="channel.revoke")
        if current.status is CredentialStatus.REVOKED:
            raise ChannelError(
                "channel.revoke: this credential is already revoked"
            )
        if instant < _timestamp(current.issued_at, "host_credential.issued_at"):
            raise ChannelError(
                "channel.revoke: cannot revoke before the credential was issued"
            )
        revoked = HostCredential(
            host_id=current.host_id,
            key_id=current.key_id,
            public_key=current.public_key,
            issued_at=current.issued_at,
            not_after=current.not_after,
            generation=current.generation,
            status=CredentialStatus.REVOKED,
        )
        self._credentials[(revoked.host_id, revoked.key_id)] = revoked
        return revoked

    def credential(
        self, host_id: str, key_id: str, *, where: str = "channel.credential"
    ) -> HostCredential:
        _identifier(host_id, f"{where}.host_id")
        _identifier(key_id, f"{where}.key_id")
        found = self._credentials.get((host_id, key_id))
        if found is None:
            raise ChannelError(
                f"{where}: no credential for host {host_id!r} and key {key_id!r}"
            )
        return found

    def active(self, host_id: str) -> HostCredential:
        _identifier(host_id, "channel.active.host_id")
        active = [
            credential
            for (host, _), credential in self._credentials.items()
            if host == host_id and credential.status is CredentialStatus.ACTIVE
        ]
        if not active:
            raise ChannelError(f"channel.active: host {host_id!r} has no active credential")
        if len(active) > 1:
            raise ChannelError(
                f"channel.active: host {host_id!r} has {len(active)} active "
                "credentials; the ledger must name exactly one"
            )
        return active[0]

    # --- reports -----------------------------------------------------------

    def accept(
        self,
        envelope: ChannelEnvelope,
        *,
        at: datetime,
        verifier: Callable[[bytes, bytes, bytes], bool],
    ) -> AcceptedReport:
        """Verify one report and record it as seen.

        Checks run cheapest-first, and the replay state is committed last: a
        forged report must not be able to use up a sequence number or a nonce.
        """
        instant = _instant(at, "channel.accept.at")
        if not isinstance(envelope, ChannelEnvelope):
            raise ChannelError("channel.accept: must be a ChannelEnvelope")
        if not callable(verifier):
            raise ChannelError("channel.accept: verifier must be callable")
        credential = self.credential(
            envelope.host_id, envelope.key_id, where="channel.accept"
        )
        if not credential.usable_at(instant):
            raise ChannelError(
                "channel.accept: the credential is not usable at this instant "
                f"(status {credential.status.value}, key {credential.key_id!r})"
            )
        issued = _timestamp(envelope.issued_at, "envelope.issued_at")
        expires = _timestamp(envelope.expires_at, "envelope.expires_at")
        if instant >= expires:
            raise ChannelError("channel.accept: the report has expired")
        if instant < issued - MAX_CLOCK_SKEW:
            raise ChannelError(
                "channel.accept: the report is issued in the future beyond the "
                f"{int(MAX_CLOCK_SKEW.total_seconds())}s clock skew"
            )
        try:
            verified = verifier(
                credential.public_key, signed_bytes(envelope), envelope.signature
            )
        except Exception as exc:  # a foreign provider must not crash the channel
            raise ChannelError(
                "channel.accept: the signature provider refused the report "
                f"({type(exc).__name__}); the channel does not fall back"
            ) from None
        if verified is not True:
            raise ChannelError("channel.accept: the signature does not verify")
        identity = (envelope.host_id, envelope.key_id)
        last = self._last_sequence.get(identity)
        if last is not None and envelope.sequence <= last:
            raise ChannelError(
                "channel.accept: the sequence is not new "
                f"(last accepted {last}, this report says {envelope.sequence}); "
                "a replay or a reordered report is refused, not delivered"
            )
        seen = self._nonces.setdefault(identity, {})
        for nonce, expiry in list(seen.items()):
            if expiry < instant:
                del seen[nonce]
        if envelope.nonce in seen:
            raise ChannelError(
                "channel.accept: the nonce was already used under a later sequence; "
                "a sequence that invented a nonce is not a report this channel trusts"
            )
        # Commit only now, after the signature and every check.
        self._last_sequence[identity] = envelope.sequence
        seen[envelope.nonce] = expires
        return AcceptedReport(
            host_id=envelope.host_id,
            key_id=envelope.key_id,
            sequence=envelope.sequence,
            issued_at=envelope.issued_at,
            body_json=envelope.body_json,
        )

    # --- introspection -----------------------------------------------------

    def last_sequence(self, host_id: str, key_id: str) -> int | None:
        return self._last_sequence.get((host_id, key_id))
