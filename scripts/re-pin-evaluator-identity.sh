#!/usr/bin/env bash
# re-pin-evaluator-identity.sh — move the pinned evaluator identity, atomically.
#
# WHY THIS IS A SCRIPT AND NOT A CHECKLIST (design D7, img-cycle-04)
# Four literals move together or the repository is broken in a way that is
# invisible until a consumer's gate runs:
#
#   container/execution-profiles.json   image + image_manifest_digest
#   templates/github-workflows/spec-coherence.yml
#                                       COHERENCE_IMAGE
#                                       COHERENCE_IMAGE_MANIFEST_DIGEST
#                                       DEVGATE_PIN
#
# Two wrong states have already shipped here, both by hand:
#
#   * A digest taken from `podman image inspect`. That value lives on the
#     LOCAL storage axis — true for a locally built image and equally true for
#     one that was just pulled — so it is not a digest any registry serves.
#     The S4 identity was recorded that way and was unpullable for a day
#     ("manifest unknown" for every consumer, anonymously). This operation
#     asks the REGISTRY: anonymous token, GET /v2/<path>/manifests/<ref>, read
#     `Docker-Content-Digest`. It never reads a local digest.
#
#   * A `DEVGATE_PIN` that predates the record. The gate checks DEVGATE_PIN out
#     into `.devgate` and reads the registry out of THAT tree, so a pin whose
#     tree does not carry the moved record does not fail loudly — it lands
#     every consumer's coherence gate at SKIPPED (coh-id-04). The pin is
#     therefore written as the FIRST of two commits, and the operation refuses
#     to finish unless that agreement holds.
#
# THE ORDER IS FORCED, NOT A CONVENTION
# Commit 1 moves the record. Commit 2 moves the template, whose DEVGATE_PIN is
# commit 1's sha — a tree that carries the record by construction. Doing it in
# the other order cannot produce a correct pin at all: at the time the template
# is written, the commit carrying the new record does not exist yet.
#
# WHAT THE GUARD ACTUALLY PROVES
# Four pairs, not two. Every test is on the pinned tree versus the template,
# AND the working-tree record versus the template — the record file the
# framework's own identity gate reads. And the pin must be REACHABLE, not
# merely present: a commit that exists locally but is not an ancestor of HEAD
# cannot be fetched by any consumer, which is the silent non-green this whole
# exercise is against. That is why the operation refuses a detached HEAD up
# front rather than discovering it afterwards.
#
# WHAT IT DOES NOT DO
# It does not build or publish the image. It re-pins to bytes the registry
# already serves, and it verifies those bytes are fetchable anonymously before
# recording them — because a consumer's runner has no credentials either.
#
# Required env:
#   none. REPIN_REPO_DIR defaults to this script's checkout.
# Optional:
#   REPIN_REPO_DIR    repository to operate on (tests point this at a fixture)
#   REPIN_REF         published ref to resolve (default: main)
#   REPIN_IMAGE       image path; default: whatever the record already names
#   REPIN_BUILT       value for `built`; default: today's date
#   REPIN_CHECK_ONLY  1 = run the pinned-tree agreement guard and nothing else
#
# There is deliberately no way to move a profile OTHER than the one the
# template names. COHERENCE_PROFILE decides which profile the gate reads, so
# moving a different profile's digest writes bytes the template does not
# reference and leaves the pinned identity untouched.
#
# Exit codes:
#   0   done — the four literals agree, and the pin's tree carries the record
#   1   configuration error (bad repo dir, missing file, malformed template)
#   2   the identity could not be resolved from the registry — nothing written
#   3   the served bytes are not fetchable anonymously — nothing was written
#   4   the pinned-tree agreement guard failed (partial, predating, unreachable)
#   5   the working tree has uncommitted changes, or HEAD is detached
#   6   a commit failed; the working tree was restored to where it started

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPIN_REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REF="${REPIN_REF:-main}"
CHECK_ONLY="${REPIN_CHECK_ONLY:-0}"

RECORD_REL="container/execution-profiles.json"
TEMPLATE_REL="templates/github-workflows/spec-coherence.yml"

