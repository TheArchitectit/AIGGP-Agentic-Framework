#!/usr/bin/env bash
# secret-scan-declared.sh — generate the fleet declaration, deterministically.
#
#   scripts/secret-scan-declared.sh --out FILE [--snapshot FILE]
#
# Reads live `gh repo list` unless --snapshot gives a canned JSON file (the
# unit-test path, and how to dry-run declaration changes without credentials).
# Applies fleet-sweep-include.txt and fleet-sweep-exclude.txt from the repo
# root. Output is the declaration secret-scan-fleet.sh consumes: one URL per
# line, sorted and deduped.
#
# WHY THIS EXISTS AS A SCRIPT
# The first production sweep's residual #1 was "a new public repository
# created tomorrow is not in this declaration until someone updates the
# file." A hand-maintained list cannot avoid going stale. Generating it per
# run makes the stale-list failure impossible by construction: the
# declaration is a derived artifact, and the only checked-in inputs are the
# reviewable include/exclude exceptions.
#
# WHY EMPTY EXITS 3
# secret-scan-fleet.sh exits 3 on an empty declaration because a vacuous
# sweep that reports clean is the worst reading of it. The generator reuses
# that code for the same reason: a generator that produced nothing (bad
# credentials, wrong owner, a broken merge) must not write an empty file
# that the sweep then refuses loudly — the generator refuses loudly first,
# naming itself. An empty generated list is a broken generator, never a
# clean fleet.
#
# WHY A SNAPSHOT FLAG
# `gh repo list` needs credentials and calls the network. The unit tests
# (T-09, T-10) and every local dry-run of a declaration change must work
# without either. --snapshot is the same JSON `gh` emits, so the code path
# under test is the code path on CI; there is no second parser.
#
# WHY LINES THAT LEAD WITH '-' ARE REFUSED
# secret-scan-fleet.sh refuses a declaration URL that starts with '-', so a
# crafted include line cannot smuggle an option into the sweep's argv. The
# generator refuses the same shape before it writes anything, because the
# generator is the thing that would write it.
#
# Exit: 0 declaration written and non-empty, 2 gh is missing when a live
# listing was asked for, 3 bad invocation or an empty result.
set -euo pipefail

OUT=""
SNAPSHOT=""

die() { echo "[secret-scan-declared] $*" >&2; exit 3; }

while [ $# -gt 0 ]; do
    case "$1" in
        --out)      [ $# -ge 2 ] || die "--out needs a file"; OUT="$2"; shift ;;
        --snapshot) [ $# -ge 2 ] || die "--snapshot needs a file"; SNAPSHOT="$2"; shift ;;
        *) die "unrecognised argument: $1" ;;
    esac
    shift
done

[ -n "$OUT" ] || die "--out is required"
if [ -n "$SNAPSHOT" ]; then
    # -r rather than -f: a snapshot may be a file, a /dev/stdin pipe, or
    # process substitution. What matters is that the generator can read it —
    # an absent snapshot must be refused, not silently treated as empty.
    [ -r "$SNAPSHOT" ] || die "--snapshot is not readable: $SNAPSHOT"
fi

