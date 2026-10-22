"""hub.toolchain_transitions — the guarded state machine over request rows.

// spec: mon-tc-03, mon-tc-04

mon-tc-04's table is *normative*, which is a stronger word than "documented": a
transition not in the table must not happen, and this module is the only place one
can. It is written as data plus one interpreter rather than as a scattering of
`if state == "open"` checks, because a table you can iterate is a table you can
test row by row — and the row nobody thought to test is exactly the row that gets
invented later, in a call site, from outside the table.

WHAT THIS MODULE DOES NOT DO. It takes a `request` dict and mutates it in place; it
does not know the registry, the JSON document, or the HTTP layer. The caller
(`Registry.decide_request`, then `hub/toolchain_api.py`) owns the lock and the save,
because one document with one writer is the thing that makes two simultaneous
decisions produce one 200 and one 409 rather than two 200s. Keeping the engine
dict-only also means every guard here is testable without a hub, a port, or a clock.

AUTHORIZATION IS LOOKED UP, NOT CLAIMED. A caller presents a secret and the hub
finds which credential that secret *is*; it never accepts a class name as evidence
of a class. The difference is the whole mon-tc-03 scenario "a runner attempts to
decide": a spoke that sends `class: "operator"` alongside its heartbeat token is
still a heartbeat token, and a hub that read the claim would let the unauthenticated
self-declare its way to a decision right. A class outside the closed table is
refused as `unknown`, so a new credential type cannot acquire a decision right by
being absent from the list (mon-tc-03).

NO SECRET, NO PREFIX, NO DERIVATION. A refusal carries a class *name* drawn from a
fixed set, never the presented value, its prefix, or a hash of it (mon-tc-03, and
the same reasoning as mon-sec-02's salted digests). Every function here was written
with that constraint in mind, which is why none of them take a token as a string
they might format.
"""

from __future__ import annotations

from . import toolchain_requests

# mon-tc-03's closed set. `mc_api_key` is deliberately absent: the spec's own
# scenario names "an ordinary Mission Control API key" as something that must be
# refused, and it is not in the class table, so it is refused as `unknown` rather
# than added to a table that would then have to say what it may do.
CREDENTIAL_CLASSES = ("enrollment", "heartbeat", "runner_key", "operator", "builder")
DECIDE_SCOPE = "toolchain:decide"

# mon-tc-03's refusal code. One code, carrying the class name — the point is that
# the hub can say what it saw without saying anything about what it was shown.
REJECTED_CREDENTIAL_CLASS = "rejected_credential_class"

STATES = ("open", "approved", "built", "fulfilled", "denied")

# mon-tc-04's normative table. (from, event) -> (guard, to, audit_row). `guard` and
# `to` are read by name below, so a reviewer can diff this against the spec page by
# page; the tuple order mirrors the spec's own column order on purpose.
TRANSITIONS: dict[tuple[str, str], dict] = {
    ("open", "decide-approve"): {
        "guard": "operator credential, fresh nonce", "to": "approved",
        "audit_row": "decision + actor claim"},
    ("open", "decide-deny"): {
        "guard": "operator credential, fresh nonce, note present", "to": "denied",
        "audit_row": "decision + actor claim + note"},
    ("approved", "report-built"): {
        "guard": "builder credential, profile id matches the approved profile, "
                 "build id and digest present", "to": "built",
        "audit_row": "build evidence"},
    ("built", "converge"): {
        "guard": "a later heartbeat reports the recorded digest and the required "
                 "probe passes", "to": "fulfilled",
        "audit_row": "convergence evidence"},
    ("approved", "build-failed"): {
        "guard": "builder credential, note present", "to": "open",
        "audit_row": "failure + note"},
    ("built", "build-failed"): {
        "guard": "builder credential, note present", "to": "open",
        "audit_row": "failure + note"},
    ("fulfilled", "gap-regressed"): {
        "guard": "a later heartbeat reports the gap again", "to": "open",
        "audit_row": "regression"},
    ("denied", "report-suppressed"): {
        "guard": "within the suppression window", "to": "denied",
        "audit_row": "no state change; suppression counter"},
    ("denied", "report-after-window"): {
        "guard": "suppression window elapsed", "to": "open",
        "audit_row": "reopen"},
}