die() { local code="$1"; shift; echo "re-pin: $*" >&2; exit "$code"; }

[ -d "$REPO_DIR/.git" ] || die 1 "$REPO_DIR is not a git checkout"
RECORD="$REPO_DIR/$RECORD_REL"
TEMPLATE="$REPO_DIR/$TEMPLATE_REL"
[ -f "$RECORD" ] || die 1 "$RECORD_REL is missing from $REPO_DIR"
[ -f "$TEMPLATE" ] || die 1 "$TEMPLATE_REL is missing from $REPO_DIR"

# One extractor, quote- and comment-tolerant, used by every reader below. A
# `COHERENCE_IMAGE: "path"` is the same value as `COHERENCE_IMAGE: path`;
# comparing the raw token would refuse a correct tree and print two
# indistinguishable strings while doing it.
read_env() {  # read_env <template> <key> -> value on stdout
    python3 - "$1" "$2" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
m = re.search(rf"^[ \t]*{re.escape(sys.argv[2])}:[ \t]*(\S+)[ \t]*(?:#.*)?$",
              text, re.M)
v = m.group(1) if m else ""
if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
    v = v[1:-1]
print(v)
PY
}

read_state() {  # read_state -> image, profile, template digest, pin (4 lines)
    python3 - "$RECORD" "$TEMPLATE" <<'PY'
import json, re, sys
rec = json.load(open(sys.argv[1]))
text = open(sys.argv[2]).read()

def env(key):
    m = re.search(rf"^[ \t]*{key}:[ \t]*(\S+)[ \t]*(?:#.*)?$", text, re.M)
    v = m.group(1) if m else ""
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else v

print(rec.get("image", ""))
print(env("COHERENCE_PROFILE"))
print(env("COHERENCE_IMAGE_MANIFEST_DIGEST"))
print(env("DEVGATE_PIN"))
PY
}

STATE_TEXT="$(read_state)" || die 1 "could not read the identity registry"
mapfile -t STATE <<<"$STATE_TEXT"
IMAGE="${REPIN_IMAGE:-${STATE[0]}}"
PROFILE="${STATE[1]}"
CURRENT_DIGEST="${STATE[2]}"
PIN_NOW="${STATE[3]}"

[ -n "$IMAGE" ] || die 1 "no image: set REPIN_IMAGE or record one in $RECORD_REL"
[ -n "$PROFILE" ] || die 1 "no COHERENCE_PROFILE in $TEMPLATE_REL"
[ -n "$CURRENT_DIGEST" ] || die 1 "no COHERENCE_IMAGE_MANIFEST_DIGEST in $TEMPLATE_REL"

# --- the pinned-tree agreement guard (D7's "re-run the chain guard") --------
# One implementation, called both at the end of a re-pin and on its own via
# REPIN_CHECK_ONLY=1, so the guarantee the operation claims and the guarantee
# the operator can re-check are the same code.
#
# It is a python program rather than a pile of shell comparisons on purpose:
# the comparisons are between values read from three different places (a
# working-tree JSON file, a template, and a blob in the pinned commit), and
# shell makes an unset index look like an empty string — which compares equal
# to another empty string and passes vacuously. Every failure below is an
# explicit exit with a message naming what disagreed.
verify_pinned_identity() {
    python3 - "$REPO_DIR" "$RECORD_REL" "$TEMPLATE_REL" <<'PY'
import json, re, subprocess, sys

repo, record_rel, template_rel = sys.argv[1], sys.argv[2], sys.argv[3]

def env(text, key):
    m = re.search(rf"^[ \t]*{key}:[ \t]*(\S+)[ \t]*(?:#.*)?$", text, re.M)
    v = m.group(1) if m else ""
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else v

def fail(msg):
    print("re-pin: " + msg, file=sys.stderr)
    raise SystemExit(4)

template = open(f"{repo}/{template_rel}").read()
t_image = env(template, "COHERENCE_IMAGE")
t_profile = env(template, "COHERENCE_PROFILE")
t_digest = env(template, "COHERENCE_IMAGE_MANIFEST_DIGEST")
pin = env(template, "DEVGATE_PIN")

if not re.fullmatch(r"[0-9a-f]{40}", pin):
    fail(f"the template declares no 40-hex DEVGATE_PIN (found {pin!r})")

def show(rev):
    r = subprocess.run(["git", "-C", repo, "show", rev],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"DEVGATE_PIN {pin} does not carry {record_rel} in its tree "
             f"({r.stderr.strip().splitlines()[0] if r.stderr.strip() else 'not in this clone'}) — "
             f"every consumer's coherence gate would land at SKIPPED. Re-pin to a "
             f"commit whose tree carries the moved record.")
    return r.stdout

# Reachability is a separate property from existence, and it is the one a
# consumer depends on: a dangling commit has an object the local clone can
# read and no consumer can fetch. This is what a re-pin on a detached HEAD
# produces, which is why that is refused before any commit is written.
anc = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", pin, "HEAD"],
                     capture_output=True, text=True)
