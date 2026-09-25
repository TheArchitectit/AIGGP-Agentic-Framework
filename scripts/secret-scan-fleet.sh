#!/usr/bin/env bash
# secret-scan-fleet.sh — sweep every declared repository, and say what could
# not be swept.
#
#   scripts/secret-scan-fleet.sh --declared FILE [--report FILE] [--work DIR]
#
# The declaration file is one URL per line; blank lines and `#` comments are
# ignored. URLs rather than local paths on purpose: what the hub holds is a
# URL, and a declaration that only works on the host where the sweep runs is a
# declaration that cannot be handed to anyone else.
#
# Exit: 0 every declared repository scanned clean, 1 at least one uncovered
# finding, 2 the scanner is unusable, 3 bad invocation, 4 at least one declared
# repository could not be scanned.
#
# WHY THIS IS SEPARATE FROM THE PUSH GATE
# `secret-scan.sh` answers "did this push add a credential" about one
# repository, at the moment of the push. This answers "is there a credential
# sitting in a repository we own that nobody has pushed to in months" about the
# whole declared fleet. secret-scan-04 keeps the two apart: the push gate never
# widens its scope to the history, and the sweep is never run on the per-push
# path.
#
# WHY THE DECLARATION IS REQUIRED AND MAY NOT BE EMPTY
# "Every repository we own" is a claim this script cannot verify — it can only
# sweep the list it was handed. An empty or absent declaration is therefore not
# a clean fleet, it is a sweep that measured nothing, and it exits 3 rather
# than 0. Same rule as run-tests.mjs refusing to report success after
# discovering zero tests, and as the gate reserving exit 0 for "the scanner ran
# over the named scope and found nothing".
#
# WHY AN UNFETCHABLE REPOSITORY IS REPORTED, NOT SKIPPED (secret-scan-07)
# The failure mode is a shorter list. A repository that cannot be cloned
# disappears from the output, and the fleet reads as entirely clean — the
# same shape as a scanner that did not run. So every declared repository
# appears in the report exactly once, with a state and, when it could not be
# scanned, the reason. The state vocabulary is: clean, findings, unfetchable,
# unscannable. Exit 4 is how the summary carries "at least one unknown"; the
# report carries which one and why.
#
# WHY THIS NEVER PRINTS A VALUE
# The gate already refuses to copy a matched value into its output or its
# report, and this aggregates the gate — a second place a value can be written
# to a file that gets attached to a ticket. Only the state, the counts, and the
# locations (rule, path, line, commit) cross from the gate's report into this
# one. The gate's report is written into the sweep's temporary directory and
# removed on exit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="$SCRIPT_DIR/secret-scan.sh"

DECLARED=""
REPORT=""
WORK=""

die() { echo "[secret-scan-fleet] $*" >&2; exit 3; }

while [ $# -gt 0 ]; do
    case "$1" in
        --declared) [ $# -ge 2 ] || die "--declared needs a file"; DECLARED="$2"; shift ;;
        --report)   [ $# -ge 2 ] || die "--report needs a file"; REPORT="$2"; shift ;;
        --work)     [ $# -ge 2 ] || die "--work needs a directory"; WORK="$2"; shift ;;
        *) die "unrecognised argument: $1" ;;
    esac
    shift
done

[ -n "$DECLARED" ] || die "no --declared file given: a sweep without a
declaration would scan nothing and exit 0, which reads as a clean fleet"
[ -f "$DECLARED" ] || die "--declared is not a file: $DECLARED"
[ -x "$GATE" ] || [ -f "$GATE" ] || die "the gate script is not beside this one: $GATE"

command -v git >/dev/null 2>&1 || die "git is not on PATH: nothing can be fetched"
command -v python3 >/dev/null 2>&1 || die "python3 is not on PATH: the report cannot be built"

# The declaration is read into an array before anything is cloned, so an empty
# declaration fails before the first fetch rather than after a sweep that
# scanned nothing and exited 0.
URLS=()
while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [ -n "$line" ] || continue
    URLS+=("$line")
done < "$DECLARED"

