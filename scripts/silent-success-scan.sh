#!/usr/bin/env bash
# silent-success-scan.sh — allowlist scan for silent-success / simulated-production
# markers (language-agnostic).
#
# A "silent success" is code that REPORTS a successful production operation
# without doing the work: a stub returning OK, a handler swallowing an error and
# returning nil, a function body that is a TODO. These pass type checks and any
# test that only asserts "no error" — which is precisely why they reach
# production and why a dedicated gate is worth having.
#
# How it works:
#   Detector families live in DATA, not in this script:
#     .guardrails/prevention-rules/silent-success-rules.json
#   For each ENABLED family, every file matching its file_glob is scanned line by
#   line. Each hit must be covered by an entry in
#     .guardrails/silent-success-allowlist.json
#   or the scan FAILS. A hit is covered when some entry's "file" equals the hit's
#   repo-relative path AND that entry's "marker" is a substring of the hit line.
#   That keeps known markers green while still failing on a NEW occurrence — a
#   different file, or a different marker in the same file.
#
#   EVERY family ships enabled:false, so a fresh DevGate install is GREEN and
#   this gate imposes nothing until you opt in. With no families enabled the
#   scan exits 0 immediately.
#
# Usage:
#   bash scripts/silent-success-scan.sh
#
# Exit codes: 0 = no enabled families, or every hit is allowlisted.
#             1 = a new/unlisted marker, or malformed config.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

RULES=".guardrails/prevention-rules/silent-success-rules.json"
ALLOWLIST=".guardrails/silent-success-allowlist.json"

if [ ! -f "$RULES" ]; then
	echo "silent-success-scan: no rules file ($RULES) — nothing to scan"
	exit 0
fi
if [ ! -f "$ALLOWLIST" ]; then
	echo "silent-success-scan: missing allowlist $ALLOWLIST" >&2
	exit 1
fi

python3 - "$RULES" "$ALLOWLIST" <<'PY'
import fnmatch
import json
import re
import sys
from pathlib import Path

rules_path, allowlist_path = sys.argv[1], sys.argv[2]

# DevGate lives at <project>/.devgate, so the scan target is the PROJECT root
# (the parent) when that is where the source lives; fall back to the DevGate root
# for a standalone checkout.
devgate_root = Path.cwd()
project_root = devgate_root.parent if (devgate_root.parent / ".git").exists() \
    or (devgate_root.name == ".devgate") else devgate_root

try:
    rules_doc = json.loads((devgate_root / rules_path).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"silent-success-scan: cannot read {rules_path}: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    allow = json.loads((devgate_root / allowlist_path).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"silent-success-scan: cannot read {allowlist_path}: {exc}", file=sys.stderr)
    sys.exit(1)

entries = allow.get("entries", [])

# Coverage key: (file_rel, marker_substring).
coverage = {(e.get("file", ""), e.get("marker", "")) for e in entries
            if isinstance(e, dict)}

enabled = [r for r in rules_doc.get("rules", []) if r.get("enabled") is True]
if not enabled:
    total = len(rules_doc.get("rules", []))
    print(f"silent-success-scan: no families enabled ({total} available, all "
          f"enabled:false) — skipping")
    print("  enable one in .guardrails/prevention-rules/silent-success-rules.json "
          "after allowlisting existing occurrences")
    sys.exit(0)

# Compile up front so a bad regex fails loudly instead of silently disabling a
# family (a gate that quietly stops checking is worse than no gate).
compiled = []
for rule in enabled:
    family = rule.get("family", "?")
    pattern = rule.get("regex", "")
    if not pattern:
        print(f"silent-success-scan: family '{family}' has no regex", file=sys.stderr)
        sys.exit(1)
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        print(f"silent-success-scan: family '{family}' has an invalid regex "
              f"({exc}): {pattern}", file=sys.stderr)
        sys.exit(1)
    compiled.append((family, rx, rule.get("file_glob") or []))

SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", "out", "vendor",
             "__pycache__", ".venv", "venv", ".next", ".nuxt", ".devgate",
             ".claude", "worktrees"}


def matches_glob(rel: str, globs) -> bool:
    """True when the repo-relative path OR its basename matches any glob."""
    base = rel.rsplit("/", 1)[-1]
    for g in globs:
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(base, g):
            return True
        # Allow 'src/**/*' to match 'src/a.rs' as well as 'src/a/b.rs'.
        if g.endswith("/**/*") and (rel == g[:-5] or rel.startswith(g[:-4])):
            return True
    return False


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        yield path


print(f"silent-success-scan: {len(compiled)} enabled family(ies); scanning "
      f"{project_root}")

files = list(iter_files(project_root))
uncovered = []
allowlisted = 0

for path in files:
    rel = path.relative_to(project_root).as_posix()
    applicable = [(f, rx) for f, rx, globs in compiled if matches_glob(rel, globs)]
    if not applicable:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    for lineno, line in enumerate(text.splitlines(), 1):
        for family, rx in applicable:
            if not rx.search(line):
                continue
            if any(fl == rel and mk and mk in line for fl, mk in coverage):
                allowlisted += 1
                print(f"  [allowlisted] {rel}:{lineno} ({family})")
            else:
                print(f"  [NEW/unlisted] {rel}:{lineno} ({family}): {line.strip()[:120]}")
                uncovered.append((rel, lineno, family))

if uncovered:
    print(f"\nsilent-success-scan: FAIL — {len(uncovered)} unlisted marker(s).")
    print("Either fix the code so it does the real work (preferred), or — if the")
    print("marker is deliberately tolerated — add it to")
    print(f"  {allowlist_path}")
    print('as {"file": "<path>", "marker": "<substring>", "family": "...",')
    print(' "reason": "...", "removal": "<sprint/ticket>"}.')
    sys.exit(1)

print(f"\nsilent-success-scan: OK — every detected marker is allowlisted "
      f"({allowlisted} hit(s), {len(entries)} allowlist entr(ies)).")
sys.exit(0)
PY

exit $?