# Bash-only path resolution: the emptiest PATH we are responsible for
# diagnosing (exit 2, gh not installed) must not also blind `dirname`.
SELF_SRC="${BASH_SOURCE[0]}"
case "$SELF_SRC" in
    */*) HERE="$(cd "${SELF_SRC%/*}" && pwd)" ;;
    *)   HERE="$(cd . && pwd)" ;;
esac
ROOT="$(cd "$HERE/.." && pwd)"
INCLUDE="$ROOT/fleet-sweep-include.txt"
EXCLUDE="$ROOT/fleet-sweep-exclude.txt"

LIST_JSON=""
if [ -n "$SNAPSHOT" ]; then
    LIST_JSON="$(cat "$SNAPSHOT")"
else
    if ! command -v gh >/dev/null 2>&1; then
        echo "[secret-scan-declared] gh is not on PATH and no --snapshot was given" >&2
        exit 2
    fi
    LIST_JSON="$(gh repo list TheArchitectit --limit 1000 \
        --json nameWithOwner,isPrivate,isArchived,url)" \
        || { echo "[secret-scan-declared] gh repo list failed" >&2; exit 2; }
fi

# The merge is one python3 pass. The generated list travels as an argv-pointed
# temp file rather than stdin so the whole merge can be a single heredoc and
# the empty-result check sits in the same interpreter that produced the empty
# result. Reports and paths only; nothing here carries a secret.
LIST_TMP="$(mktemp)"
trap 'rm -f "$LIST_TMP"' EXIT
printf '%s' "$LIST_JSON" > "$LIST_TMP"

python3 - "$OUT" "$INCLUDE" "$EXCLUDE" "$LIST_TMP" <<'PY'
import os
import sys
import tempfile
from urllib.parse import urlparse

out_path, include_path, exclude_path, list_path = sys.argv[1:5]


def norm_url(u):
    u = (u or "").strip()
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/")


def owner_name(u):
    """owner/name for a GitHub URL, or a bare owner/name, or the bare name."""
    if "://" not in u:
        u = "https://github.com/" + u
    parts = [p for p in urlparse(u).path.strip("/").split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1] if parts else u


def name_only(u):
    return owner_name(u).split("/")[-1]


def parse_file(path, label):
    """Return (tokens, warnings). Tokens are the pre-comment code; the rest of
    the line is the comment. A reason-less exclusion is a warning, never a
    silent drop of the human record of why the line is there."""
    if not os.path.isfile(path):
        return [], [f"{label} file not found (treated as empty): {path}"]
    tokens, warnings = [], []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            code, _, comment = line.partition("#")
            code = code.strip()
            comment = comment.strip()
            if not code:
                continue  # whole-line comment
            if code.startswith("-"):
                print(
                    f"[secret-scan-declared] {label} line {lineno} starts with "
                    f"'-' and is refused (option-injection guard): prefix the "
                    f"line with '#' if it is commentary",
                    file=sys.stderr,
                )
                sys.exit(3)
            if label == "exclude" and not comment:
                warnings.append(
                    f"{label} line {lineno} ({code}) has no reason comment — "
                    f"exclusions without a reason are what turns this file "
                    f"into a quiet hole"
                )
            tokens.append(code)
    return tokens, warnings


def excluded(url, exclude_tokens):
    """An exclusion may be a full URL, an owner/name, or a bare repository
    name. The last form is what the task file uses (`llama.cpp`); it matches
    the repository name alone and is case-insensitive."""
    u_key = norm_url(url).lower()
    o_key = owner_name(url).lower()
    n_key = name_only(url).lower()
    for tok in exclude_tokens:
        t = norm_url(tok).lower()
        if t == u_key:
            return True
        if "/" in t:
            if t == o_key:
                return True
        elif t == n_key:
            return True
    return False


include_tokens, include_warn = parse_file(include_path, "include")
exclude_tokens, exclude_warn = parse_file(exclude_path, "exclude")

for w in include_warn + exclude_warn:
    print(f"[secret-scan-declared] {w}", file=sys.stderr)

try:
    import json
    repos = json.load(open(list_path, encoding="utf-8"))
except Exception as exc:  # noqa: BLE001 - a broken snapshot is a broken generator
    print(f"[secret-scan-declared] could not read the repo listing: {exc}",
          file=sys.stderr)
    sys.exit(3)
if not isinstance(repos, list):
    print("[secret-scan-declared] repo listing is not a JSON array", file=sys.stderr)
    sys.exit(3)

# Archived repos are not swept: nobody can push to them, and their state is
# whatever their last sweep recorded. Everything else from the owner scope is
# in scope. Include-file URLs are kept regardless — their archived status is
# not in this listing and their presence in the include file is itself the
# deliberate act.
#
# GitHub paths are case-insensitive, so two spellings of the same URL are one
# repository. First spelling wins; the residual order is keyed on the lower
# form and then the exact spelling, so a snapshot cannot produce two different
# byte sequences across runs.
cand = {}
for r in repos:
    if not isinstance(r, dict):
        continue
    if r.get("isArchived"):
        continue
    u = norm_url(r.get("url", ""))
    if u:
        cand.setdefault(u.lower(), u)

for tok in include_tokens:
    u = norm_url(tok)
    if u:
        cand.setdefault(u.lower(), u)

kept = [
    cand[k]
    for k in sorted(cand.keys())
    if not excluded(cand[k], exclude_tokens)
]

if not kept:
    print("[secret-scan-declared] empty declaration — generator or "
          "credentials broke (or every candidate is excluded); writing "
          "nothing", file=sys.stderr)
    sys.exit(3)

# Atomic replace: the runner-heartbeat .sh reads declarations and reports the
# way the sweep's own report writer does, and a reader that observes a partial
# file is a reader that concludes the fleet is half its size.
out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
os.makedirs(out_dir, exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".declared-", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for u in kept:
            fh.write(u + "\n")
    os.replace(tmp, out_path)
except BaseException:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise

print(f"[secret-scan-declared] wrote {len(kept)} declaration entr"
      f"{'y' if len(kept) == 1 else 'ies'} to {out_path}",
      file=sys.stderr)
PY