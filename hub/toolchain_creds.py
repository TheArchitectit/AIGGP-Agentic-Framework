"""hub.toolchain_creds — operator credentials and consumed-nonce state.

// spec: mon-tc-03

Stores the hub's copy of operator service credentials. Every secret is kept
ONLY as a salted digest computed exactly the way `Registry._hash_token`
computes a heartbeat-token digest (`sha256:` + sha256(registry_salt + secret)),
so a registry read at rest yields no usable credential (mon-sec-02 applies to
operator credentials as it does to heartbeat tokens).

The credential classes are closed (mon-tc-03): enrollment, heartbeat,
runner_key, operator, builder. `operator` is the only class that may decide,
and only when it carries scope `toolchain:decide`. A class outside that set is
refused as `unknown`, so a new credential type cannot acquire a decision
right by being unlisted. runner keys, builder credentials and ordinary MC
write keys are not stored here as operator credentials — they live in their
own stores (heartbeat tokens on the runner record, runner_key/builder entries
in `toolchain_credentials`) and are classified by `classify()` so the refusal
can name the class it saw.

Consumed nonces live in the same document: a nonce is a claim about one moment
in the hub, not about one request row, so replay detection is checked across
every row before any decision is applied. The nonce value is a random 256-bit
string (tokens.mint_token) and identifies a decision rather than a principal,
so storing it is not the mon-sec-02 problem heartbeat tokens are — but a
consumed nonce is never echoed or logged, because publishing it would let a
reader replay it against a row that has since moved.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timezone

from . import tokens

DECIDE_SCOPE = "toolchain:decide"
CREDENTIAL_CLASSES = ("enrollment", "heartbeat", "runner_key", "operator", "builder")


def _salt(data: dict) -> str:
    return data.get("token_salt") or ""


def hash_secret(data: dict, secret: str) -> str:
    """Salted digest of a credential secret (mon-sec-02, same scheme as
    heartbeat tokens)."""
    return "sha256:" + hashlib.sha256(
        (_salt(data) + (secret or "")).encode("utf-8")).hexdigest()


def verify_secret(data: dict, presented: str, stored_hash: str | None) -> bool:
    if not presented or not stored_hash:
        return False
    return hmac.compare_digest(hash_secret(data, presented), stored_hash)


# --- consumed nonces ----------------------------------------------------------

def is_nonce_consumed(data: dict, nonce: str) -> bool:
    return nonce in (data.get("toolchain_consumed_nonces") or [])


def consume_nonce(data: dict, nonce: str) -> None:
    consumed = data.setdefault("toolchain_consumed_nonces", [])
    if nonce not in consumed:
        consumed.append(nonce)


# --- credential storage -------------------------------------------------------

def add_credential(data: dict, *, klass: str, secret: str,
                   credential_id: str, scope: str | None = None,
                   principal: str | None = None,
                   runner_name: str | None = None,
                   builder_identity: str | None = None) -> None:
    """Store one credential as a salted digest. Idempotent on credential_id."""
    creds = data.setdefault("toolchain_credentials", [])
    for c in creds:
        if c.get("credential_id") == credential_id:
            return  # already registered
    creds.append({
        "class": klass,
        "credential_id": credential_id,
        "secret_hash": hash_secret(data, secret),
        "scope": scope,
        "principal": principal,
        "runner_name": runner_name,
        "builder_identity": builder_identity,
    })


def _match_stored(data: dict, presented: str) -> dict | None:
    if not presented:
        return None
    for c in data.get("toolchain_credentials", []):
        if verify_secret(data, presented, c.get("secret_hash")):
            return c
    return None


def classify(data: dict, presented: str | None) -> tuple[str | None, dict | None]:
    """Classify a presented secret into a credential class.

    Returns ``(class_name, info)``. ``class_name`` is None when nothing was
    presented (unauthenticated). A presented secret that matches no stored
    credential is classified as ``"unknown"`` (mon-tc-03: a class absent from
    the table is refused as ``unknown``).
    """
    if not presented:
        return None, None
    stored = _match_stored(data, presented)
    if stored is not None:
        return stored.get("class"), stored
    # heartbeat tokens live on the runner record
    for runner in data.get("runners", []):
        if not runner.get("enrolled", False):
            continue
        if verify_secret(data, presented, runner.get("heartbeat_token_hash")):
            info = {"class": "heartbeat", "credential_id": runner.get("name"),
                    "principal": None, "scope": None,
                    "runner_name": runner.get("name")}
            return "heartbeat", info
    # enrollment tokens are stored plaintext (one-time, legacy shape)
    for tok in data.get("enrollment_tokens", []):
        if tokens.verify(presented, tok):
            info = {"class": "enrollment", "credential_id": None,
                    "principal": None, "scope": None}
            return "enrollment", info
    return "unknown", None


def operator_info(info: dict | None) -> tuple[str | None, str | None, str | None]:
    """Extract (scope, principal, credential_id) for an operator credential."""
    if not info:
        return None, None, None
    return info.get("scope"), info.get("principal"), info.get("credential_id")


# --- helpers ------------------------------------------------------------------

def mint_secret() -> str:
    return tokens.mint_token()


def migrate_legacy_state(data: dict) -> None:
    """Ensure the credential and nonce collections exist on a loaded registry.

    A registry written before this capability shipped has no such keys, and
    reading them as empty sets is correct: no operator credentials, no
    consumed nonces. This is the load-time migration; the collections are
    written by the caller (Registry.load) so a hub restart never loses
    replay state.
    """
    data.setdefault("toolchain_credentials", [])
    data.setdefault("toolchain_consumed_nonces", [])


# --- the decide seam ---------------------------------------------------------

def decide_request(data: dict, request_id: str, *, action: str,
                   credential_class: str | None, scope: str | None,
                   credential_id: str | None, actor: str | None,
                   principal: str | None, nonce: str | None,
                   expected_version: int | None, note: str | None,
                   now: str) -> dict:
    """Apply one operator decision to a request row, under the caller's lock.

    // spec: mon-tc-03, mon-tc-04

    The transitions engine is dict-only; this is the seam that resolves the
    row, runs decide(), and persists the consumed nonce on success. The caller
    (Registry.decide_request, then hub/toolchain_api.py) owns the lock and the
    save, because one document with one writer is what makes two simultaneous
    decisions produce one 200 and one 409 rather than two 200s.
    """
    from . import toolchain_transitions
    target = None
    for row in data.get("toolchain_requests", []):
        if row.get("id") == request_id:
            target = row
            break
    if target is None:
        return {"status": 404, "error": "request_not_found"}
    consumed = lambda n: is_nonce_consumed(data, n)
    result = toolchain_transitions.decide(
        target, action=action, credential_class=credential_class,
        scope=scope, credential_id=credential_id, actor=actor,
        principal=principal, nonce=nonce,
        expected_version=expected_version, note=note, now=now,
        consumed_nonces=consumed)
    # Persist the nonce only when a transition actually applied (200). A
    # refused replay never adds a nonce (it was already there). An
    # idempotent 200 means the same decision was already applied: the nonce
    # was already consumed on the original application, so do not double-count.
    if result.get("status") == 200 and not result.get("idempotent", False):
        if nonce is not None:
            consume_nonce(data, nonce)
    if result.get("status") == 200:
        target.setdefault("nonces", [])
        if nonce is not None and nonce not in target["nonces"]:
            target["nonces"].append(nonce)
    return result


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ConsumedNonces:
    """Thin wrapper retained for callers that want an object; the persisted
    state is the data dict itself (see is_nonce_consumed/consume_nonce)."""
    def __init__(self, data: dict):
        self._data = data

    def is_consumed(self, nonce: str) -> bool:
        return is_nonce_consumed(self._data, nonce)

    def consume(self, nonce: str) -> None:
        consume_nonce(self._data, nonce)

    def __contains__(self, nonce: str) -> bool:
        return is_nonce_consumed(self._data, nonce)


# Re-export for convenience.
__all__ = ["DECIDE_SCOPE", "CREDENTIAL_CLASSES", "hash_secret", "verify_secret",
           "add_credential", "classify", "is_nonce_consumed", "consume_nonce",
           "operator_info", "mint_secret", "now_iso"]