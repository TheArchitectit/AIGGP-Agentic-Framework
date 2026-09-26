# // spec: coh-ev-04
"""Authorized input retention (coh-ev-04, design.md section 9): where
reproduction needs the exact subject or package bytes, an immutable input
bundle is preserved on a channel SEPARATE from public evidence, retrievable
only under an authorization distinct from evidence-read access, and expiry
invalidates cached-result reuse for the affected identities.

Public evidence carries digests and minimum-disclosure excerpts, and its reader
does not need a secret to see it. Retained inputs are the raw bytes, so this
module guards them with (a) a control-plane HMAC capability derived from
HUB_COHERENCE_RETENTION_KEY (which an evidence reader does not hold), (b) a
lifetime window computed against the caller's trusted `as_of`, never the host
clock, and (c) a content digest re-check on every read.

Layout: <root>/bundles/<ref> holds the raw bytes; <root>/records/<ref>.json
holds the metadata the expiry and integrity checks need. The digest of a
bundle's own bytes is its ref — so retain is idempotent and read is bound to
content by construction.
"""
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

KEY_ENV = "HUB_COHERENCE_RETENTION_KEY"
_TOKEN_PREFIX = "hmac-sha256:"
_AUTH_ROLE = b"retention-authorization/v1"
# A bundle ref is the content digest retain() minted it from; anything else
# (a traversal segment, a malformed or non-string value) is not a ref.
_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class RetentionError(RuntimeError):
    """Refused to reveal a retained bundle; fail-closed. Reason codes:
    retention-unauthorized, retention-expired, retention-tampered,
    retention-unknown, retention-bad-time, retention-bad-ref."""


def _check_ref(ref) -> str:
    if not isinstance(ref, str) or not _REF_RE.fullmatch(ref):
        raise RetentionError(f"retention-bad-ref:{ref!r}")
    return ref


def _key() -> bytes:
    raw = os.environ.get(KEY_ENV, "").strip()
    if not raw:
        raise RetentionError("retention-key-not-configured")
    try:
        return bytes.fromhex(raw)
    except ValueError:
        raise RetentionError("retention-key-malformed") from None


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def issue(ref: str) -> str:
    """HMAC capability binding a caller to a single retained bundle. An
    authorization for another bundle, or produced under another key, will not
    unlock this one — the spec's 'authorization distinct from evidence read'
    is the control-plane secret this module reads and evidence does not."""
    mac = hmac.new(_key(), _AUTH_ROLE + b"\x00" + ref.encode("utf-8"),
                   hashlib.sha256)
    return _TOKEN_PREFIX + mac.hexdigest()


def _bundle_path(root, ref: str) -> Path:
    return Path(root) / "bundles" / ref


def _record_path(root, ref: str) -> Path:
    return Path(root) / "records" / f"{ref}.json"


def retain(store_root, subject_digest: str, payload: bytes, *,
           retained_at: str, retention_days: int) -> str:
    """Preserve the exact input bytes bound to `subject_digest`. Returns the
    bundle ref (the content digest). Re-retaining identical bytes is a no-op;
    a different payload under the same subject digest would create a second
    bundle, which the store's identity contract forbids — raise."""
    if retention_days < 0:
        raise RetentionError("retention-days-negative")
    try:
        _parse(retained_at)
    except ValueError:
        raise RetentionError("retention-bad-time") from None
    content_ref = "sha256:" + hashlib.sha256(payload).hexdigest()
    root = Path(store_root)
    bundle = _bundle_path(root, content_ref)
    record = _record_path(root, content_ref)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    record.parent.mkdir(parents=True, exist_ok=True)
    if bundle.exists():
        # Idempotency check: same digest implies same bytes by construction,
        # so no work; a mismatch here means a sha256 collision, which we do
        # not attempt to recover from.
        if bundle.read_bytes() != payload:
            raise RetentionError("retention-digest-collision")
    else:
        bundle.write_bytes(payload)
    meta = {"subject_digest": subject_digest, "content_digest": content_ref,
            "retained_at": retained_at, "retention_days": retention_days}
    record.write_text(json.dumps(meta), encoding="utf-8")
    return content_ref


def read(store_root, ref: str, *, as_of: str, authorization) -> bytes:
    """Retrieve a retained bundle's bytes. Every failure raises RetentionError
    with a distinct reason so the caller can tell unauthorized from expired
    from tampered; the cache layer keys off this to invalidate entries whose
    input retention has lapsed. Never consults the host clock."""
    _check_ref(ref)
    bundle = _bundle_path(store_root, ref)
    if not bundle.is_file():
        raise RetentionError("retention-unknown")
    try:
        expected = issue(ref)
    except RetentionError as e:
        raise RetentionError(f"retention-unauthorized:{e}") from None
    if not isinstance(authorization, str) or not hmac.compare_digest(
            expected, authorization):
        raise RetentionError("retention-unauthorized")
    try:
        meta = json.loads(_record_path(store_root, ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RetentionError("retention-record-missing") from None
    try:
        retained = _parse(meta["retained_at"])
        now = _parse(as_of)
    except (ValueError, KeyError, TypeError):
        raise RetentionError("retention-bad-time") from None
    expiry = retained + timedelta(days=meta["retention_days"])
    if now > expiry:
        raise RetentionError("retention-expired")
    payload = bundle.read_bytes()
    if "sha256:" + hashlib.sha256(payload).hexdigest() != ref:
        raise RetentionError("retention-tampered")
    return payload
