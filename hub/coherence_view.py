# // spec: coh-int-02, coh-int-05, coh-int-06, coh-int-07
"""Hub-side coherence-gate detection, two independent channels.

Channel A (workflow runs): presence / conclusion / recency of the
configured coherence workflow. Channel B (check-runs on watched
branches): a gate that never appears on a branch the fleet watches.

Neither channel substitutes for the other. A 404 on one channel's API is
not a finding for that channel. Kept out of hub/monitor.py to stay under
the 500-line hard limit; the MonitorLoop calls these as functions.
"""
from datetime import datetime, timezone


def check_workflow_runs(repo, config, client, raise_alert, parse_iso,
                        non_passing) -> None:
    """Channel A: workflow presence / conclusion / recency.

    A MISSING coherence workflow is an alert, not silence (coh-pol-07). A
    SKIPPED run is its own class (coh-int-06). Any other non-passing
    conclusion surfaces via `non_passing`. A stale run is overdue.
    """
    branches = [b for b in config.watched_branches if b != "default"]
    if not branches:
        raise_alert(
            repo, "coherence_unconfigured", "?",
            detail="no watched branches configured — the coherence check "
                   "is an explicit no-op, not a pass; set "
                   "HUB_WATCHED_BRANCHES to enable it")
        return

    match = config.coherence_workflow_match
    result = client.get_with_backoff(
        f"/repos/{repo}/actions/workflows?per_page=100")
    if result is None:
        return
    status, body = result
    if status != 200:
        return

    wf = None
    for candidate in body.get("workflows", []):
        if match.lower() in candidate.get("name", "").lower():
            wf = candidate
            break

    if wf is None:
        raise_alert(
            repo, "coherence_missing", "?",
            detail=f"no workflow matching '{match}' found — the coherence "
                   f"gate has been removed or renamed")
        return

    result = client.get_with_backoff(
        f"/repos/{repo}/actions/workflows/{wf['id']}/runs?per_page=100")
    if result is None:
        return
    status, body = result
    if status != 200:
        return

    latest = None
    for run in body.get("workflow_runs", []):
        if run.get("head_branch") in branches:
            latest = run
            break
    if latest is None:
        raise_alert(
            repo, "coherence_missing", "?",
            detail=f"no run of workflow '{wf['name']}' on any watched "
                   f"branch ({', '.join(branches)})")
        return

    if latest.get("conclusion") in non_passing:
        raise_alert(
            repo, "coherence_failure", "?",
            detail=f"latest coherence run did not pass "
                   f"(conclusion={latest.get('conclusion')}): "
                   f"{latest.get('html_url', '')}")
        return

    if latest.get("conclusion") == "skipped":
        raise_alert(
            repo, "coherence_skipped", "?",
            detail=f"latest coherence run on branch "
                   f"{latest.get('head_branch')} reported SKIPPED: "
                   f"{latest.get('html_url', '')}")
        return

    completed_at = parse_iso(latest.get("completed_at"))
    if completed_at is None:
        raise_alert(
            repo, "coherence_overdue", "?",
            detail="latest coherence run has no completion timestamp")
        return
    max_age_sec = 24 * 3600 + config.drift_grace_min * 60
    age_sec = (datetime.now(timezone.utc) - completed_at).total_seconds()
    if age_sec > max_age_sec:
        raise_alert(
            repo, "coherence_overdue", "?",
            detail=f"last coherence run {age_sec / 3600:.1f}h ago "
                   f"(max {max_age_sec / 3600:.1f}h)")


def check_check_runs(repo, config, client, raise_alert, watched_branches,
                     non_passing) -> None:
    """Channel B: check-runs named like the coherence gate on the branches
    the fleet watches. A gate that reports nothing is not a gate."""
    match = config.coherence_workflow_match.lower()
    for branch in watched_branches(repo):
        result = client.get_with_backoff(
            f"/repos/{repo}/commits/{branch}?per_page=1")
        if result is None:
            continue
        status, body = result
        if status != 200:
            continue
        sha = body.get("sha", "")
        if not sha:
            continue

        result = client.get_with_backoff(
            f"/repos/{repo}/commits/{sha}/check-runs?per_page=100")
        if result is None:
            continue
        status, body = result
        if status != 200:
            continue

        coherence_checks = [
            c for c in body.get("check_runs", [])
            if match in (c.get("name") or "").lower()]
        if not coherence_checks:
            raise_alert(
                repo, "coherence_absent", "?",
                detail=(f"no check-run matching '{match}' on branch "
                        f"{branch} (sha {sha[:8]}) — the coherence "
                        f"gate must run or report SKIPPED"))
            continue

        for check in coherence_checks:
            conclusion = check.get("conclusion")
            if conclusion in non_passing:
                raise_alert(
                    repo, "coherence_failure", check.get("name", "?"),
                    detail=(f"conclusion={conclusion}, branch={branch}, "
                            f"sha={sha[:8]}"))