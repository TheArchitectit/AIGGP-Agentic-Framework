# spec: fleet-006-01, fleet-006-02, fleet-006-03, fleet-006-04
"""The manager's signed desired state: what a host is asked to become.

This is the other direction from `channel`. There, a host signs a report and
the manager checks it; here, the manager signs a desired state and the host
checks it. The pull model needs both halves: an agent calls in, and the answer
is a document the agent can refuse.

The requirement this implements is the security control list, verbatim:
"replay protection on desired-state envelopes and action requests" and "signed
configuration with revision, audience, expiry, and nonce or monotonic sequence".
Sprint 3's exit — "two test hosts reconcile signed no-op desired state;
compromised/replayed commands fail closed" — is that control exercised, not
described. So the envelope carries exactly those fields and nothing else:

- **audience** — one host. State for one host is not state for another; a
  document that can be redirected at a different audience is a privilege
  escalation with a signature on it.
- **revision** — which complete world this is (`DesiredState.revision`).
- **sequence** — strictly increasing per audience, so a captured state cannot
  be played back later.
- **issued_at / expires_at** — bounded lifetime, freshness judged against a
  supplied instant, never the wall clock.
- **signature** — over one frozen canonical profile, the same discipline as
  the channel: sorted keys, compact, UTF-8, no NaN. The body is stored as that
  exact text so the signed bytes and the consumed document cannot disagree.

The body is a desired-state document, not a command. That is deliberate: the
host reconciles toward the state; the host does not execute it. There is no
field here that could carry a shell instruction, and the operations that would
change a host are the typed, allowlisted ones from `operations` with their own
receipts.

The signature provider is injected, for the same reason as in `channel`: both
Ed25519 implementations in this repository are Gate-0 non-authorizing, so
choosing one is a security decision with a sign-off, not a module default. The
manager signs with a `signer(message) -> bytes` supplied by the caller, and a
host verifies with a `verifier(public_key, message, signature) -> bool`. A
provider that raises is a refusal with no fallback, and only exactly `True`
verifies.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from .channel import _identifier, _instant, _stamp, _timestamp
from .documents import from_document
from .model import DesiredState

STATE_SCHEMA = "fleet-manager-signed-state/1"

# Desired state is configuration, not a status: a host may fetch it, lose the
# network, and keep converging toward it. An hour is long enough to survive a
# retry and a reboot and short enough that a captured envelope expires.
MAX_STATE_LIFETIME = timedelta(seconds=3600)
# The same disagreement the channel tolerates between two clocks.
MAX_STATE_CLOCK_SKEW = timedelta(seconds=60)
# A whole desired state, not a status report.
MAX_STATE_BODY_BYTES = 256 * 1024

_HEX = re.compile(r"^[0-9a-f]+$")
_MAX_SEQUENCE = 2**63 - 1


class StateError(ValueError):
    """A signed-state envelope was refused. Names the rule, never key material."""


def _body_json(value: object, where: str) -> str:
    """Canonical text of a desired-state document, or a refusal.

    Stored as text rather than a dict for the same reason as the channel's
    body: the text is exactly what the signature covers, and a value type that
    holds a mutable dict is not immutable.
    """
    if not isinstance(value, dict):
        raise StateError(f"{where}: must be an object")
    for name in value:
        if not isinstance(name, str):
            raise StateError(f"{where}: field names must be strings")
    try:
        text = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        raise StateError(
            f"{where}: must be JSON-serializable (no NaN, Infinity, or bytes)"
        ) from None
    if len(text.encode("utf-8")) > MAX_STATE_BODY_BYTES:
        raise StateError(f"{where}: exceeds the {MAX_STATE_BODY_BYTES}-byte limit")
    return text


def _document_body(text: object, where: str) -> str:
    """A body that is already canonical text must also be a desired state."""
    if not isinstance(text, str) or not text:
        raise StateError(f"{where}: must be canonical JSON text")
    try:
        parsed = json.loads(text)
    except ValueError:
        raise StateError(f"{where}: is not JSON text") from None
    canonical = _body_json(parsed, where)
    if canonical != text:
        raise StateError(f"{where}: is not the canonical form of its document")
    try:
        from_document(parsed)
    except ValueError as exc:
        raise StateError(f"{where}: is not a desired-state document ({exc})") from None
    return text


@dataclass(frozen=True, slots=True, kw_only=True)
class SignedState:
    """One signed desired state, for exactly one audience, at one revision."""

    audience: str
    revision: int
    sequence: int
    issued_at: str
    expires_at: str
    body_json: str = field(repr=False)
    signature: str = field(repr=False)

    def __post_init__(self) -> None:
        try:
            _identifier(self.audience, "signed_state.audience")
        except ValueError as exc:
            raise StateError(str(exc)) from None
        for name, value in (("revision", self.revision), ("sequence", self.sequence)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise StateError(f"signed_state.{name}: must be an integer")
            if value < 1:
                raise StateError(f"signed_state.{name}: must be 1 or greater")
            if value > _MAX_SEQUENCE:
                raise StateError(f"signed_state.{name}: is out of range")
        try:
            issued = _timestamp(self.issued_at, "signed_state.issued_at")
            expires = _timestamp(self.expires_at, "signed_state.expires_at")
        except ValueError as exc:
            raise StateError(str(exc)) from None
        if expires <= issued:
            raise StateError("signed_state.expires_at: must be after issued_at")
        if expires - issued > MAX_STATE_LIFETIME:
            raise StateError(
                "signed_state.expires_at: lifetime exceeds "
                f"{int(MAX_STATE_LIFETIME.total_seconds())}s"
            )
        _document_body(self.body_json, "signed_state.body_json")
        if not isinstance(self.signature, str) or not _HEX.match(self.signature):
            raise StateError(
                "signed_state.signature: must be lowercase hex"
            )
        if len(self.signature) != 128:
            raise StateError(
                "signed_state.signature: must be 64 bytes of hex"
            )

    def expired(self, at: datetime) -> bool:
        return at > _timestamp(self.expires_at, "signed_state.expires_at")

    def body(self) -> dict:
        return json.loads(self.body_json)


@dataclass(frozen=True, slots=True, kw_only=True)
class AcceptedState:
    """A signed state the host's checks accepted. The document, and its place."""

    audience: str
    revision: int
    sequence: int
    body_json: str = field(repr=False)

    def state(self) -> DesiredState:
        """The desired state the envelope carries, parsed and validated."""
        return from_document(json.loads(self.body_json))


