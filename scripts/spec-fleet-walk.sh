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
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

declared_path, report_path, work_dir, tier_file, lock_file, classifier = sys.argv[1:7]
work = Path(work_dir)
work.mkdir(parents=True, exist_ok=True)

# --- authenticated clones (opt-in: SPEC_FLEET_CLONE_TOKEN) -----------------
# spec-fleet.yml sets this only in `app` token mode, for the curated private
# repositories the App installation can read. CRITICAL: the report this walk
# writes is committed to docs/qa/spec-sweeps/ in a PUBLIC repository, so the
# token may never reach git's argv, the report's `reason` strings, or a log.
# The GIT_ASKPASS helper below reads the secret from its own environment at
# prompt time (the file carries no credential), and everything captured from
# a failed clone is redacted before it is stored. When the variable is unset
# the clone path is exactly as before: no helper, no env override.
clone_token = os.environ.get("SPEC_FLEET_CLONE_TOKEN", "")
_SECRET_SHAPES = re.compile(
    r"(gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})")
_URL_USERINFO = re.compile(r"(?<=://)[^/@\s]+@")


def redact(text):
    """Remove the clone token, credential-shaped literals, and URL userinfo
    from text bound for the report or the log. Defense in depth: the token is
    not on git's argv, but a failed clone's stderr is still captured."""
    if not text:
        return text
    text = _URL_USERINFO.sub("***@", text)
    if clone_token:
        text = text.replace(clone_token, "***")
    return _SECRET_SHAPES.sub("***", text)


def failure_reason(exc, stderr):
    """The historical reason text is str(exc); an authenticated clone adds the
    redacted stderr, which is the diagnosable part (the unauth path never had
    it and stays byte-identical)."""
    base = (stderr or "").strip() if clone_token else ""
    return redact((base or str(exc)))[:100]


askpass = None
git_env = None
if clone_token:
    askpass = work / ".git-askpass.sh"
    fd = os.open(askpass, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o700)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/bin/sh\n"
            "# GIT_ASKPASS for spec-fleet-walk.sh. It reads the secret from\n"
            "# its environment at prompt time; this file carries no credential.\n"
            'case "$1" in\n'
            '  Username*) printf "%s\\n" "x-access-token" ;;\n'
            '  *) printf "%s\\n" "${SPEC_FLEET_ASKPASS_TOKEN:-}" ;;\n'
            "esac\n"
        )
    askpass.chmod(0o700)
    git_env = dict(os.environ)
    git_env.update({
        "GIT_ASKPASS": str(askpass),
        "GIT_TERMINAL_PROMPT": "0",
        "SPEC_FLEET_ASKPASS_TOKEN": clone_token,
        # The username is a literal, not a secret, and an empty helper keeps
        # a runner's configured credential store from caching the App token.
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.username",
        "GIT_CONFIG_VALUE_0": "x-access-token",
        "GIT_CONFIG_KEY_1": "credential.helper",
        "GIT_CONFIG_VALUE_1": "",
    })
    # Only the clone gets the credential. The classifier and the openspec
    # binary it may spawn have no use for it, so drop it from the inherited
    # environment (git already has its own copy in git_env).
    os.environ.pop("SPEC_FLEET_CLONE_TOKEN", None)
    print("[walk] authenticated clone mode: askpass helper in place")

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
                              capture_output=True, text=True, check=True, timeout=120,
                              env=git_env)
            except Exception as exc:  # noqa: BLE001
                stderr = getattr(exc, "stderr", "") or ""
                repos.append({"name": name, "state": "unscannable",
                              "reason": failure_reason(exc, stderr), "url": url})
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
                      "reason": redact(f"classifier failed: {exc}")[:100],
                      "url": url})
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
