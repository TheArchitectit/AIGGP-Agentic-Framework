#!/usr/bin/env python3
"""hub_alert.py - deduped issue alerts for fleet workflows.

  hub_alert.py --key secret_fleet_sweep --report FILE
  hub_alert.py --key required_check_red_on_main --detail TEXT

The image-pin divergence alert in ci.yml already calls
hub.alerts.GitHubIssueNotifier inline to raise a deduped GitHub issue on
this repo. That is the same channel the fleet sweep needs, so this script
is a thin wrapper over the same call rather than a second notifier:

  * one open issue per key (SGR-11) - the notifier already dedups on
    (repo, check-class, runner) and comments on an open issue instead of
    filing a new one, re-opening a closed one when the same key fails
    again;
  * the body carries counts and redacted locations, never a matched
    value. Extraction is by field name (`state`, `uncovered`, and
    `locations[].rule/path/line/commit` only). A report that carries a
    planted `Secret` field must not leak it - the same by-name copy rule
    the fleet script's record() uses.

Exit: 0 the alert was delivered (or skipped, see --dry-run), 2 the alert
API was unreachable, 3 bad invocation. An alert that could not be raised
is non-zero because a silent alert is the same failure as a silent scanner.

// spec: mon-alert-01
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Fields the report carries that may be quoted into the issue body. A field
# outside this set is skipped even if its name looks innocuous, because the
# failure mode the skip exists to catch is a name that used to mean
# "identifier" and now means "token".
_LOCATION_FIELDS = ("rule", "path", "line", "commit")

# Template-provenance drift (SGA-21 / SGR-11): the deduped drift issue must
# name the template and BOTH hashes, never merely count them. Same by-name
# rule as locations — only these fields survive out of a drift entry. The
# hashes are truncated to 12 hex chars, the shape the SGR-06 drift alert uses.
_DRIFT_FIELDS = ("template", "kind", "pinned", "upstream", "actual", "version")
_DRIFT_HASH_LEN = 12

# Upper bound on locations quoted into one issue body. Measured on the first
# live fleet sweep: 478,452 locations produced a comment GitHub rejected with
# HTTP 422, which dropped the dedupe marker — every subsequent night would
# then re-search and re-file instead of commenting (SGR-11's exact failure
# mode). The full list lives in the run's artifact; the issue says how many
# were omitted.
MAX_BODY_LOCATIONS = 40

# T-14: an unfetchable repository must be NAMED in the alert, not merely
# counted — "unfetchable=4" tells the operator the fleet has a hole, the
# names tell them which declaration line to disposition. Reasons are quoted
# from the report (the T-31 census has already refused to commit the report
# if any carried a value shape) and truncated per line.
MAX_BODY_UNSCANNED = 40
REASON_MAX_CHARS = 100


def extract_summary(report: dict) -> tuple[str, int, int, list[dict]]:
    """(summary, uncovered_total, scanned_total, safe_locations) by field name.

    Any key not in _LOCATION_FIELDS is dropped without comment: a field that
    is not expected must not silently become "expected" because a future
    edit added it to a list that is read by name. Callers that need the
    total unread state should read `states` in the report, not this module.
    """
    if not isinstance(report, dict):
        return "report is not a JSON object", 0, 0, []

    states = report.get("states") or {}
    if not isinstance(states, dict):
        states = {}
    scanned = sum(states.values()) if states else len(report.get("repos", []) or [])

    uncovered_total = 0
    safe: list[dict] = []
    for entry in report.get("repos", []) or []:
        if not isinstance(entry, dict):
            continue
        uncovered_total += int(entry.get("uncovered", 0) or 0)
        # `findings` and `uncovered` are counts the caller may name; the
        # per-finding list is `locations`, filtered by name.
        for loc in entry.get("locations", []) or []:
            if not isinstance(loc, dict):
                continue
            kept = {k: loc[k] for k in _LOCATION_FIELDS if k in loc}
            if kept:
                safe.append(kept)

    counts = ", ".join(f"{k}={v}" for k, v in sorted(states.items())) or "states=?"
    summary = (
        f"declared={report.get('declared', '?')}, "
        f"scanned={report.get('scanned', scanned)}, {counts}, "
        f"uncovered_total={uncovered_total}, locations={len(safe)}"
    )
    return summary, uncovered_total, scanned, safe


def _drift_line(d: dict) -> str | None:
    """One template-drift entry as body text, quoted by field name only.

    A key outside _DRIFT_FIELDS is dropped without comment — the same
    contract as locations[], and for the same reason: a planted `Secret`
    in a drift entry must not survive into an issue body. Hashes are
    truncated to _DRIFT_HASH_LEN so the line stays bounded even if a
    caller hands in a long digest.
    """
    if not isinstance(d, dict):
        return None
    kept = {k: d[k] for k in _DRIFT_FIELDS if k in d}
    if not kept:
        return None

    def short(v: object) -> str:
        s = str(v)
        if len(s) > _DRIFT_HASH_LEN and all(c in "0123456789abcdefABCDEF" for c in s):
            return s[:_DRIFT_HASH_LEN]
        return s[:REASON_MAX_CHARS]

    template = short(kept.get("template", "?"))
    kind = short(kept.get("kind", "?"))
    pinned = short(kept.get("pinned", "?")) if "pinned" in kept else "?"
    other = kept.get("upstream", kept.get("actual")) if "upstream" in kept or "actual" in kept else None
    other_s = short(other) if other is not None else "?"
    version = kept.get("version")
    ver = f"  (pin {short(version)})" if version is not None else ""
    return f"{template}  {kind}  {pinned} → {other_s}{ver}"


def detail_from_report(report: dict) -> str:
    summary, _uncovered, _scanned, locations = extract_summary(report)
    lines = [summary, ""]
    if locations:
        shown = locations[:MAX_BODY_LOCATIONS]
        lines.append("locations (rule, path, line, commit):")
        for loc in shown:
            line = loc.get("line", "?")
            commit = loc.get("commit", "?")
            lines.append(
                f"  {loc.get('rule', '?')}  {loc.get('path', '?')}"
                f":{line}  ({commit})"
            )
        if len(locations) > len(shown):
            lines.append(f"  … {len(locations) - len(shown)} more locations: "
                         "see this run's secret-fleet-report artifact")
    else:
        lines.append("no redacted locations to list (state == "
                     "unfetchable/unscannable with no matching rule)")
    # T-14: name the holes. A count of unfetchable/unscannable repos without
    # names is an un-actionable alert — the operator cannot disposition a
    # declaration line they cannot identify.
    holes = [e for e in (report.get("repos") or [])
             if isinstance(e, dict)
             and e.get("state") in ("unfetchable", "unscannable")]
    if holes:
        lines.append("")
        lines.append("could not be scanned (name — reason):")
        for e in holes[:MAX_BODY_UNSCANNED]:
            reason = str(e.get("reason") or "")[:REASON_MAX_CHARS]
            lines.append(f"  {e.get('name', '?')} — {e.get('state')}"
                         f"{': ' + reason if reason else ''}")
        if len(holes) > MAX_BODY_UNSCANNED:
            lines.append(f"  … {len(holes) - MAX_BODY_UNSCANNED} more: "
                         "see this run's secret-fleet-report artifact")
    # SGA-21 / SGR-11: the deduped drift issue. Lock-level drift is one
    # finding per sweep (upstream moved); per-tree drift/unlocked is one
    # finding per repo. Either way the body NAMES the template and both
    # hashes — "drift=4" cannot be dispositioned.
    drift_lines: list[str] = []
    lp = report.get("lock_provenance")
    if isinstance(lp, dict):
        for d in lp.get("drift") or []:
            line = _drift_line(d)
            if line:
                drift_lines.append(f"  {line}")
    for entry in report.get("repos") or []:
        if not isinstance(entry, dict):
            continue
        prov = entry.get("provenance")
        if not isinstance(prov, dict):
            continue
        who = str(entry.get("name", "?"))[:REASON_MAX_CHARS]
        for d in prov.get("drift") or []:
            line = _drift_line(d)
            if line:
                drift_lines.append(f"  {who}: {line}")
        for name in prov.get("unlocked") or []:
            drift_lines.append(f"  {who}: unlocked {str(name)[:REASON_MAX_CHARS]}")
    if drift_lines:
        lines.append("")
        lines.append("template drift (template, kind, hashes, pin version):")
        shown_d = drift_lines[:MAX_BODY_LOCATIONS]
        lines.extend(shown_d)
        if len(drift_lines) > len(shown_d):
            lines.append(f"  … {len(drift_lines) - len(shown_d)} more: "
                         "see this run's report artifact")
    # The body is counts, locations, unscanned names, and template drift.
    # It is never a copy of the report, and never a field that could carry
    # a value.
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hub_alert.py",
                                description="Deduped fleet alert via hub.alerts.")
    p.add_argument("--key", required=True,
                   help="alert key (dedup class), e.g. secret_fleet_sweep")
    p.add_argument("--report",
                   help="sweep report JSON to summarise into the body")
    p.add_argument("--detail",
                   help="literal detail text (mutually exclusive with --report)")
    p.add_argument("--repo",
                   default=os.environ.get("ALERT_REPO",
                                          "TheArchitectit/AIGGP-Agentic-Framework"),
                   help="owner/repo that raises the alert (default: ALERT_REPO "
                        "or TheArchitectit/AIGGP-Agentic-Framework)")
    p.add_argument("--runner",
                   default=os.environ.get("ALERT_RUNNER", "workflow"),
                   help="runner tag the alert is attributed to (default: "
                        "ALERT_RUNNER or 'workflow')")
    p.add_argument("--api-base",
                   default=os.environ.get("GITHUB_API_URL",
                                          "https://api.github.com"))
    p.add_argument("--token",
                   default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    p.add_argument("--alerts-dir",
                   default=os.environ.get("RUNNER_TEMP", "/tmp"))
    p.add_argument("--dry-run", action="store_true",
                   help="print the body and exit 0 without touching the API")
    args = p.parse_args(argv)

    if bool(args.report) == bool(args.detail):
        p.error("exactly one of --report or --detail is required")
    if args.dry_run and args.report is None:
        p.error("--dry-run requires --report (it prints the body, nothing else)")

    if args.report:
        try:
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[hub_alert] cannot read report {args.report}: {exc}",
                  file=sys.stderr)
            return 3
        body = detail_from_report(report)
    else:
        body = args.detail

    if args.dry_run:
        print(body, file=sys.stdout)
        return 0

    if not args.token:
        print("[hub_alert] missing token: set GH_TOKEN or GITHUB_TOKEN, "
              "or pass --token", file=sys.stderr)
        return 3

    try:
        from hub.alerts import GitHubIssueNotifier
    except Exception as exc:  # noqa: BLE001 - anything at import time is unusable
        print(f"[hub_alert] hub.alerts is not importable: {exc}", file=sys.stderr)
        return 2

    try:
        GitHubIssueNotifier(
            api_base=args.api_base,
            token=args.token,
            alerts_dir=args.alerts_dir,
        ).raise_alert(args.repo, args.key, args.runner, body)
    except Exception as exc:  # noqa: BLE001 - the notifier raises what it cannot deliver
        print(f"[hub_alert] raise_alert failed: {exc}", file=sys.stderr)
        return 2

    print(f"[hub_alert] raised alert {args.key} on {args.repo}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())