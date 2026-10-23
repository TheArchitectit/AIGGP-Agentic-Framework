"""hub.toolchain_evidence — build evidence and convergence (mon-tc-05).

mon-tc-05 says `fulfilled` is not reachable from a digest alone: `built` needs
a builder credential, a profile id matching the approved profile, a build id
and a digest, and `fulfilled` needs *a later heartbeat in which the lane
reports that same digest and the required tool probe passes*. S2 shipped the
credential classes and the CAS/append-only machinery; the transition table in
`toolchain_transitions.py` has always named `report-built` and `converge` as
rows — this module is the code that applies them, and nothing else may.

WHY BUILD EVIDENCE HAS ITS OWN ROUTE AND NOT A HEARTBEAT FIELD. A build report
is authenticated by a **builder** credential, a class mon-tc-03 keeps distinct
from both the operator credential and runner credentials. The heartbeat
channel authenticates a lane, so a field on it would either accept a build
report from a lane (the lane declaring its own image built, which is the
request channel's whole failure mode inverted) or add a second credential type
to a route whose security story is one token. A separate POST is the smaller
lie, and it keeps `hub/registry.py` — at DevGate's 500-line hard limit — from
growing a builder verifier it has no business owning.

WHY CONVERGENCE IS STRICTLY SAME-TICK. mon-tc-05's words are "a later
heartbeat IN WHICH the lane reports that same digest AND the required tool
probe passes" — both halves in the one heartbeat, so that is what is enforced.
A staleness fallback ("the last clean report was under 900s ago, count it") was
the tempting version and is the wrong one: coverage `reported` is also set by a
REFUSED gap report, because mon-tc-06 asks whether the lane ever spoke and a
malformed report is still speaking. Crediting presence to the last accepted
*report* is not the same fact, and there is no stored timestamp distinguishing
"last accepted clean" from "last spoke somehow". So the probe half is true only
when THIS tick carried an accepted gap list without the row's tool and the
spoke did not flag its probe incomplete. A spoke that predated the probe field
therefore never converges a row — honest, not a bug: fulfillment demands probe
evidence, and a hub that fulfilled without it would fulfill on absence.

The two halves can still land on different ticks, in the safe direction: the
digest is stored on the runner record, so a clean gap list on a later tick
converges against the stored digest (and a refused or absent list converges
nothing). What never happens is the fallback reading silence as health.

THE LANE'S OWN DIGEST REPORT MAY ONLY CLEAR AN AWAITING DIGEST, NEVER SATISFY
ONE. mon-tc-01's principle — the spoke must not be able to declare itself
provisioned — applied to Q6's evidence field. A lane that reports digest X
while some row waits for X gets `converge` ONLY because a builder said "I built
X for this request" first; the lane supplies the "and it is running" half and
nothing else. When a lane reports a digest that is *not* the awaited one, the
awaited digest is cleared: it will never arrive, the lane has moved on, and
carrying a dead wait forward is how a row becomes a permanent alarm. The state
stays `built` and the row stays visible (mon-tc-06), because reopening it under
`build-failed` would borrow an event whose guard names a builder credential —
the lane did not fail the build, it left the image, and an audit trail is not
allowed to misattribute that.

NO BUILDER REPLAY CHECK, ON PURPOSE, STATED LOUDLY. The operator path refuses
a consumed nonce (mon-tc-03) because an operator decision is one-shot human
intent; mon-tc-05 asks no nonce of a build report, and CI retries are the
normal case. Duplicate protection is CAS: a re-reported build at an already
applied version is a 409 conflict, not a second transition. The asymmetry is
the spec's, not an oversight here — but a nonce-replay test against build
reports would fail, and this paragraph is where that fact lives.

Nothing here installs software. mon-tc-05 forbids any code path in this
capability executing a package manager, and this module never spawns a
process: it reads fields and moves rows.
"""

from __future__ import annotations

from . import toolchain_requests, toolchain_transitions

# History events this module records that are NOT table transitions. The
# precedented shape: decide records rejected-replay / rejected-conflict /
# rejected_credential_class without those being table rows either.
E_AWAITING_CLEARED = "awaiting-digest-cleared"


def _result(status: int, *, error: str | None = None, **extra) -> dict:
    return {"status": status, "error": error, **extra}