def signed_bytes(state: SignedState) -> bytes:
    """The one frozen profile a state signature covers.

    Every field except `signature`, canonical JSON: sorted keys, compact,
    UTF-8, no NaN. Pinned byte for byte by a test — a signature over "roughly
    this" verifies nothing.
    """
    if not isinstance(state, SignedState):
        raise StateError("signed_bytes: must be a SignedState")
    document = {
        "audience": state.audience,
        "body": state.body(),
        "expires_at": state.expires_at,
        "issued_at": state.issued_at,
        "revision": state.revision,
        "schema": STATE_SCHEMA,
        "sequence": state.sequence,
    }
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def state_to_document(state: SignedState) -> dict:
    if not isinstance(state, SignedState):
        raise StateError("state_to_document: must be a SignedState")
    return {
        "schema": STATE_SCHEMA,
        "audience": state.audience,
        "revision": state.revision,
        "sequence": state.sequence,
        "issued_at": state.issued_at,
        "expires_at": state.expires_at,
        "body": json.loads(state.body_json),
        "signature": state.signature,
    }


def state_from_document(doc: object, where: str = "signed_state") -> SignedState:
    """Closed wire form: missing fields are named, unknown fields refused."""
    if not isinstance(doc, dict):
        raise StateError(f"{where}: must be an object")
    required = {
        "schema", "audience", "revision", "sequence", "issued_at", "expires_at",
        "body", "signature",
    }
    missing = sorted(required - set(doc))
    if missing:
        raise StateError(f"{where}: missing {', '.join(missing)}")
    unknown = sorted(set(doc) - required)
    if unknown:
        raise StateError(f"{where}: unknown {', '.join(unknown)}")
    if doc["schema"] != STATE_SCHEMA:
        raise StateError(f"{where}.schema: must be {STATE_SCHEMA!r}")
    try:
        return SignedState(
            audience=doc["audience"],
            revision=doc["revision"],
            sequence=doc["sequence"],
            issued_at=doc["issued_at"],
            expires_at=doc["expires_at"],
            body_json=_body_json(doc["body"], f"{where}.body"),
            signature=doc["signature"],
        )
    except StateError:
        raise
    except (TypeError, ValueError) as exc:
        raise StateError(f"{where}: {exc}") from None


