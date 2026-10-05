# // spec: coh-oap-hard-04
"""Independently provisioned trust store for OAP evidence verification.

Gate 2.2 (openspec/changes/harden-oap-evidence-verification): signer
registrations and revocation state are trust material. They MUST come from an
authenticated authority outside the artifact and outside untrusted caller
input — an arbitrary caller-supplied keyring or revocation snapshot is not
trust. This module is the only source of signer trust for
`hub.coherence.oap_evidence.verify_envelope` and
`hub.coherence.strict_parse.verify_wire_envelope`; both reject anything that
is not a `TrustStore` loaded here from a provisioned file.

A trust file is strict JSON:

    {
      "snapshot_time": "2026-10-04T12:00:00Z",
      "entries": [
        {
          "producer_id": "devgate-instance-1",
          "key_id": "ed25519:...",
          "public_key": "<64 hex chars>",
          "audience": "oap-observer",
          "direction": "devgate-to-oap",
          "valid_from": "2026-10-01T00:00:00Z",
          "valid_until": "2026-11-01T00:00:00Z",
          "revoked": false,
          "revocation_version": 3
        }
      ]
    }

Every field of every entry is required; unknown fields, unknown top-level
keys, duplicate key ids, undecodable public keys and out-of-range values are
provisioning errors and fail closed at load time, not at verify time.

GATE 0 QUARANTINE still applies: a trust-store-backed verify success is a
mathematical + binding verdict and remains NON-AUTHORIZING. It is not a grant
and MUST NOT satisfy a mandatory, promotion, release, or OAP-effect check
until Gates 1-3 pass and the security reviewer plus OAP owner approve.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

NON_AUTHORIZING = True

ENTRY_FIELDS = frozenset({
    "producer_id", "key_id", "public_key", "audience", "direction",
    "valid_from", "valid_until", "revoked", "revocation_version",
})
TOP_LEVEL_FIELDS = frozenset({"snapshot_time", "entries"})

_PUBLIC_KEY_RE_LENGTH = 64  # 32 raw bytes as hex


class TrustStoreError(ValueError):
    """The provisioned trust file is missing, malformed, or incoherent.

    Raised at load time; a receiver never falls back to an unprovisioned or
    partially trusted state.
    """


def _parse_time(value):
    """Parse an ISO-8601 UTC timestamp; naive values are treated as UTC."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _require_string(entry, field):
    value = entry[field]
    if not isinstance(value, str) or not value:
        raise TrustStoreError(f"invalid-trust-entry:{field}")


def _validate_entry(raw, index):
    if not isinstance(raw, dict):
        raise TrustStoreError(f"invalid-trust-entry:{index}")
    missing = ENTRY_FIELDS - set(raw)
    unknown = set(raw) - ENTRY_FIELDS
    if missing:
        raise TrustStoreError(
            f"invalid-trust-entry:{index}:missing:{sorted(missing)[0]}")
    if unknown:
        raise TrustStoreError(
            f"invalid-trust-entry:{index}:unknown:{sorted(unknown)[0]}")
    for field in ("producer_id", "key_id", "audience", "direction"):
        _require_string(raw, field)
    public = raw["public_key"]
    if not isinstance(public, str):
        raise TrustStoreError(f"invalid-trust-entry:{index}:public_key")
    try:
        decoded = bytes.fromhex(public)
    except ValueError:
        raise TrustStoreError(
            f"invalid-trust-entry:{index}:public_key") from None
    if len(decoded) != 32 or len(public) != _PUBLIC_KEY_RE_LENGTH:
        raise TrustStoreError(f"invalid-trust-entry:{index}:public_key")
    for field in ("valid_from", "valid_until"):
        if raw[field] is not None:
            if not isinstance(raw[field], str) or \
                    _parse_time(raw[field]) is None:
                raise TrustStoreError(f"invalid-trust-entry:{index}:{field}")
    if not isinstance(raw["revoked"], bool):
        raise TrustStoreError(f"invalid-trust-entry:{index}:revoked")
    version = raw["revocation_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise TrustStoreError(
            f"invalid-trust-entry:{index}:revocation_version")
    return dict(raw, public_key=public.lower())


