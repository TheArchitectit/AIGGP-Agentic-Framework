"""hub.toolchain_api — HTTP surface for toolchain requests and decisions.

// spec: mon-tc-02, mon-tc-03, mon-tc-04

POST /toolchain/decide  operator decision on one request row.
GET  /toolchain/requests  list of request rows (system of record).

The decision route is the only one that can move a request row. It is
authenticated by an operator credential carrying scope `toolchain:decide`
plus an actor claim, timestamp, and single-use nonce. Any other credential
class is refused as `rejected_credential_class` (mon-tc-03).

This module is deliberately separate from hub/server.py so that server.py
stays under DevGate's 500-line source hard limit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import toolchain_creds, toolchain_requests, toolchain_transitions
from .registry import UNREPORTED  # noqa: F401
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .server import HubState


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def handle_decide(state: "HubState", body: dict | None) -> tuple[int, dict]:
    """Apply one operator decision. Returns (status_code, payload)."""
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "json object required"}
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "request_id required"}
    action = body.get("action")
    if action not in ("approve", "deny"):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "action must be 'approve' or 'deny'"}
    credential = body.get("credential")
    actor = body.get("actor")
    principal = body.get("principal")
    timestamp = body.get("timestamp")
    nonce = body.get("nonce")
    expected_version = body.get("expected_version")
    note = body.get("note")
    if note is not None and not isinstance(note, str):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "note must be a string or null"}
    if expected_version is not None and not isinstance(expected_version, int):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "expected_version must be an integer or null"}

    # Classify the presented credential. None when nothing was presented
    # (unauthenticated); "unknown" when a secret was presented but matched no
    # stored credential.
    credential_class, info = state.registry.classify_credential(credential)
    scope, principal_from_cred, credential_id = toolchain_creds.operator_info(info)
    # For an operator credential, prefer the credential's own principal when the
    # caller did not supply one, but never invent an actor from the credential
    # when none was claimed (mon-tc-03).
    if principal is None and principal_from_cred is not None:
        principal = principal_from_cred
    # timestamp must be present for an operator decision
    now = timestamp if isinstance(timestamp, str) and timestamp else _now_iso()

    if toolchain_transitions.note_too_long(note):
        # Refused before touching the row. No audit row: a note this long is
        # a malformed decision, not a decision about the request.
        return 400, {"ok": False, "error": "decision_note_too_long",
                     "cap": toolchain_transitions.toolchain_requests.DECISION_NOTE_MAX_CHARS}

    def do_decide(reg):
        return reg.decide_request(
            request_id, action=action, credential_class=credential_class,
            scope=scope, credential_id=credential_id, actor=actor,
            principal=principal, nonce=nonce,
            expected_version=expected_version, note=note, now=now)

    result = state.with_registry(do_decide)
    status = result.get("status", 500)
    if status == 404:
        return 404, {"ok": False, "error": "request_not_found"}
    # Translate the engine's result into the HTTP payload.
    payload = {"ok": status < 400}
    if result.get("error"):
        payload["error"] = result["error"]
    if result.get("credential_class"):
        payload["credential_class"] = result["credential_class"]
    if result.get("state"):
        payload["state"] = result["state"]
    if result.get("version") is not None:
        payload["version"] = result["version"]
    if result.get("idempotent"):
        payload["idempotent"] = True
        if result.get("applied_at"):
            payload["applied_at"] = result["applied_at"]
    if result.get("current_version") is not None:
        payload["current_version"] = result["current_version"]
    return status, payload


def handle_list_requests(state: "HubState") -> tuple[int, dict]:
    with state._lock:
        rows = [dict(r) for r in state.registry.toolchain_requests()]
    return 200, {"ok": True, "requests": rows}


def handle_build_report(state: "HubState", body: dict | None) -> tuple[int, dict]:
    """Apply one builder report. Returns (status_code, payload).

    // spec: mon-tc-05, mon-tc-04

    The class check lives in the engine, not here, for the mon-tc-03 reason: the
    hub classifies the presented secret and refuses whatever class it turns out
    to be. Nothing in this function accepts a class name from the body, so a
    runner that sends `class: "builder"` beside its heartbeat token is still a
    heartbeat token.

    `digest: null` means build-failed (the engine documents why), so a body with
    no digest key at all is refused as ambiguous rather than read as a failure:
    a report that never mentioned a digest is a malformed report, and treating
    an omitted key as "the build failed" would let a client that forgot a field
    reopen a request it never observed.
    """
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "json object required"}
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "request_id required"}
    if "digest" not in body:
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "digest required (null states a failed build)"}
    digest = body["digest"]
    if digest is not None and not isinstance(digest, str):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "digest must be a string or null"}
    for key in ("profile_id", "build_id"):
        value = body.get(key)
        if value is not None and not isinstance(value, str):
            return 400, {"ok": False, "error": "bad_request",
                         "detail": f"{key} must be a string or null"}
    note = body.get("note")
    if note is not None and not isinstance(note, str):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "note must be a string or null"}
    expected_version = body.get("expected_version")
    if expected_version is not None and not isinstance(expected_version, int):
        return 400, {"ok": False, "error": "bad_request",
                     "detail": "expected_version must be an integer or null"}
    timestamp = body.get("timestamp")
    now = timestamp if isinstance(timestamp, str) and timestamp else _now_iso()

    result = state.with_registry(
        lambda reg: reg.report_build(
            request_id, credential=body.get("credential"),
            profile_id=body.get("profile_id"), build_id=body.get("build_id"),
            digest=digest, note=note, expected_version=expected_version,
            now=now))
    status = result.get("status", 500)
    payload = {"ok": status < 400}
    for key in ("error", "credential_class", "state", "current_version",
                "submitted_version", "approved_profile"):
        if result.get(key) is not None:
            payload[key] = result[key]
    if result.get("fields"):
        payload["fields"] = result["fields"]
    return status, payload