if [ "${#URLS[@]}" -eq 0 ]; then
    die "the declaration names no repository ($DECLARED) — zero repositories
scanned is not a clean fleet"
fi

OWN_WORK=0
if [ -z "$WORK" ]; then
    WORK="$(mktemp -d)"
    OWN_WORK=1
fi
[ -d "$WORK" ] || die "--work is not a directory: $WORK"

TMPD="$(mktemp -d)"
# An `if`, not `[ ... ] && rm`: as a bare AND-list, a false test makes the list
# return non-zero, and `set -e` is still in force inside an EXIT trap — so the
# cleanup for the common case (a caller-supplied --work) would abort the trap.
cleanup() {
    rm -rf "$TMPD"
    if [ "$OWN_WORK" -eq 1 ]; then rm -rf "$WORK"; fi
    return 0
}
trap cleanup EXIT

RECORDS="$TMPD/records.jsonl"
: > "$RECORDS"

name_of() {  # <url> -> the last path segment, minus a .git suffix
    local base="${1%%\?*}"
    base="${base%/}"
    base="${base##*/}"
    printf '%s' "${base%.git}"
}

# Record one repository in the report. Written by python3 rather than by hand
# so a URL containing a quote or a backslash cannot produce a report that will
# not parse.
record() {  # <name> <url> <state> <reason> <scope> <uncovered> <report-file>
    python3 - "$RECORDS" "$1" "$2" "$3" "$4" "$5" "$6" "${7:-}" <<'PY'
import json, os, sys

records, name, url, state, reason, scope, uncovered, gate_report = sys.argv[1:9]

locations = []
findings = 0
if gate_report and os.path.exists(gate_report):
    try:
        doc = json.load(open(gate_report))
    except Exception:
        doc = {}
    # Locations only. The gate's report deliberately carries no Secret and no
    # Match field; this copies the location fields by name so that a future
    # field cannot arrive here by aggregation.
    locations = [{"rule": f.get("rule"), "path": f.get("path"),
                  "line": f.get("line"), "commit": f.get("commit")}
                 for f in doc.get("findings", [])]
    findings = len(locations)

with open(records, "a") as fh:
    fh.write(json.dumps({
        "name": name,
        "url": url,
        "state": state,
        "reason": reason or None,
        "scope": scope or None,
        "scanned_at": os.environ.get("SCAN_NOW") if scope else None,
        "findings": findings,
        "uncovered": int(uncovered or 0),
        "locations": locations,
    }) + "\n")
PY
}

SCAN_NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export SCAN_NOW

HAD_FINDINGS=0
HAD_UNSCANNED=0
ABORTED=0
SCANNED=0
IDX=0