def audit_record(request: dict, *, at: str, actor: str | None,
                 principal: str | None, credential_id: str | None, event: str,
                 frm: str | None, to: str | None, version_before: int | None,
                 version_after: int | None, note: str | None) -> dict:
    """One history entry, in the field order mon-tc-03 fixes.

    // spec: mon-tc-03

    The shape is built here rather than at call sites so that attribution is a
    property of the format and not of whoever happened to write the transition.
    `principal` is stored exactly as presented: no display name, no email, no
    identity the hub did not receive. A single-credential v1 deployment shows up in
    the records as one repeated `credential_id`, which is the honest reading —
    inventing per-operator attribution would be the audit trail lying about a thing
    a reader cannot otherwise check.
    """
    history = request.get("history") or []
    seq = (history[-1].get("seq", -1) + 1) if history else 0
    return {
        "seq": seq,
        "at": at,
        "actor": actor,
        "principal": principal,
        "credential_id": credential_id,
        "event": event,
        "from": frm,
        "to": to,
        "version_before": version_before,
        "version_after": version_after,
        "note": note,
    }


def append_history(request: dict, record: dict) -> None:
    """Append one record. mon-tc-04: history is append-only.

    There is deliberately no update or delete helper in this module. A capability
    whose audit trail can be rewritten cannot support the only thing the trail is
    for — being able to say what was decided, by which credential, when.
    """
    request.setdefault("history", []).append(record)


def note_too_long(note: object) -> bool:
    """True when a decision note exceeds the cap (mon-tc-03).

    Over-cap is refused, never truncated: a truncated reason is a *different*
    reason, and a denial note gets read as the operator's decision. An empty or
    absent note is not "too long" — whether a note is *required* is a per-event
    guard in the table, decided by the caller.
    """
    return isinstance(note, str) and len(note) > toolchain_requests.DECISION_NOTE_MAX_CHARS


def _result(status: int, *, error: str | None = None, **extra) -> dict:
    return {"status": status, "error": error, **extra}


