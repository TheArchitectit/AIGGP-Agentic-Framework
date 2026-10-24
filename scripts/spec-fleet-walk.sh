#!/usr/bin/env bash
# spec-fleet.yml's per-repo step, runnable locally for proof runs.
# Walks a declaration file (one URL/path per line), clones each into a
# work dir, classifies, and emits a capped report JSON.
#
# Usage: spec-fleet-walk.sh --declared FILE --report FILE --work DIR
#        [--tier-file FILE] [--lock-file FILE]
set -euo pipefail

DECLARED=""
REPORT=""
WORK=""
TIER_FILE=""
LOCK_FILE=""
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [ $# -gt 0 ]; do
    case "$1" in
        --declared) DECLARED="$2"; shift 2 ;;
        --report)   REPORT="$2"; shift 2 ;;
        --work)     WORK="$2"; shift 2 ;;
        --tier-file) TIER_FILE="$2"; shift 2 ;;
        --lock-file) LOCK_FILE="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 3 ;;
    esac
done
[ -n "$DECLARED" ] && [ -n "$REPORT" ] && [ -n "$WORK" ] || { echo "missing args" >&2; exit 3; }

mkdir -p "$WORK"
CLASSIFIER="$HERE/spec-fleet-classify.py"

python3 - "$DECLARED" "$REPORT" "$WORK" "$TIER_FILE" "$LOCK_FILE" "$CLASSIFIER" <<'PY'
import json, os, subprocess, sys, tempfile
from pathlib import Path

declared_path, report_path, work_dir, tier_file, lock_file, classifier = sys.argv[1:7]
work = Path(work_dir)
work.mkdir(parents=True, exist_ok=True)

declared = [l.strip() for l in Path(declared_path).read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]

if not declared:
    # Exit 3 family: an empty declaration is a broken walk, not a clean
    # fleet. A vacuous sweep that reports "0 declared, 0 states" would read
    # green on the trend line — the exact reading the secret-scan family
    # refuses for the same reason.
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps({
        "declared": 0, "scanned": 0, "states": {},
        "error": "empty declaration — the walk measured nothing; this is a "
                 "broken generator, not a clean fleet",
    }, indent=2, sort_keys=True), encoding="utf-8")
    print("empty declaration — refusing to write a vacuous report", file=sys.stderr)
    sys.exit(3)

repos = []
states = {}
for idx, url in enumerate(declared):
    name = url.rstrip("/").split("/")[-1]
    # support local paths (for proof runs) as well as URLs
    if url.startswith("http"):
        clone_dir = work / f"{idx:03d}-{name}"
        # owner/repo form for tier matching: https://github.com/owner/repo
        repo_name = "/".join(url.rstrip("/").split("/")[-2:])
        if not clone_dir.exists():
            try:
                subprocess.run(["git", "clone", "--depth", "1", url, str(clone_dir)],
                              capture_output=True, text=True, check=True, timeout=120)
            except Exception as exc:  # noqa: BLE001
                repos.append({"name": name, "state": "unscannable",
                              "reason": str(exc)[:100], "url": url})
                states["unscannable"] = states.get("unscannable", 0) + 1
                continue
        root = clone_dir
    else:
        root = Path(url)
        repo_name = name

    cmd = [sys.executable, classifier, "--root", str(root), "--json"]
    if tier_file:
        cmd += ["--tier-file", tier_file]
    if lock_file:
        cmd += ["--lock-file", lock_file]
    cmd += ["--repo-name", repo_name]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        data = json.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        repos.append({"name": name, "state": "unscannable",
                      "reason": f"classifier failed: {exc}"[:100], "url": url})
        states["unscannable"] = states.get("unscannable", 0) + 1
        continue
    cls = data.get("classification", {})
    state = cls.get("state", "unscannable")
    repos.append({
        "name": name,
        "state": state,
        "reason": cls.get("reason", ""),
        "gaps": cls.get("gaps", 0),
        "tiered": cls.get("tiered", False),
        "red": cls.get("red", False),
        "strict_state": cls.get("strict_state"),
        "strict_reason": cls.get("strict_reason", ""),
        "has_openspec": cls.get("has_openspec"),
        # Provenance travels with the row: the workflow's fault step reads it
        # from here, and dropping it made every sweep say "provenance: clean".
        "provenance": cls.get("provenance"),
        "provenance_red": cls.get("provenance_red", False),
        "provenance_findings": cls.get("provenance_findings", False),
        "url": url,
    })
    states[state] = states.get(state, 0) + 1

# Capped summary lists, mirroring the secret sweep's report so one reader
# pattern works for both (design: unspaced[] / invalid[] / gaps_top[], each
# capped at 40 with an omitted count — the cap that fixed the 422).
CAP = 40
def _cap(items, key):
    items = sorted(items, key=key)
    kept = items[:CAP]
    return kept, max(0, len(items) - len(kept))

unspaced, unspaced_omitted = _cap(
    [r for r in repos if r.get("state") == "unspaced"], key=lambda r: r["name"])
invalid, invalid_omitted = _cap(
    [r for r in repos if r.get("state") == "invalid"],
    key=lambda r: (not r.get("tiered"), r["name"]))
gaps_top, gaps_top_omitted = _cap(
    [r for r in repos if r.get("state") == "gaps"],
    key=lambda r: (-(r.get("gaps") or 0), r["name"]))

# Lock-level provenance once per sweep (pin integrity + upstream drift).
lock_prov = {"templates": {}, "drift": [], "unlocked": [], "fault": False,
             "unknown": [], "reason": "no lock file"}
if lock_file:
    try:
        lp = subprocess.run([sys.executable, classifier, "--lock-check-only",
                             "--lock-file", lock_file],
                            capture_output=True, text=True, timeout=300)
        lock_prov = json.loads(lp.stdout)
    except Exception as exc:  # noqa: BLE001
        lock_prov = {"templates": {}, "drift": [], "unlocked": [], "fault": True,
                     "unknown": [], "reason": f"lock check failed: {exc}"[:100]}

report = {
    "lock_provenance": lock_prov,
    "declared": len(declared),
    "scanned": len(repos),
    "states": states,
    "repos": repos,
    "unspaced": unspaced,
    "unspaced_omitted": unspaced_omitted,
    "invalid": invalid,
    "invalid_omitted": invalid_omitted,
    "gaps_top": gaps_top,
    "gaps_top_omitted": gaps_top_omitted,
}
Path(report_path).parent.mkdir(parents=True, exist_ok=True)
Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True),
                            encoding="utf-8")
print(json.dumps({"declared": len(declared), "states": states}, indent=1))
PY
