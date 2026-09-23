#!/usr/bin/env python3
"""gen-checksums.py — release-artifact checksums with a verify mode (R12).

Generates sha256 checksums for every shipped script (the gate surface a
consumer actually executes) and verifies them. The release process is:
generate at tag time, commit the manifest, verify in CI or on install.

Verify mode recomputes and compares — it does not trust the manifest's own
digest lines. Exit: 0 verified / 1 mismatch or missing / 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = "CHECKSUMS.sha256"
EXIT_OK, EXIT_MISMATCH, EXIT_USAGE = 0, 1, 2


def tracked_scripts(repo: Path) -> list[str]:
    r = subprocess.run(["git", "ls-files", "scripts/", "hub/"], cwd=str(repo),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gen-checksums: git ls-files failed: {r.stderr}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return sorted(l for l in r.stdout.splitlines()
                  if l.endswith((".py", ".mjs", ".sh")) or "/" not in l
                  and "." in Path(l).name)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(prog="gen-checksums",
                                 description="generate/verify release checksums")
    ap.add_argument("mode", choices=["generate", "verify"])
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    out = repo / MANIFEST

    files = tracked_scripts(repo)
    if not files:
        print("gen-checksums: FAIL — no tracked scripts found", file=sys.stderr)
        return EXIT_MISMATCH

    if args.mode == "generate":
        lines = [
            f"# DevGate release checksums — generated "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "# Verify before use: python3 scripts/gen-checksums.py verify",
        ]
        for rel in files:
            lines.append(f"{digest(repo / rel)}  {rel}")
        out.write_text("\n".join(lines) + "\n")
        print(f"gen-checksums: wrote {len(files)} checksums to {MANIFEST}")
        return EXIT_OK

    # verify
    if not out.exists():
        print(f"gen-checksums: FAIL — {MANIFEST} missing", file=sys.stderr)
        return EXIT_MISMATCH
    recorded = {}
    for line in out.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not parts[1].startswith(("scripts/", "hub/")):
            print(f"gen-checksums: FAIL — malformed manifest line: {line[:60]}",
                  file=sys.stderr)
            return EXIT_MISMATCH
        recorded[parts[1].strip()] = parts[0]
    current = {rel: digest(repo / rel) for rel in files}

    problems = []
    for rel, want in recorded.items():
        if rel not in current:
            problems.append(f"{rel}: in manifest but no longer tracked")
        elif current[rel] != want:
            problems.append(f"{rel}: DIGEST MISMATCH")
    for rel in current:
        if rel not in recorded:
            problems.append(f"{rel}: shipped script missing from manifest")

    if problems:
        print(f"gen-checksums: VERIFY FAIL — {len(problems)} problem(s):")
        for p in problems:
            print(f"  {p}")
        return EXIT_MISMATCH
    print(f"gen-checksums: VERIFY OK — {len(recorded)} checksums match")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
