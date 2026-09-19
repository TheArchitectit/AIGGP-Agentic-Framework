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


def advisory_status(repo_record: dict, max_advisory_age_days: int,
                    reference_time: str) -> dict:
    """Advisory age vs the central cap for one repo at one reference time."""
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
