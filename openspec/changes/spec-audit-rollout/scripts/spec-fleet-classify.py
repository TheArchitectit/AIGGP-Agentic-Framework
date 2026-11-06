#!/usr/bin/env python3
"""spec-fleet-classify.py — per-repo classifier for the spec intake gate.

Spec: spec-intake-gate (SGA-10..15), spec-template-provenance (SGA-20..22).

This is the MECHANICAL half of the nightly walk: given a checked-out
repository tree and (optionally) the adoption tier file, classify it into
exactly one of:

    spaced     openspec present, strict validation green, gap scan clean
    gaps       openspec present, strict validation green, gap scan found gaps
    invalid    openspec present, strict validation red
    unspaced   no openspec material at all (INFORMATIONAL, never red)
    unscannable could not clone / could not classify

SGA-11: unspaced is informational, never red. invalid reds only for repos
listed in the adoption tier file. An unparseable tier file is a gate fault,
never an empty tier.

SGA-12: clone failures / unreadable trees / scanner faults -> unscannable
with the reason, counted, named in the alert body (reason truncated to
100 chars per hub_alert's REASON_MAX_CHARS).

SGA-20..22: provenance step fetches each locked upstream artifact, hashes
it, compares. Mismatch -> drift. Unreachable upstream -> unknown + fault red,
never in-sync.

Exit codes follow the secret-scan family:
    0  classified (report written)
    2  classifier unusable (missing root, unreadable tree, bad tier file)
    3  bad invocation
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

STATE_SPACED = "spaced"
STATE_GAPS = "gaps"
STATE_INVALID = "invalid"
STATE_UNSPACED = "unspaced"
STATE_UNSCANNABLE = "unscannable"

VALID_STATES = {STATE_SPACED, STATE_GAPS, STATE_INVALID, STATE_UNSPACED, STATE_UNSCANNABLE}

REASON_MAX_CHARS = 100
BODY_CAP = 40


def parse_tier_file(path: Path) -> set[str]:
    """Parse the adoption tier file. Returns the set of tiered repo names.

    Raises ValueError on an unparseable file (SGA-11 scenario 4): a broken
    gate must never read as an empty allowlist.
    """
    if not path.exists():
        return set()
    tiered = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"tier file unreadable: {exc}") from exc
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code, _, _comment = line.partition("#")
        code = code.strip()
        if not code:
            continue
        # owner/repo form expected; a bare token is still a repo name.
        tiered.add(code)
    return tiered


def has_openspec(root: Path) -> bool:
    """True iff the tree carries openspec material (specs or changes)."""
    openspec = root / "openspec"
    if not openspec.is_dir():
        return False
    if (openspec / "specs").is_dir():
        return True
    if (openspec / "changes").is_dir():
        # any spec delta under changes/*/specs counts
        for p in (openspec / "changes").rglob("*.md"):
            if "specs" in p.relative_to(openspec / "changes").parts:
                return True
    return False


def strict_validation(root: Path) -> tuple[str, str]:
    """Run openspec validate --all --strict.

    Returns a tri-state: ("ok", ""), ("invalid", reason), ("not-run", reason).
    The distinction matters: "invalid" is a real spec defect (red for tiered
    repos per SGA-11); "not-run" is an infrastructure condition (binary
    missing, invocation failed) and must NOT be red — a fleet-wide gate that
    reds every repo because the CLI binary is absent is exactly the SGR-10
    muted-gate failure this package exists to avoid.

    The binary is resolved from SPEC_AUDIT_OPENSPEC_BIN (env), then the
    tree's own node_modules/.bin (devgate layout), then PATH. An unset env
    var is NOT a fault by itself — it falls through to the repo-local and
    PATH lookups, and only when all three are absent do we report not-run.
    """
    openspec_bin = os.environ.get("SPEC_AUDIT_OPENSPEC_BIN") or ""
    candidates = []
    if openspec_bin:
        candidates.append(Path(openspec_bin))
    # Prefer the tree's own node_modules/.bin (devgate layout).
    candidates.append(root / "node_modules" / ".bin" / "openspec")
    import shutil
    candidates.append(Path(shutil.which("openspec")) if shutil.which("openspec")
                      else Path("openspec"))
    chosen = None
    for cand in candidates:
        if cand is None:
            continue
        p = Path(cand)
        if p.is_file():
            chosen = str(p)
            break
    if chosen is None:
        # One expression: the return statement ends at its own newline, so a
        # second f-string on the next line would be dead code and the reason
        # would silently lose which sources were tried.
        return "not-run", ("openspec CLI not found (SPEC_AUDIT_OPENSPEC_BIN unset, "
                           "no node_modules/.bin/openspec, none on PATH)"
                           )[:REASON_MAX_CHARS]
    try:
        proc = subprocess.run(
            [chosen, "validate", "--all", "--strict"],
            cwd=str(root), capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "not-run", f"validator invocation failed: {exc}"[:REASON_MAX_CHARS]
    if proc.returncode != 0:
        reason = (proc.stderr or proc.stdout or "strict validation failed").strip()
        return "invalid", reason[:REASON_MAX_CHARS]
    # non-vacuity: at least one item validated
    out = proc.stdout or ""
    m = re.search(r"Totals:\s*(\d+)\s+passed", out)
    if m and int(m.group(1)) < 1:
        return "invalid", "strict validation passed 0 items (vacuous)"
    return "ok", ""


def gap_scan(root: Path) -> tuple[int, str]:
    """Run spec_gap_scan.py. Returns (gap_count, reason)."""
    scanner = None
    for cand in (root / "scripts" / "spec_gap_scan.py",
                 Path("/mnt/data/git/AIGGP-Agentic-Framework/scripts/spec_gap_scan.py")):
        if cand.is_file():
            scanner = str(cand)
            break
    if scanner is None:
        return -1, "spec_gap_scan.py not found"
    try:
        proc = subprocess.run(
            [sys.executable, scanner, "--root", str(root), "--json"],
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, f"scanner invocation failed: {exc}"[:REASON_MAX_CHARS]
    if proc.returncode == 2:
        return -1, (proc.stderr or "scanner unusable").strip()[:REASON_MAX_CHARS]
    try:
        report = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return -1, "scanner output not JSON"
    s = report.get("summary", {})
    gaps = s.get("unspaced", 0) + s.get("partially_tracked", 0) + s.get("uncovered_ids", 0)
    return gaps, ""


def classify_repo(root: Path, tiered: set[str], repo_name: str) -> dict:
    """Classify one repository tree. Returns a dict with state + details."""
    # Tier matching is form-agnostic: the tier file writes owner/repo, but the
    # walk can pass a bare repo name (local path) or a full URL. Match on the
    # repo name alone, the owner/repo form, and the full URL — a repo that
    # opted in must not read as unenforced because its name arrived bare.
    name_key = repo_name.rsplit("/", 1)[-1].lower()
    tiered_names = {t.lower() for t in tiered}
    tiered_name_keys = {t.lower().rsplit("/", 1)[-1] for t in tiered}
    tiered = name_key in tiered_name_keys or repo_name.lower() in tiered_names
    result = {
        "name": repo_name,
        "state": None,
        "reason": "",
        "tiered": tiered,
        "gaps": 0,
        "strict_ok": None,
        "has_openspec": False,
    }
    if not root.is_dir():
        result["state"] = STATE_UNSCANNABLE
        result["reason"] = f"root not a directory: {root}"[:REASON_MAX_CHARS]
        return result
    result["has_openspec"] = has_openspec(root)
    if not result["has_openspec"]:
        result["state"] = STATE_UNSPACED
        result["reason"] = "no openspec material"
        return result
    # openspec present -> run strict (tri-state)
    strict_state, strict_reason = strict_validation(root)
    result["strict_state"] = strict_state
    result["strict_reason"] = strict_reason
    if strict_state == "not-run":
        # Gate fault: the validator could not run at all. Never red, never
        # treated as spaced — a gate that evaluated nothing is not green.
        result["state"] = STATE_UNSCANNABLE
        result["reason"] = strict_reason
        return result
    if strict_state == "invalid":
        result["state"] = STATE_INVALID
        result["reason"] = strict_reason
        return result
    # strict green -> gap scan
    gaps, scan_reason = gap_scan(root)
    result["strict_state"] = strict_state
    if gaps < 0:
        # SGA-04: "unknown scope (no anchors found)" is an honest empty,
        # not a scanner fault. A repo whose layout has no game-shaped
        # anchors (DevGate itself) reports zero gaps honestly rather than
        # being marked unscannable. Any OTHER scanner failure (exit 2 with
        # a different reason) stays unscannable.
        if "unknown scope (no anchors found)" in scan_reason:
            gaps = 0
        else:
            result["state"] = STATE_UNSCANNABLE
            result["reason"] = scan_reason
            return result
    result["gaps"] = gaps
    if gaps == 0:
        result["state"] = STATE_SPACED
    else:
        result["state"] = STATE_GAPS
    return result


def check_provenance(root: Path, lock_path: Path) -> dict:
    """Template provenance step (SGA-20..22).

    Returns a dict:
      { "templates": {name: {state, pinned, upstream, ...}},
        "drift": [...], "unlocked": [...], "fault": bool }
    """
    out = {"templates": {}, "drift": [], "unlocked": [], "fault": False,
           "unknown": []}
    if not lock_path.is_file():
        # No lock file at all: every vendored template is unlocked.
        return out
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        out["fault"] = True
        out["reason"] = f"lock file unreadable: {exc}"[:REASON_MAX_CHARS]
        return out
    templates = (lock.get("templates") or {}) if isinstance(lock, dict) else {}
    # Find vendored template files in tree
    vendored = []
    for cand_dir in (root / "templates" / "openspec",
                     root / "openspec" / "templates",
                     root / ".devgate" / "templates" / "openspec"):
        if cand_dir.is_dir():
            for p in cand_dir.rglob("*"):
                if p.is_file():
                    vendored.append(p)
    # Also any file named in lock entries' vendored_path
    locked_names = set(templates.keys())
    for name, entry in templates.items():
        if not isinstance(entry, dict):
            out["fault"] = True
            continue
        source = entry.get("source")
        pinned = entry.get("pinned_sha256")
        vendored_path = entry.get("vendored_path")
        vpath = (root / vendored_path) if vendored_path else None
        state = {"name": name, "pinned": pinned, "source": source}
        if vpath is None or not vpath.is_file():
            # locked but missing on disk -> unlocked finding (and we still
            # attempt the upstream fetch below to honour SGA-22).
            out["unlocked"].append(name)
            state["status"] = "missing-vendored"
            # fall through to fetch upstream rather than continue
        if vpath is not None and vpath.is_file():
            try:
                local_hash = hashlib.sha256(vpath.read_bytes()).hexdigest()
            except OSError:
                out["fault"] = True
                out["unknown"].append(name)
                state["status"] = "unknown (local unreadable)"
                out["templates"][name] = state
                out["templates"][name] = state
                # skip upstream compare for this entry
                continue
            state["local_hash"] = local_hash
            if pinned and local_hash != pinned:
                out["drift"].append({"template": name, "kind": "local",
                                     "pinned": pinned, "actual": local_hash})
        # fetch upstream
        if source:
            try:
                with urllib.request.urlopen(source, timeout=30) as resp:
                    upstream_bytes = resp.read()
                upstream_hash = hashlib.sha256(upstream_bytes).hexdigest()
                state["upstream_hash"] = upstream_hash
                if pinned and upstream_hash != pinned:
                    out["drift"].append({"template": name, "kind": "upstream",
                                         "pinned": pinned, "upstream": upstream_hash,
                                         "version": entry.get("upstream_version")})
            except Exception as exc:  # noqa: BLE001
                out["fault"] = True
                out["unknown"].append(name)
                state["status"] = f"unknown (fetch failed): {exc}"[:REASON_MAX_CHARS]
        out["templates"][name] = state
    # unlocked vendored templates: files present but not in lock
    locked_paths = set()
    for entry in templates.values():
        if isinstance(entry, dict) and entry.get("vendored_path"):
            locked_paths.add(entry["vendored_path"])
    for p in vendored:
        rel = str(p.relative_to(root))
        if rel not in locked_paths:
            out["unlocked"].append(rel)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--tier-file", type=Path, default=None,
                    help="adoption tier file (one owner/repo per line)")
    ap.add_argument("--lock-file", type=Path, default=None,
                    help="spec-templates.lock.json path")
    ap.add_argument("--repo-name", default=None,
                    help="repository name for tier matching (owner/repo)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--report", type=Path, default=None,
                    help="write full JSON report to this path")
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"spec-fleet-classify: not a directory: {root}", file=sys.stderr)
        return 2
    tiered: set[str] = set()
    if args.tier_file is not None:
        try:
            tiered = parse_tier_file(args.tier_file.resolve())
        except ValueError as exc:
            print(f"spec-fleet-classify: gate fault: {exc}", file=sys.stderr)
            return 2
    repo_name = args.repo_name or root.name
    cls = classify_repo(root, tiered, repo_name)

    # Tier gating: invalid reds only for tiered repos (SGA-11).
    # For non-tiered repos, an invalid spec tree is reported as `gaps`-ish?
    # Per spec: invalid = openspec present, strict red. Red only past tier line.
    # We keep the state as `invalid` but mark red=False unless tiered.
    cls["red"] = (cls["state"] == STATE_INVALID and cls["tiered"])

    # Provenance
    lock_path = args.lock_file
    if lock_path is None:
        for cand in (root / "spec-templates.lock.json",
                     root / "openspec" / "spec-templates.lock.json"):
            if cand.is_file():
                lock_path = cand
                break
    prov = check_provenance(root, lock_path) if lock_path else {
        "templates": {}, "drift": [], "unlocked": [], "fault": False,
        "unknown": [], "reason": "no lock file"}
    cls["provenance"] = prov

    # Provenance fault reds the provenance section (SGA-22)
    if prov.get("fault"):
        cls["provenance_red"] = True
    else:
        cls["provenance_red"] = bool(prov.get("drift") or prov.get("unlocked")
                                     or prov.get("unknown"))

    report = {
        "root": str(root),
        "repo": repo_name,
        "classification": cls,
        "provenance": prov,
    }
    if args.as_json:
        print(json.dumps(report, indent=1))
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True),
                              encoding="utf-8")
    # Exit codes: 0 classified. Gate-fault (unscannable with reason) is still
    # a classification, reported; the walk decides red. Classifier itself only
    # returns 2 when it could not run at all.
    return 0


if __name__ == "__main__":
    sys.exit(main())
