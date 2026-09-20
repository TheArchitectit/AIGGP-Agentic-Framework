# // spec: coh-ev-02, coh-ev-03, coh-ev-06
"""Verification semantics and claim lifecycle (fw-* audit architecture).

The framework's core promise is that a completion claim is only ever as
strong as its evidence. This module makes that promise executable:

  - an explicit state vocabulary (REQUESTED..VERIFIED) with a frozen
    transition table — states are never silently collapsed, and UNKNOWN
    can never be promoted to success by any code path;
  - claim records that bind evidence to the exact subject state it was
    collected against (digest-bound), so evidence goes STALE when the
    thing it proved changes;
  - independent verification support: a claim's executor and its verifier
    can be different callables, and only an INDEPENDENT check may raise a
    claim to VERIFIED.

Every claim serializes canonically and carries a digest, so a claim file
can be sealed and later re-verified exactly like evidence bundles.
"""
from . import canon

# --- the frozen state vocabulary -------------------------------------------
#
# Distinction the whole system exists to enforce: a convincing message is
# REQUESTED, not VERIFIED. The states form a strict ladder; sideways jumps
# and skips are rejected.

REQUESTED = "REQUESTED"      # wanted; nothing has happened yet
PLANNED = "PLANNED"          # a concrete plan exists
ATTEMPTED = "ATTEMPTED"      # work started; outcome unknown
EXECUTED = "EXECUTED"        # work ran to a stop; result unexamined
COMPLETED = "COMPLETED"      # the actor believes the work is done
TESTED = "TESTED"            # a check ran against the work
OBSERVED = "OBSERVED"        # the check's output was actually captured
VERIFIED = "VERIFIED"        # independent verification confirmed the claim
BLOCKED = "BLOCKED"          # an external dependency prevents progress
FAILED = "FAILED"            # the work produced a negative outcome
UNKNOWN = "UNKNOWN"          # nothing can be asserted — the honest default

# Ladder order for forward promotion. REQUESTED -> ... -> VERIFIED. PLANNED
# is an optional rung: work may start (REQUESTED -> ATTEMPTED) without a
# recorded plan — a missing plan is a documentation gap, not a proof gap.
# FAILED, BLOCKED and UNKNOWN are terminal side-states: they may absorb a
# claim from any state, but only fresh evidence (a new claim) can leave
# them — a recovery is a new claim referencing the old one, never an edit of
# a FAILED claim into VERIFIED.
LADDER = [REQUESTED, PLANNED, ATTEMPTED, EXECUTED, COMPLETED,
          TESTED, OBSERVED, VERIFIED]

# Forward transitions. PLANNED is an optional rung: work may start
# (REQUESTED -> ATTEMPTED) without a recorded plan — a missing plan is a
# documentation gap, not a proof gap. Every other rung must be earned in
# order; a skip would let an unexecuted state claim its successor's strength.
_FORWARD = {LADDER[i]: LADDER[i + 1] for i in range(len(LADDER) - 1)}
_FORWARD[REQUESTED] = {PLANNED, ATTEMPTED}

# A transition into a terminal state is legal from any state (reality
# interrupts work at any point, and refuting even a VERIFIED claim is how
# verification stays honest). Backward transitions on the ladder are
# forbidden: unwinding is modelled as a new claim, so history cannot be
# rewritten.
_TERMINAL = {BLOCKED, FAILED, UNKNOWN}

CLAIM_API_VERSION = "devgate.verification.claim/v1"


class VerificationError(ValueError):
    """An illegal verification-state operation was attempted."""


def can_transition(current: str, target: str) -> bool:
    """True when current -> target is legal under the frozen table."""
    if current not in LADDER and current not in _TERMINAL:
        raise VerificationError(f"unknown current state {current!r}")
    if target not in LADDER and target not in _TERMINAL:
        raise VerificationError(f"unknown target state {target!r}")
    if current == target:
        return True
    # Demotion is always legal, including refuting a VERIFIED claim: a
    # downgrade can never fabricate success, so nothing stands in its way.
    if target in _TERMINAL:
        return True
    # An independent verifier certifies the WHOLE claim at once: it may
    # reach VERIFIED from any pre-VERIFIED state without the intermediate
    # rungs having been recorded individually (TESTED/OBSERVED document the
    # actor's own process; the independent check supersedes them).
    if target == VERIFIED and current in LADDER:
        return True
    allowed = _FORWARD.get(current)
    return target in allowed if isinstance(allowed, set) else allowed == target


def transition(claim: dict, target: str, *, reason: str = "",
               observation: dict = None, _independent: bool = False) -> dict:
    """Move a claim to `target`, enforcing the frozen transition table.

    Reaching VERIFIED requires an `observation` recorded by an INDEPENDENT
    verifier (see `verify_independently`); `transition(claim, VERIFIED)` by
    the actor itself raises rather than self-certifying. Any illegal jump
    raises VerificationError — callers can never accidentally promote
    UNKNOWN work into a success state.
    """
    current = claim.get("state")
    if target == VERIFIED and current != VERIFIED and not _independent:
        raise VerificationError(
            "VERIFIED requires independent verification; use "
            "verify_independently() — an actor cannot certify itself")
    if not can_transition(current, target):
        raise VerificationError(
            f"illegal transition {current!r} -> {target!r}")
    claim["state"] = target
    claim["transitions"].append({
        "to": target,
        "reason": reason or None,
    })
    return claim