for url in "${URLS[@]}"; do
    IDX=$((IDX + 1))
    name="$(name_of "$url")"
    [ -n "$name" ] || name="repo-$IDX"

    if [ "$ABORTED" -eq 1 ]; then
        # The scanner is unusable, so every remaining repository would fail the
        # same way. They are still recorded, because secret-scan-07 is about the
        # report rather than the loop: a repository dropped here disappears from
        # the fleet view and reads as one nobody declared.
        record "$name" "$url" unscannable \
            "sweep aborted: the scanner is unusable" "" 0 ""
        HAD_UNSCANNED=1
        continue
    fi

    dir="$WORK/$IDX-$name"
    # Which line of a failed command is the reason is not the same for both
    # tools here, and both choices are measured rather than stylistic. git puts
    # its diagnosis FIRST and follows it with advice ("Please make sure you have
    # the correct access rights / and the repository exists"), so the first line
    # is the reason. The gate prints its scope before it configures anything, so
    # its failures are at the END — the last line is the reason, and the first
    # would be a scope statement that reads as a successful scan.
    if ! git clone --quiet --no-single-branch "$url" "$dir" >"$TMPD/clone.log" 2>&1; then
        why="$(head -n 1 "$TMPD/clone.log" 2>/dev/null || true)"
        record "$name" "$url" unfetchable \
            "could not fetch: ${why:-git clone failed}" "" 0 "" >/dev/null
        echo "[secret-scan-fleet] UNFETCHABLE $name: ${why:-git clone failed}"
        HAD_UNSCANNED=1
        continue
    fi

    gate_report="$TMPD/$IDX-report.json"
    rm -f "$gate_report"
    rc=0
    bash "$GATE" --all --repo "$dir" --report "$gate_report" \
        >"$TMPD/$IDX-gate.log" 2>&1 || rc=$?

    case "$rc" in
        0|1) ;;
        2)  # A scanner that did not run is not a repository with nothing in it.
            # Nothing about this sweep is trustworthy, including the clean
            # verdicts already collected, so the exit code says so even though
            # those records stay in the report as what was observed.
            why="$(tail -n 1 "$TMPD/$IDX-gate.log" 2>/dev/null || true)"
            record "$name" "$url" unscannable \
                "scanner unusable: ${why:-gitleaks could not run}" "" 0 ""
            echo "[secret-scan-fleet] SCANNER UNUSABLE at $name: ${why:-gitleaks could not run}" >&2
            HAD_UNSCANNED=1
            ABORTED=1
            continue ;;
        *)  # Bad gate configuration in the fetched repository: the gate refused
            # before scanning, so there is no verdict for it — and "no verdict"
            # is not "clean".
            why="$(tail -n 1 "$TMPD/$IDX-gate.log" 2>/dev/null || true)"
            record "$name" "$url" unscannable \
                "the gate refused this repository: ${why:-exit $rc}" "" 0 ""
            echo "[secret-scan-fleet] UNSCANNABLE $name: ${why:-exit $rc}"
            HAD_UNSCANNED=1
            continue ;;
    esac

    if [ "$rc" -eq 1 ]; then
        state=findings
        HAD_FINDINGS=1
    else
        state=clean
    fi
    SCANNED=$((SCANNED + 1))
    uncovered="$(python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("uncovered", 0))
except Exception: print(0)' "$gate_report")"
    record "$name" "$url" "$state" "" all "$uncovered" "$gate_report"
    echo "[secret-scan-fleet] ${state^^} $name ($uncovered uncovered)"
done

DECLARED_N="${#URLS[@]}"
if [ -n "$REPORT" ]; then
    python3 - "$RECORDS" "$REPORT" "$DECLARED_N" "$SCANNED" <<'PY'
import json, sys

records_path, report_path, declared, scanned = sys.argv[1:5]
repos = [json.loads(l) for l in open(records_path) if l.strip()]
states = {"clean": 0, "findings": 0, "unfetchable": 0, "unscannable": 0}
for r in repos:
    states[r["state"]] = states.get(r["state"], 0) + 1
with open(report_path, "w") as fh:
    json.dump({
        "declared": int(declared),
        "scanned": int(scanned),
        "states": states,
        "repos": repos,
    }, fh, indent=2, sort_keys=True)
PY
fi

echo "[secret-scan-fleet] declared $DECLARED_N, scanned $SCANNED, states: $(python3 -c 'import json,sys
repos=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
seen={}
for r in repos: seen[r["state"]]=seen.get(r["state"],0)+1
print(", ".join(f"{k}={v}" for k,v in sorted(seen.items())))' "$RECORDS")"

# Precedence: a scanner fault means no verdict is trustworthy, a real leak
# outranks an unknown, and an unknown outranks clean. Every branch is non-zero
# except the last, which is only reached when every declared repository was
# scanned and none had anything to fix.
if [ "$ABORTED" -eq 1 ]; then
    echo "[secret-scan-fleet] FAIL: the scanner is unusable — no verdict from this sweep is trustworthy" >&2
    exit 2
fi
if [ "$HAD_FINDINGS" -eq 1 ]; then
    echo "[secret-scan-fleet] FAIL: at least one repository has an uncovered finding" >&2
    exit 1
fi
if [ "$HAD_UNSCANNED" -eq 1 ]; then
    echo "[secret-scan-fleet] UNKNOWN: at least one declared repository could not be scanned — see the report" >&2
    exit 4
fi
echo "[secret-scan-fleet] OK: every declared repository scanned clean"