def accepted_gap_list(missing, rejection: str | None) -> list[str] | None:
    """The gap list convergence may believe, or None when none exists.

    // spec: mon-tc-01, mon-tc-05

    Only an ACCEPTED list may speak about tool presence: a refused submission
    says nothing about any tool, and reading a tool's absence-from-a-rejected-
    list as "this tool is present" is absence reported as health. This forwards
    the accepted list ITSELF, never an empty one — an earlier draft in
    `registry.py` wrote `[] if rejection is None`, which turned every honest
    "cargo is still missing" into "nothing is missing" and converged rows the
    lane had no business converging.
    test_digest_with_the_tool_still_missing_stays_built keeps that bug dead.

    Lives here, beside the consumer, rather than inline in `Registry.heartbeat`,
    because registry.py sits at DevGate's 500-line source hard limit and the
    rule is a rule of this module, not of the registry.
    """
    if rejection is not None or not isinstance(missing, list):
        return None
    return list(missing)


def find_request_by_id(data: dict, request_id: str) -> dict | None:
    for row in data.get("toolchain_requests", []):
        if row.get("id") == request_id:
            return row
    return None


def _missing_fields(build_id, profile_id, digest) -> list[str]:
    out = []
    if not isinstance(build_id, str) or not build_id:
        out.append("build_id")
    if not isinstance(profile_id, str) or not profile_id:
        out.append("profile_id")
    if not isinstance(digest, str) or not digest:
        out.append("digest")
    return out


