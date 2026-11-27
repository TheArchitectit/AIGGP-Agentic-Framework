#!/usr/bin/env python3
"""Create a standalone synthetic consumer from an empty destination."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_DEVGATE_SHA = "bdbd450e0275a05b319ce29d83f761e8ed552e69"
WORKFLOW_SOURCE = "templates/github-workflows/text-integrity.yml"
PLACEHOLDER = "REPLACE_WITH_REVIEWED_FULL_40_HEX_COMMIT"
FILES = (
    "app.py",
    ".gitattributes",
    ".gitignore",
    ".guardrails/scope.json",
    ".guardrails/charset-allowlist.json",
    ".github/workflows/reference-consumer.yml",
    "tests/test_app.py",
    "tests/run_tests.py",
)


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=check
    )


def materialize(destination: Path, devgate_sha: str) -> str:
    source_root = Path(__file__).resolve().parents[2]
    if not re.fullmatch(r"[0-9a-f]{40}", devgate_sha):
        raise ValueError("DevGate revision must be a full lowercase 40-character SHA")
    if git(source_root, "cat-file", "-e", f"{devgate_sha}^{{commit}}", check=False).returncode:
        raise ValueError(f"DevGate commit is unavailable locally: {devgate_sha}")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("destination must be an empty directory")

    destination.parent.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).resolve().parent
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    try:
        for relative in FILES:
            source = template / relative
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"allowlisted template file is missing or unsafe: {relative}")
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

        workflow = git(source_root, "show", f"{devgate_sha}:{WORKFLOW_SOURCE}").stdout
        if workflow.count(PLACEHOLDER) != 1:
            raise ValueError("pinned workflow must contain exactly one DevGate SHA placeholder")
        workflow = workflow.replace(PLACEHOLDER, devgate_sha)
        workflow_path = stage / ".github/workflows/text-integrity.yml"
        workflow_path.write_text(workflow, encoding="utf-8", newline="\n")

        git(stage, "init", "--quiet")
        git(stage, "add", "--all")
        git(
            stage,
            "-c", "user.name=Synthetic Consumer",
            "-c", "user.email=synthetic-consumer@example.invalid",
            "commit", "--quiet", "-m", "Create synthetic reference consumer",
        )
        if destination.exists():
            destination.rmdir()
        stage.replace(destination)
    except (OSError, ValueError, subprocess.CalledProcessError):
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return git(destination, "rev-parse", "HEAD").stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="empty directory for the consumer repository")
    parser.add_argument("--devgate-sha", default=DEFAULT_DEVGATE_SHA)
    args = parser.parse_args(argv)
    try:
        consumer_sha = materialize(args.destination.resolve(), args.devgate_sha)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"materialization failed: {exc}", file=sys.stderr)
        return 1
    print(f"consumer repository: {args.destination.resolve()}")
    print(f"consumer commit: {consumer_sha}")
    print(f"DevGate commit: {args.devgate_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