class StateIssuer:
    """The manager's side: one monotonic sequence per audience, and a signature.

    In-memory state, the same shape as `AgentChannel`: a store will later hold
    both. The sequence is the replay protection; it is allocated here so the
    host's only job is to check that it increased.
    """

    def __init__(self) -> None:
        self._sequences: dict[str, int] = {}

    def last_sequence(self, audience: str) -> int | None:
        return self._sequences.get(audience)

    def issue(
        self,
        body: dict,
        *,
        audience: str,
        issued_at: datetime,
        signer: Callable[[bytes], bytes],
        ttl: timedelta = MAX_STATE_LIFETIME,
        revision: int | None = None,
    ) -> SignedState:
        """Build, sign, and allocate the next sequence for one audience."""
        try:
            _identifier(audience, "state_issuer.audience")
            _instant(issued_at, "state_issuer.issued_at")
        except ValueError as exc:
            raise StateError(str(exc)) from None
        if not callable(signer):
            raise StateError("state_issuer.signer: must be callable")
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0):
            raise StateError("state_issuer.ttl: must be a positive timedelta")
        if ttl > MAX_STATE_LIFETIME:
            raise StateError(
                "state_issuer.ttl: lifetime exceeds "
                f"{int(MAX_STATE_LIFETIME.total_seconds())}s"
            )
        text = _body_json(body, "state_issuer.body")
        if revision is None:
            try:
                revision = from_document(body).revision
            except ValueError as exc:
                raise StateError(f"state_issuer.body: {exc}") from None
        sequence = self._sequences.get(audience, 0) + 1
        expires_at = _stamp(issued_at + ttl)
        issued_text = _stamp(issued_at)
        # Build unsigned first: the signature covers exactly `signed_bytes` of
        # the finished value, so nothing can sign a shape it does not return.
        unsigned = SignedState(
            audience=audience,
            revision=revision,
            sequence=sequence,
            issued_at=issued_text,
            expires_at=expires_at,
            body_json=text,
            signature="00" * 64,
        )
        try:
            signature = signer(signed_bytes(unsigned))
        except Exception as exc:
            raise StateError(
                "state_issuer.signer: the signature provider refused the state "
                f"({type(exc).__name__}); the issuer does not fall back"
            ) from None
        if not isinstance(signature, bytes):
            raise StateError("state_issuer.signer: must return bytes")
        state = SignedState(
            audience=unsigned.audience,
            revision=unsigned.revision,
            sequence=unsigned.sequence,
            issued_at=unsigned.issued_at,
            expires_at=unsigned.expires_at,
            body_json=unsigned.body_json,
            signature=signature.hex(),
        )
        self._sequences[audience] = sequence
        return state


def accept_state(
    state: SignedState,
    *,
    at: datetime,
    verifier: Callable[[bytes, bytes, bytes], bool],
    public_key: bytes,
    audience: str,
    last_sequence: int | None = None,
) -> AcceptedState:
    """Check a signed state the way the receiving host must.

    Order matters and is the order a refusal should learn from: the document is
    for *this* audience first (a redirected state is refused before anything in
    it is trusted), then its lifetime and freshness, then the signature, then
    the sequence. The caller's `last_sequence` is not advanced here — this is a
    pure check, and the host advances it only once the state is accepted, so a
    forged envelope cannot burn a sequence number.
    """
    if not isinstance(state, SignedState):
        raise StateError("accept_state: must be a SignedState")
    try:
        _instant(at, "accept_state.at")
        _identifier(audience, "accept_state.audience")
    except ValueError as exc:
        raise StateError(str(exc)) from None
    if not callable(verifier):
        raise StateError("accept_state.verifier: must be callable")
    if state.audience != audience:
        raise StateError(
            "accept_state: this state is for a different audience; a document "
            "that can be redirected at another host is not configuration"
        )
    if state.expired(at):
        raise StateError("accept_state: the state has expired")
    issued = _timestamp(state.issued_at, "signed_state.issued_at")
    if at < issued - MAX_STATE_CLOCK_SKEW:
        raise StateError(
            "accept_state: the state is issued beyond the clock skew; its "
            "freshness cannot be judged against this instant"
        )
    try:
        verified = verifier(public_key, signed_bytes(state), bytes.fromhex(state.signature))
    except Exception as exc:
        raise StateError(
            "accept_state: the signature provider refused the state "
            f"({type(exc).__name__}); the host does not fall back"
        ) from None
    if verified is not True:
        raise StateError("accept_state: the state's signature did not verify")
    if last_sequence is not None:
        if not isinstance(last_sequence, int) or isinstance(last_sequence, bool):
            raise StateError("accept_state.last_sequence: must be an integer")
        if state.sequence <= last_sequence:
            raise StateError(
                "accept_state: this state's sequence is not newer than the last "
                "accepted one; a replayed state is refused"
            )
    return AcceptedState(
        audience=state.audience,
        revision=state.revision,
        sequence=state.sequence,
        body_json=state.body_json,
    )
