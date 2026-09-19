#!/usr/bin/env python3
"""log_failure.py — append one entry to the DevGate failure registry.

The registry header points at this script ("Use scripts/log_failure.py to add
entries consistently"). It writes exactly one valid JSON line to
.guardrails/failure-registry.jsonl (override with the FAILURE_REGISTRY_PATH env
var, the same variable scripts/regression_check.py honours). The registry is
APPEND-ONLY: this script never rewrites, reorders, or deletes existing lines.

Every bug fix should be logged here. The `regression_pattern` field is what
scripts/regression_check.py compiles and matches against newly ADDED lines of a
diff, so a fix without an entry is a fix that can silently regress.

Language-agnostic: nothing here assumes a package manager, language, or
directory layout. Paths passed to --affected-files are recorded verbatim
(repo-relative paths are the convention, so the file_glob matching in
regression_check.py can scope patterns to them).

Usage:
  python3 scripts/log_failure.py \\
      --error-message "guardrails scan matched absolute paths against relative globs" \\
      --category lint --severity high \\
      --root-cause "walk() yields absolute paths; globMatch expected repo-relative" \\
      --affected-files scripts/guardrails-scan.mjs \\
      --fix-commit 80b0c9b \\
      --regression-pattern 'globMatch\\(rule\\.file_glob, absolutePath\\)' \\
      --file-glob '*.mjs' \\
      --prevention-rule "strip the repo root before glob-matching" \\
      --status resolved

Prints the generated failure_id on success. Exit 0 on success, 1 on write error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# scripts/ lives directly under the DevGate root. DEFAULT target (H8 fix,
# fix-vacuous-and-broken-gates): the PROJECT's own overlay registry at
# <project>/.guardrails/failure-registry.jsonl — a consumer's bugs belong in
# the consumer's overlay, not in the shared baseline shipped to everyone (the
# old default wrote into the submodule and is how the shipped registry
# accumulated entries referencing other repos' files). Consumers of DevGate
# ITSELF (this repo, standalone layout) resolve to the same file the old
# default used. Opt into the baseline explicitly with --baseline.
# FAILURE_REGISTRY_PATH still overrides everything.
DEVGATE_ROOT = Path(__file__).resolve().parent.parent
if DEVGATE_ROOT.name == ".devgate":
    PROJECT_ROOT = DEVGATE_ROOT.parent
else:
    PROJECT_ROOT = DEVGATE_ROOT
DEFAULT_REGISTRY = PROJECT_ROOT / ".guardrails" / "failure-registry.jsonl"
BASELINE_REGISTRY = DEVGATE_ROOT / ".guardrails" / "failure-registry.jsonl"

CATEGORIES = ("build", "runtime", "test", "type", "lint", "deploy", "config", "regression")
SEVERITIES = ("low", "medium", "high", "critical")
STATUSES = ("active", "resolved", "deprecated")


def registry_path(baseline: bool = False) -> Path:
    """The registry to append to: FAILURE_REGISTRY_PATH, else the project
    overlay (or the bundled baseline with --baseline)."""
    override = os.environ.get("FAILURE_REGISTRY_PATH")
    if override:
        return Path(override)
    return BASELINE_REGISTRY if baseline else DEFAULT_REGISTRY


def build_entry(args: argparse.Namespace) -> dict:
    """Assemble one registry entry matching the shape already in the registry.

    Field order and names mirror the existing entries (failure_id, timestamp,
    category, severity, error_message, root_cause, affected_files, fix_commit,
    regression_pattern, prevention_rule, status, updated_at) so a hand-written
    line and a generated line are indistinguishable. `file_glob` is only
    included when supplied — it is an optional scoping field read by
    regression_check.py.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "failure_id": args.failure_id or "FAIL-" + uuid.uuid4().hex[:8],
        "timestamp": now,
        "category": args.category,
        "severity": args.severity,
        "error_message": args.error_message,
        "root_cause": args.root_cause,
        "affected_files": args.affected_files,
        "fix_commit": args.fix_commit,
        "regression_pattern": args.regression_pattern,
        "prevention_rule": args.prevention_rule,
        "status": args.status,
        "updated_at": now,
    }
    if args.file_glob:
        entry["file_glob"] = args.file_glob
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(
        description="append an entry to the DevGate failure registry (append-only)"
    )
    ap.add_argument("--error-message", required=True, help="the actual error message")
    ap.add_argument("--category", default="regression", choices=CATEGORIES)
    ap.add_argument("--severity", default="medium", choices=SEVERITIES)
    ap.add_argument("--root-cause", default="", help="why the failure occurred")
    ap.add_argument(
        "--affected-files",
        action="append",
        default=[],
        metavar="PATH",
        help="repo-relative file involved (repeatable)",
    )
    ap.add_argument("--fix-commit", default="", help="git SHA of the fixing commit")
    ap.add_argument(
        "--regression-pattern",
        default="",
        help="regex that regression_check.py matches against ADDED diff lines",
    )
    ap.add_argument(
        "--file-glob",
        action="append",
        default=[],
        metavar="GLOB",
        help="restrict regression_pattern to matching files (repeatable, optional)",
    )
    ap.add_argument("--prevention-rule", default="", help="rule preventing recurrence")
    ap.add_argument("--status", default="resolved", choices=STATUSES)
    ap.add_argument(
        "--failure-id",
        default="",
        help="explicit failure_id (default: generated FAIL-<uuid8>)",
    )
    ap.add_argument(
        "--baseline",
        action="store_true",
        help="append to the bundled DevGate baseline registry instead of the "
             "project overlay (for maintainers of DevGate itself)",
    )
    ap.add_argument(
        "--registry",
        dest="registry",
        default=None,
        metavar="PATH",
        help="explicit registry path (same as FAILURE_REGISTRY_PATH env)",
    )
    args = ap.parse_args()

    entry = build_entry(args)

    # One entry MUST be exactly one line: a newline would corrupt the JSONL.
    line = json.dumps(entry, ensure_ascii=False)
    if "\n" in line:
        print("error: serialized entry contains a newline", file=sys.stderr)
        return 1

    path = Path(args.registry) if args.registry else registry_path(args.baseline)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        with path.open("a", encoding="utf-8") as fh:
            # Newline repair: if a previous writer left the file without a
            # trailing newline, appending directly would merge two entries.
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(line + "\n")
    except OSError as exc:
        print(f"error: could not append to {path}: {exc}", file=sys.stderr)
        return 1

    print(entry["failure_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