def new_claim(claim_id: str, requirement: str, *, subject_digest: str = None,
              actor: str = "") -> dict:
    """A claim starts at REQUESTED with empty evidence and a transition log."""
    return {
        "api_version": CLAIM_API_VERSION,
        "claim_id": claim_id,
        "requirement": requirement,
        "state": REQUESTED,
        "actor": actor or None,
        "subject_digest": subject_digest,
        "bound_digests": {},
        "evidence_refs": [],
        "independent_verification": None,
        "transitions": [{"to": REQUESTED, "reason": "created"}],
    }


def bind(claim: dict, role: str, digest: str) -> dict:
    """Bind a content digest to the claim under a role name.

    Bound digests are the staleness anchors: code, config, environment —
    anything whose change invalidates the evidence must be bound here at
    claim time. An unbound input is an UNVERIFIED assumption, so callers
    should bind everything the claim's truth depends on.
    """
    if not isinstance(role, str) or not role:
        raise VerificationError("bind role must be a non-empty string")
    if not isinstance(digest, str) or not digest:
        raise VerificationError("bind digest must be a non-empty string")
    claim["bound_digests"][role] = digest
    return claim


def attach_evidence(claim: dict, evidence_ref: str) -> dict:
    """Attach an evidence reference (path/digest of a sealed artifact)."""
    if not isinstance(evidence_ref, str) or not evidence_ref:
        raise VerificationError("evidence_ref must be a non-empty string")
    claim["evidence_refs"].append(evidence_ref)
    return claim


def staleness(claim: dict, observed_digests: dict) -> list:
    """Compare bound digests against the world as it is NOW.

    Returns the list of bound roles whose content changed since the claim's
    evidence was collected. An empty list means every anchor still matches —
    note this is necessary, not sufficient, for the claim to still hold.
    """
    return sorted(
        role for role, digest in claim["bound_digests"].items()
        if observed_digests.get(role) != digest
    )


def revalidate(claim: dict, observed_digests: dict) -> str:
    """Return the claim's effective state against current reality.

    Digest drift demotes the effective state to UNKNOWN — the recorded
    verification was real but no longer applies; it must be re-established,
    never assumed. The claim record itself is not rewritten: history stays,
    the caller decides what to do with the answer.
    """
    if staleness(claim, observed_digests):
        return UNKNOWN
    return claim["state"]


def verify_independently(claim: dict, verifier, *, observed_digests: dict = None,
                         reason: str = "") -> dict:
    """Raise the claim to VERIFIED through a verifier the actor does not own.

    `verifier(claim) -> (ok: bool, observation: dict)` runs OUTSIDE the
    claim's actor; its observation (what was executed, what was seen) is
    recorded on the claim. The verifier is re-invoked against reality when
    `observed_digests` are supplied and stale — a verifier's yes from an
    older world is not a yes for this one.

    A FAILED independent check demotes the claim to FAILED with the negative
    observation retained as evidence. Either way the outcome is recorded;
    nothing is silently swallowed.
    """
    if observed_digests is not None and staleness(claim, observed_digests):
        raise VerificationError(
            "claim evidence is stale; re-verify against current reality "
            "with a fresh claim")
    ok, observation = verifier(claim)
    observation = observation or {}
    record = {
        "verifier": getattr(verifier, "__name__", "independent-verifier"),
        "ok": bool(ok),
        "observation": observation,
    }
    claim["independent_verification"] = record
    if not ok:
        transition(claim, FAILED, reason=reason or "independent check failed")
        return claim
    if observed_digests is not None and staleness(claim, observed_digests):
        transition(claim, UNKNOWN,
                   reason="digests changed between verification and recording")
        return claim
    transition(claim, VERIFIED, reason=reason or "independent check confirmed",
               _independent=True)
    return claim


def summarize(claims: list) -> dict:
    """Honest accounting: counts by state, with UNVERIFIED called out.

    Anything not VERIFIED is UNVERIFIED for completion purposes — TESTED,
    COMPLETED and even OBSERVED are progress markers, not proof. The summary
    makes it impossible to average a claim into success.
    """
    counts = {}
    for c in claims:
        counts[c["state"]] = counts.get(c["state"], 0) + 1
    verified = counts.get(VERIFIED, 0)
    unverified = len(claims) - verified
    return {
        "total": len(claims),
        "by_state": counts,
        "verified": verified,
        "unverified": unverified,
    }


def digest_claim(claim: dict) -> str:
    """Canonical claim digest — claims can be sealed and re-verified."""
    return canon.digest_obj("decision/v1", claim)


# --- digest anchoring helpers -----------------------------------------------

def digest_content(role_tag: str, payload: bytes) -> str:
    """Digest raw content for binding (re-exported shape for callers)."""
    return canon.digest_bytes(role_tag, payload)


def content_commitment(root) -> str:
    """A whole-tree content commitment for bind() anchors.

    Binds every file under `root` (relative path + raw digest, canonically
    serialized). Unlike a single manifest digest, a commitment over the
    directory detects tamper of ANY member — including files the manifest
    itself does not commit to — so a claim anchored with
    `bind(claim, "evidence-tree", content_commitment(bundle))` goes stale
    when any byte in the bundle changes (fw-ev-05: digest equality of an
    index is not content integrity of the indexed files).
    """
    import hashlib
    from pathlib import Path as _Path

    root_p = _Path(root)
    if not root_p.is_dir():
        raise VerificationError(f"commitment root is not a directory: {root}")
    entries = []
    for p in sorted(root_p.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root_p).as_posix()
        h = hashlib.sha256()
        h.update(p.read_bytes())
        entries.append({"path": rel, "sha256": "sha256:" + h.hexdigest()})
    return canon.digest_obj("evidence-manifest/v1",
                            {"commitment": "tree/v1", "entries": entries})
