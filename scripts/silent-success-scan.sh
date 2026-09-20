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
#   The families in effect are the DevGate BASELINE merged with the consuming
#   project's overlay of the same path — <project>/.guardrails/prevention-rules/
#   silent-success-rules.json — so a repo can retune a family (scope it, change
#   its severity) or add one WITHOUT forking the submodule baseline. Overlay wins
#   on a matching "family" id (replaced in place), new families append; a project
#   with no overlay gets byte-identical baseline behaviour. This is the same
#   bundled-baseline + project-overlay convention as gate_overlay.py /
#   guardrails-scan.mjs (the allowlist is NOT overlaid — it keys into one repo's
#   tree, so it stays submodule-only by design).
#   For each ENABLED family, every file matching its file_glob is scanned line by
#   line, EXCEPT files matching that family's optional "exclude_globs" (e.g.
#   ["*_test.go"] to keep a Go family out of test files — where discarding an
#   error is often idiomatic). Exclusion is per-family: a file excluded for one
#   family is still scanned by the others whose file_glob matches.
#   Each remaining hit must be covered by an entry in
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
# Exit codes: 0 = no enabled families, or every hit is allowlisted/excluded.
#             1 = a new/unlisted marker, or malformed config (including a
#                 malformed project overlay — the merge fails closed, it does not
#                 fall back to the baseline and quietly drop the overlay).

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
import os
import re
import sys
from pathlib import Path

rules_path, allowlist_path = sys.argv[1], sys.argv[2]

# DevGate lives at <project>/.devgate, so the scan target is the PROJECT root
# (the parent) when that is where the source lives; fall back to the DevGate root
# for a standalone checkout.
devgate_root = Path.cwd()
# SILENT_SUCCESS_SCAN_ROOT overrides the scan target — the canary test uses
# it to prove this gate FAILS on a planted violation (a gate that cannot
# fail is decoration, not a gate).
project_root = Path(os.environ["SILENT_SUCCESS_SCAN_ROOT"]) \
    if os.environ.get("SILENT_SUCCESS_SCAN_ROOT") \
    else (devgate_root.parent if (devgate_root.parent / ".git").exists()
          or (devgate_root.name == ".devgate") else devgate_root)

try:
    rules_doc = json.loads((devgate_root / rules_path).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"silent-success-scan: cannot read {rules_path}: {exc}", file=sys.stderr)
    sys.exit(1)

# Bundled baseline + project overlay (gate_overlay.py's merge contract, keyed by
# "family"): an overlay entry replaces the same-family baseline entry in place,
# new families append. No overlay file -> baseline only, byte-identical to the
# pre-overlay behaviour every other consumer relies on. A present-but-malformed
# overlay FAILS CLOSED (exit 1) — falling back to the baseline would quietly
# drop the project's rules, which is the failure mode this whole class of gates
# exists to refuse.
rules = rules_doc.get("rules", [])
overlay_path = project_root / rules_path
if overlay_path.exists() and overlay_path.resolve() != (devgate_root / rules_path).resolve():
    try:
        sys.path.insert(0, str(devgate_root / "scripts"))
        import gate_overlay
        overlay_rules = json.loads(overlay_path.read_text(encoding="utf-8")).get("rules", [])
    except (OSError, json.JSONDecodeError, ImportError) as exc:
        print(f"silent-success-scan: cannot read project overlay {overlay_path}: {exc}",
              file=sys.stderr)
        sys.exit(1)
    if not isinstance(overlay_rules, list):
        print(f"silent-success-scan: project overlay {overlay_path} has a non-list "
              f"'rules' key", file=sys.stderr)
        sys.exit(1)
    rules = gate_overlay.merge_by_id(rules, overlay_rules, "family")
    print(f"silent-success-scan: {len(rules)} family(ies) in effect (bundled "
          f"baseline + {overlay_path.relative_to(project_root)} overlay merged)")

try:
    # SILENT_SUCCESS_SCAN_ALLOWLIST overrides the allowlist location for
    # the canary test (same principle: exercise the real code path).
    allow_src = Path(os.environ["SILENT_SUCCESS_SCAN_ALLOWLIST"]) \
        if os.environ.get("SILENT_SUCCESS_SCAN_ALLOWLIST") \
        else (devgate_root / allowlist_path)
    allow = json.loads(allow_src.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"silent-success-scan: cannot read {allowlist_path}: {exc}", file=sys.stderr)
    sys.exit(1)

entries = allow.get("entries", [])

# Coverage key: (file_rel, marker_substring).
coverage = {(e.get("file", ""), e.get("marker", "")) for e in entries
            if isinstance(e, dict)}

enabled = [r for r in rules if r.get("enabled") is True]
if not enabled:
    total = len(rules)
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
    excludes = rule.get("exclude_globs") or []
    if not isinstance(excludes, list):
        print(f"silent-success-scan: family '{family}' has a non-list "
              f"exclude_globs: {excludes!r}", file=sys.stderr)
        sys.exit(1)
    compiled.append((family, rx, rule.get("file_glob") or [], excludes))

SKIP_DIRS = {".git", "node_modules", "target", "dist", "build", "out", "vendor",
             "__pycache__", ".venv", "venv", ".next", ".nuxt", ".devgate",
             ".claude", "worktrees", ".sandbox-home"}


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
excluded = 0

for path in files:
    rel = path.relative_to(project_root).as_posix()
    # Exclusion is PER-FAMILY: a file excluded for one family stays fully
    # scanned by every other family whose file_glob matches it.
    applicable = [(f, rx, bool(ex_globs) and matches_glob(rel, ex_globs))
                  for f, rx, globs, ex_globs in compiled if matches_glob(rel, globs)]
    if not applicable:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    for lineno, line in enumerate(text.splitlines(), 1):
        for family, rx, skip_this in applicable:
            if not rx.search(line):
                continue
            if skip_this:
                excluded += 1
                print(f"  [excluded] {rel}:{lineno} ({family})")
            elif any(fl == rel and mk and mk in line for fl, mk in coverage):
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

print(f"\nsilent-success-scan: OK — every detected marker is allowlisted or "
      f"excluded ({allowlisted} allowlisted, {excluded} excluded by family "
      f"exclude_globs, {len(entries)} allowlist entr(ies)).")
sys.exit(0)
PY

exit $?
