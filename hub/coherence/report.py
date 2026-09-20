# // spec: coh-pol-03, coh-pol-06
"""Advisory-age and exception-expiry reporting (coh-pol-03, coh-pol-06).

Reporting is derived, never ambient: ages are computed against a supplied
reference time (a context's evaluation_time), never the host clock, so a
report is reproducible. Advisory is a stage with an expiry — a repo that
passes max_advisory_age without an approved renewal must be visible here
(the LobsterWars anti-goal, made measurable).
"""
from datetime import datetime, timezone

DAY = 86400


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def advisory_age(repo_record: dict, max_advisory_age_days: int,
                 reference_time: str) -> dict:
    """Age vs the central cap, in the terms the ENFORCEMENT path needs.

    Distinct from `advisory_status` below, which is the REPORTING view and
    deliberately scoped to the Stage-1 ordinal: this answers "is the shelter
    spent at `reference_time`", which coh-pol-03 bounds the promotion of a
    repository that has ALREADY reached the ratchet (design.md round-16).
    Stretching the reporting view's `stage != 1` early return into the run
    path would make the cap inert for exactly the repositories it targets.

    Age is computed from the trusted reference time, never the host clock.
    """
    ref = _parse(reference_time)
    out = {"advisory_age_days": None,
           "max_advisory_age_days": max_advisory_age_days,
           "expired": False, "notes": []}
    stage = repo_record.get("stage")
    if stage == 0:
        # Nothing blocks at inventory, so an expired cap has no consequence
        # to report. This is the ONE stage where age is not measured.
        out["notes"].append("inventory stage; cap does not apply")
        return out
    started = repo_record.get("advisory_started")
    if not started:
        # NO record is NOT an expired one. The escalation must be silent when
        # the caller supplies nothing to measure — inferring an expiry from a
        # missing field would block every run that did not opt into the
        # regime, and would report a violation nobody actually committed.
        # (The REPORTING view keeps its opposite reading for the Stage-1
        # ordinal, where a missing start on a dwelling repo IS the violation
        # coh-pol-03 names; this is the enforcement path, where silence is
        # the only honest verdict available.)
        out["notes"].append("no recorded advisory start; cap not measured")
        return out
    age_days = (ref - _parse(started)).total_seconds() / DAY
    out["advisory_age_days"] = round(age_days, 2)
    expiry = repo_record.get("advisory_expiry")
    if expiry:
        out["advisory_expiry"] = expiry
        if _parse(expiry) <= ref:
            out["expired"] = True
            out["notes"].append(
                "advisory expiry reached; promotion requires escalation or an "
                "approved renewal (coh-pol-03)")
    elif max_advisory_age_days and age_days > max_advisory_age_days:
        out["expired"] = True
        out["notes"].append(
            f"advisory age {out['advisory_age_days']}d exceeds the central "
            f"cap of {max_advisory_age_days}d with no renewal recorded")
    return out


def advisory_status(repo_record: dict, max_advisory_age_days: int,
                    reference_time: str) -> dict:
    """Advisory age vs the central cap for one repo at one reference time.

    The REPORTING view: it measures the Stage-1 dwelling state alone, so a
    record past Stage 1 reports "cap does not apply" here. Enforcement uses
    `advisory_age`, which is not stage-gated that way (round-16).
    """
    ref = _parse(reference_time)
    stage = repo_record.get("stage")
    out = {"repo_stage": stage, "owner": repo_record.get("owner"),
           "next_stage": repo_record.get("next_stage"),
           "advisory_age_days": None, "max_advisory_age_days":
               max_advisory_age_days,
           "expired": False, "notes": []}
    if stage != 1:
        out["notes"].append("not in advisory stage; cap does not apply")
        return out
    started = repo_record.get("advisory_started")
    if not started:
        out["expired"] = True
        out["notes"].append("advisory stage without a recorded start — "
                            "bounded-adoption requirement is violated")
        return out
    age = advisory_age(repo_record, max_advisory_age_days, reference_time)
    out.update({k: v for k, v in age.items() if k != "notes"})
    out["notes"].extend(age["notes"])
    return out


def exception_status(exceptions: list, reference_time: str) -> list:
    """Per-exception remaining life; expired entries are escalation flags."""
    ref = _parse(reference_time)
    rows = []
    for ex in exceptions:
        exp = ex.get("expires_at")
        remaining = None
        if exp:
            try:
                remaining = (_parse(exp) - ref).total_seconds() / DAY
            except ValueError:
                rows.append({"exception_id": ex.get("exception_id"),
                             "error": f"unparseable expires_at {exp!r}"})
                continue
        rows.append({
            "exception_id": ex.get("exception_id"),
            "assertion_id": ex.get("assertion_id"),
            "owner": ex.get("owner"),
            "expires_at": exp,
            "days_remaining": None if remaining is None else round(remaining, 2),
            "expired": bool(remaining is not None and remaining <= 0),
        })
    return rows


def summarize(result: dict, context: dict, repo_record: dict,
              max_advisory_age_days: int,
              exceptions: list = None) -> dict:
    """One report object joining result + context + adoption state.

    Advisory age comes from the CONTEXT's evaluation_time (coh-ctx-01),
    never from when the report is generated — the same sealed result always
    reports the same age.
    """
    from . import context as _ctx
    return {
        # Derived label only (coh-ctx-02): the mode IS the authoritative
        # stage's name; nothing in the pipeline reads it for behavior.
        "mode": _ctx.mode_for_stage(context.get("stage")),
        "decision": result.get("decision"),
        "subject_digest": result.get("subject_digest"),
        "context_digest": context.get("context_digest"),
        "promotion_authorizing": context.get("semantics",
                                             "fresh-promotion")
        == "fresh-promotion",
        "advisory": advisory_status(repo_record, max_advisory_age_days,
                                    context["evaluation_time"]),
        "exceptions": exception_status(exceptions or [],
                                       context["evaluation_time"]),
    }