def decide(request: dict, *, action: str, credential_class: str | None,
           scope: str | None, credential_id: str | None, actor: str | None,
           principal: str | None, nonce: str | None, expected_version: int | None,
           note: str | None, now: str, consumed_nonces) -> dict:
    """Apply an operator decision (approve|deny) to one request row.

    // spec: mon-tc-03, mon-tc-04

    Returns ``{"status": ..., "error": ..., "idempotent": bool}``. Statuses are HTTP
    codes because the refusal *is* the API contract: 401 when nothing authenticated,
    403 when something authenticated but may not decide, 409 on a version conflict,
    400 on a malformed decision, 200 when it applied or was already applied.

    Order of the checks is load-bearing and was chosen for two reasons:

      1. **Authenticate before evaluating anything about the request.** A guard that
         inspects the request first would leak "that request exists and is in state
         X" to an unauthenticated caller.
      2. **Replay is refused before idempotency.** mon-tc-03 refuses a consumed
         nonce; mon-tc-04 returns the existing outcome for a decision re-submitted
         at an already-applied version. Those are different events with different
         answers, and the distinction is the nonce: the same decision *content*
         presented with a fresh nonce is the idempotent case, the *same nonce*
         presented twice is the replay case, and it must be the replay that fails.

    ``consumed_nonces`` is a callable the caller supplies over the whole request set
    — a nonce is a claim about one moment in the hub, not about one row, so replay
    must be checked across every request rather than only the one being decided.
    """
    if credential_class is None:
        return _result(401, error="unknown_credential")
    if credential_class != "operator" or scope != DECIDE_SCOPE:
        # One code carrying the class name; never the secret, its prefix, or a
        # derivation (mon-tc-03).
        append_history(request, audit_record(
            request, at=now, actor=actor, principal=principal,
            credential_id=credential_id, event=REJECTED_CREDENTIAL_CLASS,
            frm=request.get("state"), to=request.get("state"),
            version_before=request.get("version"),
            version_after=request.get("version"), note=None))
        return _result(403, error=REJECTED_CREDENTIAL_CLASS,
                       credential_class=credential_class or "unknown")

    event = "decide-approve" if action == "approve" else "decide-deny"

    version = request.get("version")
    # mon-tc-04 CAS: a decision targets a version. If the row has moved since the
    # caller last read it, exactly one decision wins and the other is refused
    # with 409. Both attempts are recorded so the loser is visible in the trail.
    if expected_version is not None and expected_version != version:
        append_history(request, audit_record(
            request, at=now, actor=actor, principal=principal,
            credential_id=credential_id, event="rejected-conflict",
            frm=request.get("state"), to=request.get("state"),
            version_before=version, version_after=version, note=note))
        return _result(409, error="version_conflict", current_version=version,
                       submitted_version=expected_version)

    # mon-tc-04 idempotency: re-submitting the identical decision at the version
    # it already produced returns that outcome without applying a second time.
    # Content is compared, not identity: a re-submission of a *different* decision
    # at that version is a conflict, not a no-op, and answering it 200 would report
    # success for a decision nobody made. This runs before the rule lookup because
    # the table only covers `open` as a source state — an already-applied decision
    # re-submitted at its own version is not "already approved, approve again", it
    # *is* approve again at a version it produced, so it is a no-op.
    if expected_version == version:
        prior = next((h for h in request.get("history", [])
                      if h.get("version_after") == version
                      and h.get("event") == event
                      and h.get("actor") == actor
                      and h.get("note") == note), None)
        if prior is not None:
            return _result(200, error=None, idempotent=True,
                           applied_at=prior.get("at"), version=version,
                           state=request.get("state"))

    if not actor or not principal or not nonce:
        return _result(400, error="actor_claim_incomplete")
    if nonce is not None and consumed_nonces(nonce):
        append_history(request, audit_record(
            request, at=now, actor=actor, principal=principal,
            credential_id=credential_id, event="rejected-replay",
            frm=request.get("state"), to=request.get("state"),
            version_before=request.get("version"),
            version_after=request.get("version"), note=None))
        return _result(409, error="replayed_nonce")
    if note_too_long(note):
        # Refused, not truncated. No history row: a note this long is a malformed
        # decision rather than a decision about the request, and putting the refused
        # note in the trail would store the very content the cap exists to exclude.
        return _result(400, error="decision_note_too_long",
                       cap=toolchain_requests.DECISION_NOTE_MAX_CHARS)
    if event == "decide-deny" and not note:
        append_history(request, audit_record(
            request, at=now, actor=actor, principal=principal,
            credential_id=credential_id, event="rejected-missing-note",
            frm=request.get("state"), to=request.get("state"),
            version_before=request.get("version"),
            version_after=request.get("version"), note=None))
        return _result(400, error="deny_requires_note")

    # Rule lookup: a transition not in the table is not permitted — including the
    # tempting "already approved, just approve it again" that idempotency above
    # handles when expected_version == version, and including any state an
    # unimplemented future adds.
    rule = TRANSITIONS.get((request.get("state"), event))
    if rule is None:
        append_history(request, audit_record(
            request, at=now, actor=actor, principal=principal,
            credential_id=credential_id, event="rejected-transition",
            frm=request.get("state"), to=request.get("state"),
            version_before=version, version_after=version, note=None))
        return _result(409, error="transition_not_in_table",
                       state=request.get("state"), event=event)

    from_state = request["state"]
    request["state"] = rule["to"]
    request["version"] = version + 1
    request["actor"] = actor
    request["principal"] = principal
    request["credential_id"] = credential_id
    request["decided_at"] = now
    request["decision_note"] = note
    request.setdefault("nonces", []).append(nonce)
    if rule["to"] == "denied":
        request["suppression_until"] = suppress_until(now)
    append_history(request, audit_record(
        request, at=now, actor=actor, principal=principal,
        credential_id=credential_id, event=event, frm=from_state, to=rule["to"],
        version_before=version, version_after=version + 1, note=note))
    return _result(200, error=None, idempotent=False, version=version + 1,
                   state=rule["to"])


def suppress_until(now: str) -> str:
    """When a denial stops suppressing: mon-tc-06 owns the number, not this file."""
    from datetime import datetime, timedelta, timezone

    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        base = datetime.strptime(now, fmt).replace(tzinfo=timezone.utc)
    except ValueError:
        base = datetime.now(timezone.utc)
    return (base + timedelta(days=toolchain_requests.TOOL_REQUEST_SUPPRESSION_DAYS)
            ).strftime(fmt)


def report_event(state: str, *, within_suppression: bool) -> str | None:
    """Which table event a gap report means for a row in `state`.

    // spec: mon-tc-04

    The three cases mon-tc-04 separates: an open request just gets re-observed
    (None — no transition, no version bump), a fulfilled one regressing is
    `gap-regressed`, and a denied one is `report-suppressed` inside the window or
    `report-after-window` once it has elapsed. Returning the event name rather than
    applying it keeps this a lookup the table can be diffed against, and lets the
    gap-report path stay readable.
    """
    if state == "fulfilled":
        return "gap-regressed"
    if state == "denied":
        return "report-suppressed" if within_suppression else "report-after-window"
    return None
