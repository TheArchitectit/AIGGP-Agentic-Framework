#!/usr/bin/env python3
# spec: fw-storage-01
"""artifact_hygiene.py — GitHub Actions storage hygiene (fw-storage-01).

WHY THIS EXISTS (measured, not theoretical)

GitHub Actions storage is metered per account for PRIVATE repositories. Two
separate allowances apply, and they are not the same pool:

  * artifact storage (shared with GitHub Packages), and
  * cache storage (a separate allowance, 10 GB per repository).

On 2026-10-17 the fleet hit the literal error

    Failed to CreateArtifact: Artifact storage quota has been hit.
    Unable to upload any new artifacts.

and the failing step was always the UPLOAD, never the gate that produced the
evidence. So the gates stayed green while release evidence and SBOM
attachments silently stopped being retained. The 2026-10-17 policy
(infra-info ci-fleet/artifact-quota-policy.md) fixed the *upload* side by
gating uploads on failure or tag and bounding retention.

That policy has no enforcement and no cleanup half. This gate is both:

  1. AUDIT (static, no network). Every `actions/upload-artifact` step must
     carry a `retention-days:` bound, and that bound must not exceed
     `max_retention_days` in `.guardrails/storage-policy.json`. An unbounded
     upload is a future quota incident with a commit date on it. This runs on
     every push, so the defect is caught where it is written rather than in
     next month's billing.

  2. TRIM (live, needs a token). Delete artifacts older than
     `trim_keep_days` while always preserving the newest `trim_keep_latest`
     per artifact name, and delete caches not accessed within
     `cache_max_idle_days`. Dry-run by default; `--apply` deletes.

WHY TRIM IS BOUNDED BY NAME AND NOT BY AGE ALONE

An age-only rule deletes the release evidence a tag produced, which is the
one artifact the policy deliberately keeps. Preserving the newest N per name
means a nightly report keeps its trend line while the tail above the bound is
removed, and a release artifact survives regardless of age.

FAIL-CLOSED, NON-VACUOUS

The audit FAILS on zero workflow files scanned: a scan that evaluated nothing
must never read as green, which is the failure mode this gate exists to
prevent and it applies to the gate first. Zero *upload steps* is reported
explicitly rather than left to inference -- a repo with no uploads genuinely
has no upload risk, and saying so is different from saying nothing.

Exit: 0 clean; 1 findings/api failure; 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

POLICY_REL = Path(".guardrails") / "storage-policy.json"
WORKFLOW_DIR = Path(".github") / "workflows"

DEFAULT_POLICY = {
    "max_retention_days": 90,
    "trim_keep_days": 30,
    "trim_keep_latest": 5,
    "cache_max_idle_days": 14,
}

UPLOAD_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*actions/upload-artifact@(\S+)")


def load_policy(repo: Path) -> dict:
    """The declared bounds. A malformed policy is a hard error, never a
    silent fall-through to defaults: a policy file that cannot be read must
    not make the gate *less* strict than the file asked for."""
    p = repo / POLICY_REL
    if not p.is_file():
        return dict(DEFAULT_POLICY)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[storage] FAIL: {POLICY_REL} is not readable JSON: {e}",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    out = dict(DEFAULT_POLICY)
    for k in DEFAULT_POLICY:
        if k in data:
            v = data[k]
            if not isinstance(v, int) or v < 0:
                print(f"[storage] FAIL: {POLICY_REL} {k}={v!r} is not a "
                      f"non-negative integer", file=sys.stderr)
                sys.exit(EXIT_USAGE)
            out[k] = v
    return out


def _step_block(lines: list[str], use_idx: int) -> tuple[int, int]:
    """The enclosing step's line range for the upload at use_idx.

    In this repository the step is written `- uses: actions/upload-artifact@...`,
    so the `- ` is on the upload line itself and the step STARTS there. Only
    when it is written as a later key of a step (`- name: x` / `  uses: ...`)
    is there anything to walk back to -- and then the walk stops at the nearest
    `- ` at the same indent, which is that step's first line.

    The walk must not cross the boundary into a PRECEDING step: its body is
    indented DEEPER than its own `- `, so a naive `while indent <= n` walk
    sails past the boundary and can hand a bounded step's `retention-days:` to
    an unbounded neighbour -- which is exactly the failure this check exists to
    catch, one step over. Pinned by
    test_bound_belongs_to_its_own_step_not_a_neighbour.
    """
    raw = lines[use_idx]
    indent = len(raw) - len(raw.lstrip(" "))
    start = use_idx
    if not raw.strip().startswith("- "):
        while start > 0:
            prev = lines[start - 1]
            pind = len(prev) - len(prev.lstrip(" "))
            if pind < indent:
                break
            if pind == indent and prev.strip().startswith("- "):
                start -= 1
                break
            start -= 1
    end = len(lines)
    for j in range(use_idx + 1, len(lines)):
        raw = lines[j]
        if not raw.strip():
            continue
        jind = len(raw) - len(raw.lstrip(" "))
        if jind < indent:
            end = j
            break
        if jind == indent and raw.strip().startswith("- "):
            end = j
            break
    return start, end


def audit(repo: Path, policy: dict) -> list[str]:
    """Static audit of every upload step. Returns findings; empty is clean."""
    wdir = repo / WORKFLOW_DIR
    findings: list[str] = []
    if not wdir.is_dir():
        findings.append(f"no {WORKFLOW_DIR}/ directory -- nothing was scanned")
        return findings
    files = sorted(p for p in wdir.glob("*.yml")) + \
        sorted(p for p in wdir.glob("*.yaml"))
    if not files:
        findings.append(f"{WORKFLOW_DIR}/ holds no workflow files -- "
                        f"nothing was scanned (a vacuous scan is not a pass)")
        return findings

    max_days = policy["max_retention_days"]
    uploads = 0
    for f in files:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if not UPLOAD_RE.match(line):
                continue
            uploads += 1
            start, end = _step_block(lines, i)
            block = "\n".join(lines[start:end])
            rel = f.relative_to(repo)
            m = re.search(r"^\s*retention-days:\s*(\d+)\s*$", block, re.M)
            if m is None:
                findings.append(
                    f"{rel}:{i + 1}: upload-artifact step has no "
                    f"retention-days bound -- an unbounded artifact is a "
                    f"future quota incident")
                continue
            days = int(m.group(1))
            if days > max_days:
                findings.append(
                    f"{rel}:{i + 1}: retention-days {days} exceeds the "
                    f"declared maximum {max_days} (storage-policy.json)")

    print(f"[storage] audit scope: {len(files)} workflow file(s), "
          f"{uploads} upload-artifact step(s), max_retention_days={max_days}")
    if uploads == 0:
        print("[storage] 0 upload steps inspected -- nothing to bound. "
              "This is a real clean state, not a skipped scan.")
    return findings


def _utc(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def select_artifacts(arts: list[dict], keep_days: int, keep_latest: int,
                     now: datetime) -> list[dict]:
    """Artifacts to delete.

    Two rules, in this order:

      * an artifact GitHub marks **expired** is always deletable -- retention
        has already judged it dead, and keeping it is bookkeeping with no
        reader. It does not consume the newest-N budget either, so an expired
        head cannot shield the live tail behind it.
      * among live artifacts, the newest `keep_latest` PER NAME are protected
        regardless of age, and the rest are deleted once older than
        `keep_days`. Per name, not per repo: a global 'newest N' would let one
        busy artifact name shield an unrelated stale one.
    """
    expired = [a for a in arts if a.get("expired")]
    live = [a for a in arts if not a.get("expired")]
    ordered = sorted(live, key=lambda a: a["created_at"], reverse=True)
    protected: set[int] = set()
    seen: dict[str, int] = {}
    for a in ordered:
        n = a.get("name", "")
        if seen.get(n, 0) < keep_latest:
            seen[n] = seen.get(n, 0) + 1
            protected.add(a["id"])
    doomed = [a for a in ordered
              if a["id"] not in protected
              and (now - _utc(a["created_at"])).days > keep_days]
    return doomed + expired


def select_caches(caches: list[dict], idle_days: int,
                  now: datetime) -> list[dict]:
    doomed = []
    for c in caches:
        stamp = c.get("last_accessed_at") or c.get("created_at")
        if stamp and (now - _utc(stamp)).days > idle_days:
            doomed.append(c)
    return doomed


def _api(url: str, token: str, method: str = "GET") -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}
    except OSError as e:
        return 0, {"error": str(e)[:300]}


def _paginate(slug: str, token: str, path: str, key: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        st, data = _api(f"https://api.github.com/repos/{slug}{path}"
                        f"?per_page=100&page={page}", token)
        if st != 200:
            raise RuntimeError(f"GET {path} -> {st} {data}")
        items = data.get(key) or []
        out.extend(items)
        if len(items) < 100:
            return out
        page += 1


def trim(slug: str, token: str, policy: dict, apply: bool) -> int:
    now = datetime.now(timezone.utc)
    try:
        arts = _paginate(slug, token, "/actions/artifacts", "artifacts")
        caches = _paginate(slug, token, "/actions/caches", "actions_caches")
    except RuntimeError as e:
        print(f"[storage] FAIL: {e}", file=sys.stderr)
        return EXIT_FINDINGS

    d_arts = select_artifacts(arts, policy["trim_keep_days"],
                              policy["trim_keep_latest"], now)
    d_caches = select_caches(caches, policy["cache_max_idle_days"], now)
    a_bytes = sum(a.get("size_in_bytes", 0) for a in d_arts)
    c_bytes = sum(c.get("size_in_bytes", 0) for c in d_caches)
    print(f"[storage] trim scope: {len(arts)} artifact(s), "
          f"{len(caches)} cache(s) in {slug}")
    print(f"[storage] selected: {len(d_arts)} artifact(s) "
          f"({a_bytes} B), {len(d_caches)} cache(s) ({c_bytes} B) "
          f"[keep_days={policy['trim_keep_days']} "
          f"keep_latest={policy['trim_keep_latest']} "
          f"cache_idle={policy['cache_max_idle_days']}]")

    if not apply:
        for a in d_arts:
            print(f"  would delete artifact {a['id']} {a.get('name')} "
                  f"{a.get('created_at')}")
        for c in d_caches:
            print(f"  would delete cache {c['id']} {c.get('key')}")
        print("[storage] dry run -- pass --apply to delete")
        return EXIT_OK

    failed = 0
    art_ok = cache_ok = 0
    for a in d_arts:
        st, data = _api(f"https://api.github.com/repos/{slug}"
                        f"/actions/artifacts/{a['id']}", token, "DELETE")
        if st == 204:
            art_ok += 1
        else:
            failed += 1
            print(f"  FAILED artifact {a['id']}: {st} {data}", file=sys.stderr)
    for c in d_caches:
        st, data = _api(f"https://api.github.com/repos/{slug}"
                        f"/actions/caches/{c['id']}", token, "DELETE")
        if st == 204:
            cache_ok += 1
        else:
            failed += 1
            print(f"  FAILED cache {c['id']}: {st} {data}", file=sys.stderr)
    print(f"[storage] deleted {art_ok} artifact(s) and {cache_ok} cache(s); "
          f"{failed} failure(s)")
    return EXIT_FINDINGS if failed else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="artifact_hygiene",
                                 description="artifact/cache hygiene "
                                             "(fw-storage-01)")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--audit", action="store_true",
                    help="static audit of upload-artifact retention bounds")
    ap.add_argument("--trim", action="store_true",
                    help="list/delete artifacts and caches beyond policy")
    ap.add_argument("--repo-slug", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--apply", action="store_true",
                    help="perform deletions (default is a dry run)")
    args = ap.parse_args(argv)

    if not args.audit and not args.trim:
        ap.error("choose --audit and/or --trim")

    repo = Path(args.repo).resolve()
    policy = load_policy(repo)
    rc = EXIT_OK

    if args.audit:
        findings = audit(repo, policy)
        if findings:
            print(f"[storage] FAIL: {len(findings)} finding(s):")
            for f in findings:
                print(f"  {f}")
            rc = EXIT_FINDINGS
        else:
            print("[storage] audit OK: every upload step is bound")

    if args.trim:
        if not args.repo_slug:
            print("[storage] --trim needs --repo-slug owner/name "
                  "(or GITHUB_REPOSITORY)", file=sys.stderr)
            return EXIT_USAGE
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            print(f"[storage] missing token: set GH_TOKEN or GITHUB_TOKEN "
                  f"to trim {args.repo_slug}", file=sys.stderr)
            return EXIT_USAGE
        tr = trim(args.repo_slug, token, policy, args.apply)
        rc = max(rc, tr)

    return rc


if __name__ == "__main__":
    sys.exit(main())
