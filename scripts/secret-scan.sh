#!/usr/bin/env bash
# secret-scan.sh — the push-path secret gate.
#
#   scripts/secret-scan.sh --tree                 # working tree only
#   scripts/secret-scan.sh --range BEFORE..AFTER  # pushed commits + working tree
#   scripts/secret-scan.sh --all                  # every ref + working tree
#
#   [--repo DIR] [--report FILE]
#
# Exit: 0 clean (scanner ran over the named scope), 1 finding, 2 scanner
# unusable, 3 bad invocation or bad gate configuration.
#
# WHY THIS IS A SCRIPT AND NOT WORKFLOW STEPS
# A scanner that is absent, uninstalled, or invoked wrongly produces no
# findings, and no findings reads as clean. So 0 is reserved for "the scanner
# ran over the scope named in the output and found nothing"; everything else
# that could be mistaken for clean is non-zero. Same rule as run-tests.mjs
# refusing to report success after discovering zero tests.
#
# WHY THE SCOPE IS REQUIRED
# "Did this push add a credential" and "is there a credential anywhere in this
# repository" are different questions with different owners. The push gate
# takes a range and never widens it silently; the sweep is asked for by name.
# The one seam is a first push or a forced update, where the range's base
# commit does not exist — that falls back to the full history and says so,
# because scanning nothing and exiting 0 is the worst reading of it.
#
# WHY NOTHING HERE PRINTS A VALUE
# A scanner that echoes the matched secret into CI logs and uploaded artifacts
# has published it a second time, to a wider audience than the commit did. The
# scanner is always invoked with --redact, and this script never copies the
# report's Secret or Match fields into its own output or its own report — it
# prints rule, path, line, and commit, which is everything needed to find the
# value locally. The scanner's raw report is written into a temporary directory
# that is removed on exit, so no unredacted artifact survives the run.
#
# Dispositions live in .guardrails/secret-allowlist.json: an entry names a rule
# AND a path and carries a reason. A rule alone is not a disposition — one
# entry for one false positive must not immunise a ruleset — and docs are not
# excluded from the scan, because docs are where people paste real credentials.
set -euo pipefail

REPO=""
REPORT=""
SCOPE=""
RANGE=""

die() { echo "[secret-scan] $*" >&2; exit 3; }

while [ $# -gt 0 ]; do
    case "$1" in
        --tree)  [ -z "$SCOPE" ] || die "only one scope may be given"; SCOPE=tree ;;
        --all)   [ -z "$SCOPE" ] || die "only one scope may be given"; SCOPE=all ;;
        --range) [ -z "$SCOPE" ] || die "only one scope may be given"
                 [ $# -ge 2 ] || die "--range needs BASE..HEAD"
                 SCOPE=range; RANGE="$2"; shift ;;
        --repo)  [ $# -ge 2 ] || die "--repo needs a directory"; REPO="$2"; shift ;;
        --report) [ $# -ge 2 ] || die "--report needs a file"; REPORT="$2"; shift ;;
        *) die "unrecognised argument: $1" ;;
    esac
    shift
done

[ -n "$SCOPE" ] || die "no scope given: pass --tree, --range BASE..HEAD, or --all"

# Which scope is a decision, not a default, so it is validated before anything
# expensive or anything that could be mistaken for a result happens.
case "$SCOPE" in
    range)
        case "$RANGE" in *..*) ;; *) die "--range needs BASE..HEAD, got: $RANGE" ;; esac
        BASE="${RANGE%%..*}"
        ;;
esac

if [ -z "$REPO" ]; then
    REPO="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    [ -n "$REPO" ] || die "--repo not given and the working directory is not in a git repository"
fi
[ -d "$REPO" ] || die "--repo is not a directory: $REPO"

MISSING=""
command -v gitleaks >/dev/null 2>&1 || MISSING="gitleaks"
command -v python3  >/dev/null 2>&1 || MISSING="${MISSING:+$MISSING, }python3"
if [ -n "$MISSING" ]; then
    echo "[secret-scan] scanner unusable: not on PATH: $MISSING — install the pinned release; do not skip the scan" >&2
    exit 2
fi

ALLOWLIST="$REPO/.guardrails/secret-allowlist.json"

# The allowlist is validated before the scan runs: a gate configured wrongly
# must not spend a scan and then report a finding as if the scan had settled
# anything.
python3 - "$ALLOWLIST" <<'PY'
import json, os, sys

path = sys.argv[1]
if not os.path.exists(path):
    sys.exit(0)
try:
    doc = json.load(open(path))
except Exception as exc:
    print(f"[secret-scan] allowlist is not valid JSON: {path}: {exc}", file=sys.stderr)
    sys.exit(3)

entries = doc.get("entries") if isinstance(doc, dict) else None
if not isinstance(entries, list):
    print(f"[secret-scan] allowlist must be an object with an 'entries' list: {path}", file=sys.stderr)
    sys.exit(3)

for i, e in enumerate(entries):
    if not isinstance(e, dict):
        print(f"[secret-scan] allowlist entry {i} is not an object", file=sys.stderr)
        sys.exit(3)
    for field in ("rule", "path", "reason"):
        v = e.get(field)
        if not isinstance(v, str) or not v.strip():
            print(f"[secret-scan] allowlist entry {i} is missing {field!r} — "
                  f"a tolerated finding needs a rule, a path, and a reason", file=sys.stderr)
            sys.exit(3)
PY

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT

