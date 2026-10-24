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
        code, _sep, reason = line.partition("#")
        code = code.strip()
        if not code:
            continue
        # The reason is load-bearing: an entry without one is a quiet hole
        # (the rule the secret sweep's exclude file uses). Refuse the file
        # rather than enforce a hole as if it were a decision.
        if not reason.strip():
            raise ValueError(f"tier entry without a reason: line {lineno}: {code}")
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
        # Name what was actually tried. The first version said "env unset"
        # unconditionally — false whenever it was set to a path that is not a
        # file, and the operator reading the alert would chase the wrong thing.
        # One expression: the return statement ends at its own newline, so a
        # second f-string on the next line would be dead code and the reason
        # would silently lose which sources were tried.
        tried = ("SPEC_AUDIT_OPENSPEC_BIN set but not a file" if openspec_bin
                 else "SPEC_AUDIT_OPENSPEC_BIN unset")
        return "not-run", (f"openspec CLI not found ({tried}; "
                           f"no node_modules/.bin/openspec; none on PATH)"
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
    env_bin = os.environ.get("SPEC_AUDIT_GAP_SCANNER") or ""
    candidates = [Path(env_bin)] if env_bin else []
    # This file's own repo (the gate's host) carries the scanner; the tree
    # under audit may carry its own copy, which is used only if ours is gone.
    candidates.append(Path(__file__).resolve().parent / "spec_gap_scan.py")
    candidates.append(root / "scripts" / "spec_gap_scan.py")
    for cand in candidates:
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


def load_lock_templates(lock_path: Path) -> tuple[dict, str]:
    """Read the lock. Returns (templates, error). An unreadable lock is a fault."""
    if lock_path is None or not Path(lock_path).is_file():
        return {}, "no lock file"
    try:
        lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"lock file unreadable: {exc}"[:REASON_MAX_CHARS]
    templates = (lock.get("templates") or {}) if isinstance(lock, dict) else {}
    for name, entry in list(templates.items()):
        if not isinstance(entry, dict):
            return {}, f"lock entry {name} is not an object"
    return templates, ""


def fetch_hash(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return hashlib.sha256(resp.read()).hexdigest()


def check_lock(lock_path: Path) -> dict:
    """Lock-level provenance (SGA-20..22): is the lock's own pin honest, and
    has upstream moved?

    Computed ONCE per sweep, not per repo. Upstream drift is a property of the
    lock, not of the tree being classified: reporting it on every row prints
    the same finding N times and buries the real per-tree findings.
    """
    out = {"templates": {}, "drift": [], "unlocked": [], "fault": False,
           "unknown": []}
    templates, err = load_lock_templates(lock_path)
    if err and err != "no lock file":
        out["fault"] = True
        out["reason"] = err
        return out
    if err:
        out["reason"] = err
        return out
    for name, entry in templates.items():
        pinned = entry.get("pinned_sha256")
        state = {"name": name, "pinned": pinned, "source": entry.get("source"),
                 "pin_source": entry.get("pin_source"),
                 "status": "vendored" if entry.get("vendored_path") else "not-vendored"}
        # pin integrity: the URL the pin was verified at must still hash to it.
        # A mismatch means the lock is lying about its own pin -> gate fault.
        pin_source = entry.get("pin_source")
        if pin_source:
            try:
                pin_hash = fetch_hash(pin_source)
                state["pin_source_hash"] = pin_hash
                if pinned and pin_hash != pinned:
                    out["fault"] = True
                    state["status"] = "fault (pin_source does not match pinned_sha256)"
            except Exception as exc:  # noqa: BLE001
                out["fault"] = True
                out["unknown"].append(name)
                state["status"] = f"unknown (pin_source fetch failed): {exc}"[:REASON_MAX_CHARS]
        # upstream: the moving source. A difference is upstream drift — the
        # SGA-21 alert — never a bad pin.
        source = entry.get("source")
        if source:
            try:
                upstream_hash = fetch_hash(source)
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
    return out


def check_provenance(root: Path, lock_path: Path) -> dict:
    """Per-tree provenance: the vendored copies in THIS tree against the pins.

    No network here — pin integrity and upstream drift belong to check_lock,
    which the walk runs once. What is checked here is local: a copy in tree
    that no longer matches its pin (local drift), a locked copy that is gone
    (unlocked), and a vendored file the lock does not know (unlocked).
    """
    out = {"templates": {}, "drift": [], "unlocked": [], "fault": False,
           "unknown": []}
    templates, err = load_lock_templates(lock_path)
    if err:
        out["reason"] = err
        return out
    vendored = []
    for cand_dir in (root / "templates" / "openspec",
                     root / "openspec" / "templates",
                     root / ".devgate" / "templates" / "openspec"):
        if cand_dir.is_dir():
            for f in cand_dir.rglob("*"):
                if f.is_file():
                    vendored.append(f)
    for name, entry in templates.items():
        vendored_path = entry.get("vendored_path")
        pinned = entry.get("pinned_sha256")
        if vendored_path is None:
            # Deliberately not vendored: a documented decision, not a finding.
            continue
        vpath = root / vendored_path
        state = {"name": name, "pinned": pinned, "vendored_path": vendored_path}
        if not vpath.is_file():
            out["unlocked"].append(name)
            state["status"] = "missing-vendored"
            out["templates"][name] = state
            continue
        try:
            local_hash = hashlib.sha256(vpath.read_bytes()).hexdigest()
        except OSError:
            out["fault"] = True
            out["unknown"].append(name)
            state["status"] = "unknown (local unreadable)"
            out["templates"][name] = state
            continue
        state["local_hash"] = local_hash
        if pinned and local_hash != pinned:
            out["drift"].append({"template": name, "kind": "local",
                                 "pinned": pinned, "actual": local_hash})
        out["templates"][name] = state
    # vendored files present but not in the lock
    locked_paths = {e.get("vendored_path") for e in templates.values()
                    if isinstance(e, dict) and e.get("vendored_path")}
    for f in vendored:
        rel = str(f.relative_to(root))
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
    ap.add_argument("--lock-check-only", action="store_true",
                    help="emit the lock-level provenance report and exit "
                         "(the walk runs this once per sweep, not per repo)")
    args = ap.parse_args()
    if args.lock_check_only:
        lock_path = args.lock_file
        if lock_path is None:
            print("spec-fleet-classify: --lock-check-only needs --lock-file",
                  file=sys.stderr)
            return 2
        print(json.dumps(check_lock(lock_path), indent=1))
        return 0
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

    # Tier gating: `invalid` keeps its state for every repo (it is the honest
    # answer to "openspec present, strict red"), but it is RED only for a repo
    # past the tier line (SGA-11). A repo that never accepted the contract
    # gets the same finding as information, never as failure.
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

    # SGA-22: a fault — unreadable lock, unreadable local copy — is red.
    # Findings (local drift, unlocked) go to the deduped drift issue (SGA-21),
    # not to red: the SGR-10 lesson is that a gate red on every notice gets
    # muted and then misses the real ones.
    cls["provenance_red"] = bool(prov.get("fault") or prov.get("unknown"))
    cls["provenance_findings"] = bool(prov.get("drift") or prov.get("unlocked"))

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