if anc.returncode != 0:
    fail(f"DEVGATE_PIN {pin} is not an ancestor of HEAD — it exists in this "
         f"clone but no consumer that fetches this branch can resolve it, so "
         f"their coherence gate would land at SKIPPED (coh-id-04).")

pinned = json.loads(show(f"{pin}:{record_rel}"))
if not isinstance(pinned, dict):
    fail(f"DEVGATE_PIN {pin} carries a {record_rel} that is not an object")

if t_image != pinned.get("image"):
    fail(f"DEVGATE_PIN {pin} names a tree recording image {pinned.get('image')!r}, "
         f"the template pins {t_image!r}")

prof = next((p for p in pinned.get("profiles", [])
             if p.get("label") == t_profile), None)
if prof is None:
    fail(f"DEVGATE_PIN {pin} names a tree with no profile {t_profile!r} — "
         f"the template's COHERENCE_PROFILE cannot be resolved from it")
if t_digest != prof.get("image_manifest_digest"):
    fail(f"DEVGATE_PIN {pin} names a tree recording digest "
         f"{prof.get('image_manifest_digest')!r} for profile {t_profile!r}, "
         f"the template pins {t_digest!r}")

# The fourth pair: the working-tree record, which is the file this framework's
# own identity gate reads. A pin whose tree agrees with the template while the
# checked-out record disagrees is a repository that disagrees with itself.
work = json.load(open(f"{repo}/{record_rel}"))
if work.get("image") != t_image:
    fail(f"{record_rel} records image {work.get('image')!r}, the template pins "
         f"{t_image!r} — commit the record or re-pin")
wprof = next((p for p in work.get("profiles", []) if p.get("label") == t_profile), None)
if wprof is None:
    fail(f"{record_rel} has no profile {t_profile!r} — the template's "
         f"COHERENCE_PROFILE cannot be resolved from the working tree")
if wprof.get("image_manifest_digest") != t_digest:
    fail(f"{record_rel} records digest {wprof.get('image_manifest_digest')!r}, "
         f"the template pins {t_digest!r} — commit the record or re-pin")
PY
}

if [ "$CHECK_ONLY" = "1" ]; then
    if verify_pinned_identity; then
        echo "re-pin: DEVGATE_PIN $PIN_NOW carries the pinned identity ($CURRENT_DIGEST)"
        exit 0
    else
        exit 4
    fi
fi

# --- preconditions ---------------------------------------------------------
if [ -n "$(git -C "$REPO_DIR" status --porcelain)" ]; then
    die 5 "uncommitted changes in $REPO_DIR — this operation writes commits;" \
          "commit or stash them first"
fi

# Committing on a detached HEAD makes both commits dangling: the guard's
# reachability check would then refuse at the end, having already written
# them. Refuse here, where nothing has been written yet.
if ! git -C "$REPO_DIR" symbolic-ref -q HEAD >/dev/null; then
    die 5 "HEAD is detached in $REPO_DIR — commits written here belong to no" \
          "branch, so no consumer could fetch the pin. Check out a branch first"
fi