def report_build(data: dict, request_id: str, *, credential_class: str | None,
                 credential_id: str | None, builder_identity: str | None,
                 profile_id, build_id, digest, note, expected_version,
                 now: str) -> dict:
    """Apply one builder report to one request row, under the caller's lock.

    // spec: mon-tc-05, mon-tc-03, mon-tc-04

    Order is load-bearing and copies `decide`'s reasoning: authenticate the
    *class* before any fact about the row is revealed, because a guard that
    inspects the row first tells an unauthenticated caller which ids exist and
    what state they are in. The class is looked up from the presented secret by
    the caller (toolchain_creds.classify); nothing here takes a class as a
    string the sender chose.

    An empty `digest` is not a malformed report, it is a *different report*:
    `build-failed` (the table's other builder event), which mon-tc-04 guards
    with "builder credential, note present". That reading is a judgement call
    — the spec never says how a failure arrives — and it is written here rather
    than hidden in an `if`, because the alternative (a separate boolean) is a
    field no spec mentions while an absent digest plainly means something.
    A failure clears the row's evidence fields: a digest from a failed build
    must not linger as something a lane could later "converge onto".
    """
    row = find_request_by_id(data, request_id)
    if credential_class is None:
        return _result(401, error="unknown_credential")
    if credential_class != "builder":
        if row is None:
            return _result(404, error="request_not_found")
        toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
            row, at=now, actor=builder_identity, principal=builder_identity,
            credential_id=credential_id,
            event=toolchain_transitions.REJECTED_CREDENTIAL_CLASS,
            frm=row.get("state"), to=row.get("state"),
            version_before=row.get("version"), version_after=row.get("version"),
            note=None))
        return _result(403, error=toolchain_transitions.REJECTED_CREDENTIAL_CLASS,
                       credential_class=credential_class or "unknown")
    if row is None:
        return _result(404, error="request_not_found")
    # mon-tc-05's "builder credential" is not just a class: the identity in the
    # audit row comes FROM the credential, never from the report body. A builder
    # registration without an identity is a hub misconfiguration and refusing
    # says so, because storing a report nobody can attribute is what an audit
    # trail exists to prevent.
    if not builder_identity:
        return _result(403, error="builder_identity_missing")

    failure = digest is None
    if not failure:
        missing = _missing_fields(build_id, profile_id, digest)
        if missing:
            # Refused before any audit row: an evidence report missing its
            # primary fields is not a claim about this request. The spec
            # forbids storing a rejected value, and a digest-shaped value in a
            # note field would be exactly that value wearing a sentence.
            return _result(400, error="build_evidence_incomplete",
                           fields=missing)
    if toolchain_transitions.note_too_long(note):
        return _result(400, error="note_too_long",
                       cap=toolchain_requests.DECISION_NOTE_MAX_CHARS)
    if failure and not (isinstance(note, str) and note):
        toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
            row, at=now, actor=builder_identity, principal=builder_identity,
            credential_id=credential_id, event="rejected-missing-note",
            frm=row.get("state"), to=row.get("state"),
            version_before=row.get("version"), version_after=row.get("version"),
            note=None))
        return _result(400, error="build_failure_requires_note")

    version = row.get("version")
    # CAS is required, not optional, on this route: without an expected_version
    # it is the only thing standing between a retried CI job and a second
    # transition, and mon-tc-05's whole point is that reaching a state takes
    # evidence rather than an extra report.
    if expected_version is None:
        return _result(400, error="expected_version_required")
    if expected_version != version:
        toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
            row, at=now, actor=builder_identity, principal=builder_identity,
            credential_id=credential_id, event="rejected-conflict",
            frm=row.get("state"), to=row.get("state"),
            version_before=version, version_after=version, note=None))
        return _result(409, error="version_conflict", current_version=version,
                       submitted_version=expected_version)

    event = "build-failed" if failure else "report-built"
    rule = toolchain_transitions.TRANSITIONS.get((row.get("state"), event))
    if rule is None:
        toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
            row, at=now, actor=builder_identity, principal=builder_identity,
            credential_id=credential_id, event="rejected-transition",
            frm=row.get("state"), to=row.get("state"),
            version_before=version, version_after=version, note=None))
        return _result(409, error="transition_not_in_table",
                       state=row.get("state"), event=event)

    if not failure:
        # "profile id matching the approved profile" is read strictly: both
        # sides must name a profile and they must agree. A row whose assignment
        # was moved to None after approval refuses rather than matching a
        # missing value to whatever the builder happened to build — the
        # profile-less lane is the state mon-tc-01 refuses to call healthy.
        approved = row.get("required_profile")
        if approved is None or approved != profile_id:
            toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
                row, at=now, actor=builder_identity, principal=builder_identity,
                credential_id=credential_id, event="rejected-transition",
                frm=row.get("state"), to=row.get("state"),
                version_before=version, version_after=version,
                note="profile_mismatch"))
            return _result(409, error="profile_mismatch",
                           approved_profile=approved)

    from_state = row["state"]
    row["state"] = rule["to"]
    row["version"] = version + 1
    row["builder_identity"] = builder_identity
    if failure:
        # The attempt is over; its evidence goes with it. History keeps the
        # record, the row keeps none of a failed build's claims.
        row["build_id"] = None
        row["lane_image_digest"] = None
    else:
        row["build_id"] = build_id
        row["lane_image_digest"] = digest
    if rule["to"] != "built":
        row["fulfilled_at"] = None
    toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
        row, at=now, actor=builder_identity, principal=builder_identity,
        credential_id=credential_id, event=event, frm=from_state, to=rule["to"],
        version_before=version, version_after=version + 1, note=note))
    return _result(200, error=None, state=rule["to"], version=version + 1)


def note_lane_evidence(runner: dict, data: dict, lane_image_digest,
                       missing, now: str,
                       probe_complete: bool | None = None) -> int:
    """Write the lane's own image digest and run every digest-based consequence.

    // spec: mon-tc-05, mon-tc-04, mon-tc-06

    Called from `Registry.heartbeat` after the gap report has been recorded and
    coverage noted, so "the probe passes" is judged against the freshest thing
    the lane actually said. Returns how many rows changed state, which exists
    for tests and triage, not for the spoke.

    ``lane_image_digest`` follows the registry's presence-not-truth convention:
    pass the module-level ``UNREPORTED`` sentinel (the same object
    `hub.registry` and `hub.server` use) to mean "the lane said nothing about
    its image", which touches nothing. A non-empty string is stored; an
    explicit None clears it. Anything else — a dict, a number — is a malformed
    field from an untrusted host and is dropped rather than coerced, because
    ``str(12345)`` is digest-shaped enough to converge something if it ever
    reaches a comparison.

    ``missing`` is the accepted gap list from THIS heartbeat, or None when the
    heartbeat carried no gap field. The distinction is mon-tc-06's whole
    coverage story and it decides convergence here too: a report in which the
    row's tool is absent is a passing probe, and no report is not a failed
    probe but also never a passing one on its own.
    """
    from .registry import UNREPORTED as _ABSENT

    # The sentinel skips the WRITE and nothing else. "No opinion about my image
    # digest this tick" is not "no opinion about this request": a row can
    # converge on the stored digest against a later passing probe, and
    # short-circuiting here would silently forbid that.
    if lane_image_digest is _ABSENT:
        lane_image_digest = runner.get("lane_image_digest")
    elif isinstance(lane_image_digest, str) and lane_image_digest:
        runner["lane_image_digest"] = lane_image_digest
    elif lane_image_digest is None:
        runner["lane_image_digest"] = None

    reported = runner.get("lane_image_digest")
    changed = 0
    for row in data.get("toolchain_requests", []):
        if row.get("lane") != runner.get("name"):
            continue
        state = row.get("state")
        if state == "built":
            changed += _converge_or_clear(row, reported, missing,
                                          probe_complete, now)
        elif state == "fulfilled":
            changed += _regress_if_reported(row, missing, now)
    return changed


