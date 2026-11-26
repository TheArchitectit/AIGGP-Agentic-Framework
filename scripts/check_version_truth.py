#!/usr/bin/env python3
# spec: doc-version-01
"""check_version_truth.py — VERSION, CHANGELOG.md, and git tags agree (doc-version-01).

doc-version-01: "VERSION, CHANGELOG.md, and git tags SHALL describe the same
release history; the release pipeline SHALL update every artifact it owns in
one step." This gate is the standing half of that contract — it checks the
AGREEMENT on the tree it is pointed at:

  * VERSION (when present) equals the newest `v<semver>` git tag;
  * every `v<semver>` tag has a `## [X.Y.Z]` section in CHANGELOG.md;
  * every `## [X.Y.Z]` section in CHANGELOG.md has that git tag — a version
    heading with no tag is a release claim nothing backs.

Both directions matter. The 2026-11-03 audit found a hand-bumped VERSION and
a dated `## [1.3.0]` section for a release that was never tagged, defended by
a changelog statement that the artifacts "intentionally disagree". One of
those three artifacts was lying; this gate names which.

Fail-closed and non-vacuous: a missing VERSION, a missing CHANGELOG.md, or a
repository whose tags are not visible (shallow CI checkouts do not fetch
tags) is a FAILURE, never a pass. deploy.sh writes and re-verifies the same
agreement at release time.

Exit: 0 all three agree; 1 any disagreement (each named); 2 usage/unreadable.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_DISAGREE = 1
EXIT_USAGE = 2

TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
SECTION_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]")


def _git_tags(repo: Path) -> list:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "tag", "--list"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"check-version-truth: FAIL - cannot read git tags: {exc}",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    tags = [m.group(0) for line in out.stdout.splitlines()
            if (m := TAG_RE.match(line.strip()))]
    return tags


def _version_key(tag: str):
    return tuple(int(p) for p in tag[1:].split("."))


def _changelog_versions(text: str) -> list:
    return [m.group(1) for line in text.splitlines()
            if (m := SECTION_RE.match(line))]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="VERSION / CHANGELOG.md / git tags agreement (doc-version-01)")
    ap.add_argument("--repo", default=".", help="repository root")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"check-version-truth: FAIL - not a directory: {repo}",
              file=sys.stderr)
        return EXIT_USAGE

    version_path = repo / "VERSION"
    changelog_path = repo / "CHANGELOG.md"
    for path in (version_path, changelog_path):
        if not path.is_file():
            print(f"check-version-truth: FAIL - {path.name} is missing; "
                  f"doc-version-01 owns it and it must exist",
                  file=sys.stderr)
            return EXIT_DISAGREE
    try:
        version = version_path.read_text(encoding="utf-8").strip()
        changelog = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"check-version-truth: FAIL - unreadable: {exc}", file=sys.stderr)
        return EXIT_USAGE

    tags = _git_tags(repo)
    if not tags:
        print("check-version-truth: FAIL - no v* semver tags visible; VERSION "
              "cannot agree with a tag set that was not fetched (CI needs "
              "fetch-depth 0 or fetch-tags: true)", file=sys.stderr)
        return EXIT_DISAGREE

    newest = max(tags, key=_version_key)
    sections = _changelog_versions(changelog)
    problems = []

    if version != newest[1:]:
        problems.append(
            f"VERSION reads {version!r} but the newest v* tag is {newest} "
            f"(doc-version-01: VERSION equals the newest tag)")
    for tag in tags:
        if tag[1:] not in sections:
            problems.append(
                f"git tag {tag} has no CHANGELOG.md section '## [{tag[1:]}]'")
    for ver in sections:
        if f"v{ver}" not in tags:
            problems.append(
                f"CHANGELOG.md section '## [{ver}]' claims a release with no "
                f"git tag v{ver}")

    if problems:
        for problem in problems:
            print(f"check-version-truth: FAIL - {problem}", file=sys.stderr)
        return EXIT_DISAGREE
    print(f"check-version-truth: OK - VERSION {version} == newest tag {newest}, "
          f"{len(tags)} tag(s) all documented in CHANGELOG.md")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