# The template must carry all three literals, exactly once each, BEFORE
# anything is committed. Discovered later, a malformed template would leave
# the record commit behind and a half-moved repository — the partial state
# this operation exists to make impossible.
python3 - "$TEMPLATE" <<'PY' || die 1 "$TEMPLATE_REL does not carry all three literals exactly once each"
import re, sys
text = open(sys.argv[1]).read()
bad = []
for key in ("COHERENCE_IMAGE", "COHERENCE_IMAGE_MANIFEST_DIGEST", "DEVGATE_PIN"):
    n = len(re.findall(rf"^[ \t]*{key}:[ \t]*\S+[ \t]*(?:#.*)?$", text, re.M))
    if n != 1:
        bad.append(f"{key} (found {n})")
if bad:
    print("re-pin: expected exactly one of each literal, got: " + ", ".join(bad),
          file=sys.stderr)
    raise SystemExit(1)
PY

ORIG="$(git -C "$REPO_DIR" rev-parse HEAD)"

# --- resolve the digest from the REGISTRY, never from local storage --------
# The same anonymous path a consumer's gate takes. A local `podman image
# inspect` answers on a different axis and is deliberately not consulted.
case "$IMAGE" in ghcr.io/*) ;; *) die 1 "$IMAGE is not a ghcr.io image path" ;; esac
REPO_PATH="${IMAGE#ghcr.io/}"

TOKEN="$(curl -fsS \
    "https://ghcr.io/token?scope=repository:${REPO_PATH}:pull&service=ghcr.io" \
    | python3 -c 'import json,sys;print(json.load(sys.stdin).get("token",""))' 2>/dev/null || true)"
[ -n "$TOKEN" ] || die 2 "could not get an anonymous pull token for $REPO_PATH —" \
                         "the registry was unreachable or refused; nothing was written"

HEADERS="$(curl -fsS -o /dev/null -D - \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' \
    "https://ghcr.io/v2/${REPO_PATH}/manifests/${REF}" 2>/dev/null || true)"
SERVED="$(printf '%s\n' "$HEADERS" | tr -d '\r' \
    | awk 'tolower($1) == "docker-content-digest:" {print $2}')"
[ -n "$SERVED" ] || die 2 "the registry served no Docker-Content-Digest for" \
                         "${IMAGE}:${REF} — nothing to pin"

echo "re-pin: ${IMAGE}:${REF} is served as $SERVED"

# --- verify the bytes are fetchable the way a consumer fetches them --------
# The pull IS the check: it verifies the fetched manifest against the requested
# digest, so a success means the registry holds bytes addressed by that digest.
# It is run BEFORE anything is recorded — discovering unfetchability later is
# how the pin spent a day naming bytes nobody could pull.
if ! REGISTRY_AUTH_FILE=/nonexistent podman pull --quiet "$IMAGE@$SERVED" >/dev/null 2>&1; then
    die 3 "the registry names $SERVED but an anonymous pull of it failed —" \
          "recording it would ship an identity every consumer's runner SKIPs on"
fi

# Commit, or restore everything and say so. A failed commit halfway through is
# a half-moved repository: the record moved and the template not, or the
# reverse. Both states land consumers at SKIPPED.
commit_staged() {  # commit_staged <message>; 0 = committed, 1 = nothing staged
    git -C "$REPO_DIR" diff --cached --quiet && return 1
    if ! git -C "$REPO_DIR" commit -q -m "$1"; then
        git -C "$REPO_DIR" reset --hard -q "$ORIG" >/dev/null 2>&1 || true
        die 6 "the commit failed (a hook, a git identity, or an index lock);" \
              "the working tree was restored to $ORIG — nothing was left applied"
    fi
    return 0
}

# --- commit 1: the record --------------------------------------------------
REPO_DIR="$REPO_DIR" RECORD="$RECORD" PROFILE="$PROFILE" IMAGE="$IMAGE" \
DIGEST="$SERVED" BUILT="${REPIN_BUILT:-$(date +%F)}" python3 - <<'PY'
import json, os
path = os.environ["RECORD"]
with open(path) as fh:
    rec = json.load(fh)
rec["image"] = os.environ["IMAGE"]
prof = next((p for p in rec["profiles"] if p.get("label") == os.environ["PROFILE"]), None)
if prof is None:
    raise SystemExit(f"no profile {os.environ['PROFILE']!r} in {path}")
prof["image_manifest_digest"] = os.environ["DIGEST"]
prof["built"] = os.environ["BUILT"]
with open(path, "w") as fh:
    json.dump(rec, fh, indent=2)
    fh.write("\n")
PY

git -C "$REPO_DIR" add "$RECORD_REL"
RECORD_CHANGED=0
if commit_staged "chore(identity): record $IMAGE@$SERVED"; then
    RECORD_CHANGED=1
fi
# Which commit the pin should name. If the record moved, it is the commit just
# written. If it did not, the pin may already name a tree carrying the served
# identity — in which case it STAYS, and a second run writes nothing at all.
# Re-pointing it at HEAD unconditionally would make every re-run append a
# commit: correct, since HEAD's tree also carries the record, but never
# idempotent, and a pin that creeps forward on every invocation is not a pin.
RECORD_SHA="$(git -C "$REPO_DIR" rev-parse HEAD)"
if [ "$RECORD_CHANGED" = "0" ] && python3 - "$REPO_DIR" "$RECORD_REL" "$PIN_NOW" \
        "$IMAGE" "$SERVED" "$PROFILE" <<'PY'
import json, subprocess, sys
repo, rel, pin, image, digest, profile = sys.argv[1:7]
if not pin:
    raise SystemExit(1)
r = subprocess.run(["git", "-C", repo, "show", f"{pin}:{rel}"],
                   capture_output=True, text=True)
if r.returncode != 0:
    raise SystemExit(1)
try:
    rec = json.loads(r.stdout)
except ValueError:
    raise SystemExit(1)
prof = next((p for p in rec.get("profiles", []) if p.get("label") == profile), None)
raise SystemExit(0 if rec.get("image") == image and prof
                 and prof.get("image_manifest_digest") == digest else 1)
PY
then
    RECORD_SHA="$PIN_NOW"
fi

# --- commit 2: the template, pinned at commit 1 ----------------------------
REPO_DIR="$REPO_DIR" TEMPLATE="$TEMPLATE" IMAGE="$IMAGE" DIGEST="$SERVED" \
PIN="$RECORD_SHA" python3 - <<'PY'
import os, re, sys
path = os.environ["TEMPLATE"]
text = open(path).read()
moved = {"COHERENCE_IMAGE": os.environ["IMAGE"],
         "COHERENCE_IMAGE_MANIFEST_DIGEST": os.environ["DIGEST"],
         "DEVGATE_PIN": os.environ["PIN"]}
for key, value in moved.items():
    text, n = re.subn(rf"^([ \t]*{key}:[ \t]*)\S+([ \t]*(?:#.*)?)$",
                      lambda m: m.group(1) + value + m.group(2), text, flags=re.M)
    if n != 1:
        print(f"re-pin: expected exactly one {key} line in {path}, found {n}",
              file=sys.stderr)
        raise SystemExit(1)
open(path, "w").write(text)
PY

git -C "$REPO_DIR" add "$TEMPLATE_REL"
TEMPLATE_CHANGED=0
if commit_staged "chore(identity): pin the template at $RECORD_SHA"; then
    TEMPLATE_CHANGED=1
fi

if [ "$RECORD_CHANGED" = "0" ] && [ "$TEMPLATE_CHANGED" = "0" ]; then
    echo "re-pin: nothing to move — the record and the template already name $SERVED"
fi

# --- fail closed if the moved literals do not agree ------------------------
if ! verify_pinned_identity; then
    git -C "$REPO_DIR" reset --hard -q "$ORIG" >/dev/null 2>&1 || true
    die 4 "the edits did not agree; the working tree was restored to $ORIG"
fi

echo "re-pin: done"
echo "  record  $RECORD_REL -> $SERVED"
echo "  pin     DEVGATE_PIN  -> $RECORD_SHA"