def _probe_passes(row: dict, missing, probe_complete: bool | None) -> bool:
    """This tick's accepted evidence that the tool is present (mon-tc-05).

    ``missing`` is the ACCEPTED gap list or None: a refused list arrives here as
    None and returns False, because "cargo is not in a list we rejected" says
    nothing about cargo — reading it as presence is absence reported as health
    with a green check on it. The spoke's own probe-incomplete flag vetoes even
    a clean list: an incomplete run that found nothing missing found nothing.
    """
    if probe_complete is False:
        return False
    if not isinstance(missing, list):
        return False
    return row.get("tool") not in missing


def _converge_or_clear(row: dict, reported_digest, missing,
                       probe_complete, now: str) -> int:
    awaiting = row.get("lane_image_digest")
    if not awaiting or not reported_digest:
        return 0
    if reported_digest != awaiting:
        if row.get("awaiting_cleared") == reported_digest:
            return 0  # already cleared for this exact digest; no log spam
        row["lane_image_digest"] = None
        row["awaiting_cleared"] = reported_digest
        toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
            row, at=now, actor=None, principal=None, credential_id=None,
            event=E_AWAITING_CLEARED, frm=row.get("state"), to=row.get("state"),
            version_before=row.get("version"), version_after=row.get("version"),
            note="lane reported a different image digest; the awaited build "
                 "will never converge. State stays built and visible (mon-tc-06)."))
        return 0
    if not _probe_passes(row, missing, probe_complete):
        return 0  # digest is right, probe evidence is not: stays built
    from_state = row["state"]
    version = row.get("version")
    rule = toolchain_transitions.TRANSITIONS.get((from_state, "converge"))
    if rule is None:  # unreachable for `built`, defended against anyway
        return 0
    row["state"] = rule["to"]
    row["version"] = version + 1
    row["fulfilled_at"] = now
    row.pop("awaiting_cleared", None)
    toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
        row, at=now, actor=None, principal=None, credential_id=None,
        event="converge", frm=from_state, to=rule["to"],
        version_before=version, version_after=version + 1,
        note=None))
    return 1


def _regress_if_reported(row: dict, missing, now: str) -> int:
    """A fulfilled row whose tool the lane just reported missing (mon-tc-04)."""
    if not isinstance(missing, list) or row.get("tool") not in missing:
        return 0
    from_state = row["state"]
    version = row.get("version")
    rule = toolchain_transitions.TRANSITIONS.get((from_state, "gap-regressed"))
    if rule is None:
        return 0
    row["state"] = rule["to"]
    row["version"] = version + 1
    row["fulfilled_at"] = None
    # The fulfilled image is gone; so is the build evidence behind it, or a
    # later heartbeat could "converge" onto an image that already regressed.
    row["build_id"] = None
    row["lane_image_digest"] = None
    toolchain_transitions.append_history(row, toolchain_transitions.audit_record(
        row, at=now, actor=None, principal=None, credential_id=None,
        event="gap-regressed", frm=from_state, to=rule["to"],
        version_before=version, version_after=version + 1,
        note="lane re-reported this tool missing after fulfillment"))
    return 1


__all__ = ["report_build", "note_lane_evidence", "find_request_by_id",
           "E_AWAITING_CLEARED"]