class TrustStore:
    """Read-only signer trust loaded from an independently provisioned file.

    Instances are created only through `TrustStore.load(path)`; there is no
    way to assemble trust from in-memory caller data, so a verifier that
    receives a `TrustStore` knows its entries survived file-level
    provisioning and validation.
    """

    def __init__(self, *args, **kwargs):
        raise TrustStoreError(
            "TrustStore cannot be constructed from caller data; use "
            "TrustStore.load(path) against a provisioned trust file")

    @classmethod
    def _from_validated(cls, entries, snapshot_time,
                        max_snapshot_age_seconds):
        store = object.__new__(cls)
        store._entries = tuple(entries)
        store._by_key_id = {entry["key_id"]: entry for entry in entries}
        store._snapshot_time = snapshot_time
        store._max_snapshot_age_seconds = max_snapshot_age_seconds
        return store

    @classmethod
    def load(cls, path, *, max_snapshot_age_seconds=None) -> "TrustStore":
        """Load and validate a provisioned trust file. Fails closed.

        `max_snapshot_age_seconds`, when set, requires the file to carry an
        authenticated `snapshot_time`; at verify time a snapshot older than
        the bound denies use (`stale-revocation-snapshot`).
        """
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise TrustStoreError(f"trust-file-unreadable:{exc}") from None
        try:
            doc = json.loads(text)
        except ValueError:
            raise TrustStoreError("trust-file-malformed") from None
        if not isinstance(doc, dict):
            raise TrustStoreError("trust-file-malformed:not-an-object")
        unknown = set(doc) - TOP_LEVEL_FIELDS
        if unknown:
            raise TrustStoreError(
                f"trust-file-unknown-field:{sorted(unknown)[0]}")
        if "entries" not in doc or not isinstance(doc["entries"], list) \
                or not doc["entries"]:
            raise TrustStoreError("trust-file-malformed:entries")
        snapshot_time = doc.get("snapshot_time")
        if snapshot_time is not None and _parse_time(snapshot_time) is None:
            raise TrustStoreError("trust-file-malformed:snapshot_time")
        if max_snapshot_age_seconds is not None and snapshot_time is None:
            raise TrustStoreError(
                "trust-file-missing-snapshot-time:staleness-unverifiable")
        entries = [_validate_entry(raw, index)
                   for index, raw in enumerate(doc["entries"])]
        seen = set()
        for entry in entries:
            if entry["key_id"] in seen:
                raise TrustStoreError(
                    f"trust-file-duplicate-key-id:{entry['key_id']}")
            seen.add(entry["key_id"])
        store = cls._from_validated(entries, snapshot_time,
                                    max_snapshot_age_seconds)
        return store

    @property
    def entries(self):
        return self._entries

    @property
    def snapshot_time(self):
        return self._snapshot_time

    @property
    def revocation_version(self):
        """Highest revocation version present in the snapshot."""
        return max(entry["revocation_version"] for entry in self._entries)

    def lookup(self, key_id):
        return self._by_key_id.get(key_id)

    def evaluate(self, key_id, *, producer_id, direction, audience,
                 reference_time=None):
        """Authorize a key for an exact scope. Returns (entry, reason).

        First failure wins with a distinct reason code: snapshot freshness ->
        unknown-key -> revoked-key -> producer/direction/audience binding ->
        key validity window. `reference_time` is the consumer's authenticated
        context time (a `datetime`); a producer timestamp is never trusted.
        """
        if reference_time is not None and reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        if self._max_snapshot_age_seconds is not None and \
                reference_time is not None:
            snapshot = _parse_time(self._snapshot_time)
            if reference_time - snapshot > timedelta(
                    seconds=self._max_snapshot_age_seconds):
                return None, "stale-revocation-snapshot"
        entry = self.lookup(key_id)
        if entry is None:
            return None, f"unknown-key:{key_id}"
        if entry["revoked"]:
            return None, f"revoked-key:{key_id}"
        if entry["producer_id"] != producer_id:
            return None, f"key-producer-mismatch:{entry['producer_id']}"
        if entry["direction"] != direction:
            return None, f"key-direction-mismatch:{entry['direction']}"
        if entry["audience"] != audience:
            return None, f"key-audience-mismatch:{entry['audience']}"
        if reference_time is not None:
            valid_from = _parse_time(entry["valid_from"]) \
                if entry["valid_from"] else None
            valid_until = _parse_time(entry["valid_until"]) \
                if entry["valid_until"] else None
            if entry["valid_from"] and valid_from is None:
                return None, "key-window-unparseable:valid_from"
            if valid_from is not None and reference_time < valid_from:
                return None, "key-not-yet-valid"
            if entry["valid_until"] and valid_until is None:
                return None, "key-window-unparseable:valid_until"
            if valid_until is not None and reference_time > valid_until:
                return None, "key-expired"
        return entry, None


def digest_of(content: bytes) -> str:
    """The `sha256:` digest form used by envelope bindings."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


__all__ = [
    "ENTRY_FIELDS", "NON_AUTHORIZING", "TOP_LEVEL_FIELDS", "TrustStore",
    "TrustStoreError", "digest_of",
]