# Base-commit fall-back. The range's base may be absent on a first push or a
# forced update; the push payload still carries a `before` of all zeroes there.
HISTORY_MODE="$SCOPE"
if [ "$SCOPE" = range ]; then
    if git -C "$REPO" rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null 2>&1; then
        echo "[secret-scan] scope: commits in $RANGE, plus the working tree"
    else
        echo "[secret-scan] no usable base commit for range '$RANGE' (first push or forced update) — falling back to the full history sweep (--all), plus the working tree"
        HISTORY_MODE=all
    fi
elif [ "$SCOPE" = all ]; then
    echo "[secret-scan] scope: full history (all refs), plus the working tree"
else
    echo "[secret-scan] scope: working tree only"
fi

scan() {  # scan <report-file> <extra args...>
    local out="$1"; shift
    local rc=0
    gitleaks detect --source "$REPO" --redact --report-format json --report-path "$out" "$@" >/dev/null 2>&1 || rc=$?
    printf '%s' "$rc"
}

TREE_RC="$(scan "$TMPD/tree.json" --no-git)"
HIST_RC=0
HIST_JSON=""
if [ "$HISTORY_MODE" != tree ]; then
    if [ "$HISTORY_MODE" = all ]; then
        HIST_JSON="$TMPD/history.json"
        HIST_RC="$(scan "$HIST_JSON" --log-opts=--all)"
    else
        HIST_JSON="$TMPD/history.json"
        HIST_RC="$(scan "$HIST_JSON" --log-opts="$RANGE")"
    fi
fi

# A scanner that crashed is not a repository with nothing in it.
for rc in "$TREE_RC" "$HIST_RC"; do
    case "$rc" in
        0|1) ;;
        *) echo "[secret-scan] scanner unusable: gitleaks exited $rc — not reporting this run as clean" >&2; exit 2 ;;
    esac
done
# A run that reported findings but wrote no readable report fails closed too:
# the findings are real, and the gate cannot say where they are.
for pair in "$TREE_RC:$TMPD/tree.json" "$HIST_RC:$HIST_JSON"; do
    rc="${pair%%:*}"
    [ "$rc" = 1 ] || continue
    f="${pair#*:}"
    [ -s "$f" ] || { echo "[secret-scan] scanner unusable: gitleaks reported findings but wrote no report" >&2; exit 2; }
done

python3 - "$ALLOWLIST" "$REPORT" "$TREE_RC:$TMPD/tree.json" "$HIST_RC:$HIST_JSON" "$SCOPE" "$HISTORY_MODE" <<'PY'
import json, os, sys

allow_path, report_path, *rest = sys.argv[1:]
scope, history_mode = rest[-2], rest[-1]
scans = rest[:-2]

entries = []
if os.path.exists(allow_path):
    entries = json.load(open(allow_path)).get("entries", [])

findings = []
for spec in scans:
    rc, path = spec.split(":", 1)
    if not path or not os.path.exists(path):
        continue
    try:
        loaded = json.load(open(path))
    except Exception:
        loaded = []
    for f in loaded or []:
        # Deliberately not carried through: Secret, Match, Author, Email. A
        # finding is a location, not a value.
        findings.append({
            "rule": f.get("RuleID") or f.get("Rule") or "unknown",
            "path": f.get("File") or "unknown",
            "line": f.get("StartLine") or 0,
            "commit": (f.get("Commit") or "")[:12] or "working tree",
        })

def covered(f):
    return any(e["rule"] == f["rule"] and e["path"] == f["path"] for e in entries)

uncovered = [f for f in findings if not covered(f)]
covered_findings = [f for f in findings if covered(f)]
matched = {i for i, e in enumerate(entries)
           if any(e["rule"] == f["rule"] and e["path"] == f["path"] for f in findings)}

for f in findings:
    verdict = "allowlisted" if covered(f) else "FINDING"
    print(f"[secret-scan] {verdict}: {f['rule']} {f['path']}:{f['line']} ({f['commit']})")

for i, e in enumerate(entries):
    if i in matched:
        continue
    # Only a full-history sweep can claim an entry is stale outright; in a
    # narrower scope the subject may simply be outside it. The reason is quoted
    # only when the claim is definite, so this line stays a signal instead of
    # four lines of noise on every push that readers learn to skip.
    if history_mode == "all":
        print(f"[secret-scan] allowlist stale: no finding matches "
              f"{e['rule']} {e['path']} anywhere in the history — remove the entry "
              f"or re-check it. Reason on file: {e['reason']}")
    else:
        print(f"[secret-scan] allowlist: {e['rule']} {e['path']} not matched in this "
              f"scope (may be stale — run with --all to settle it)")

print(f"[secret-scan] scanned {len(findings)} finding(s): "
      f"{len(covered_findings)} allowlisted, {len(uncovered)} to fix")
print(f"[secret-scan] allowlist: {len(entries)} entry/entries, {len(matched)} matched")

if report_path:
    with open(report_path, "w") as fh:
        json.dump({
            "scope": scope,
            "history_mode": history_mode,
            "allowlist_entries": len(entries),
            "allowlist_matched": len(matched),
            "findings": findings,          # locations only; no Secret, no Match
            "uncovered": len(uncovered),
        }, fh, indent=2, sort_keys=True)

if uncovered:
    print(f"[secret-scan] FAIL: {len(uncovered)} finding(s) not covered by a disposition", file=sys.stderr)
    sys.exit(1)

print("[secret-scan] OK: nothing to fix in the scanned scope")
PY
