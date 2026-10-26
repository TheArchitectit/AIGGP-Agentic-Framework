#!/usr/bin/env python3
"""baseline_ownership_check.py - base-own-01 for the bundled baseline DATA files.

Requirement (openspec/specs/baseline-ownership, `base-own-01`): "Every entry in a
bundled baseline data file (failure registry, silent-success allowlist,
prevention rules, openspec specs) SHALL reference only paths, bugs, and
capabilities of this repository; a hygiene gate SHALL fail when a bundled entry
references a path absent from this tree."

scripts/failure_registry_check.py enforces the failure-registry half of that
sentence. This gate enforces the silent-success-allowlist half, because that is
the bundled file a CONSUMING project legitimately copies over with its own
entries - the one most likely to drift back into foreign data, and the one that
did: emptied on 2026-09-19 (QA H3) and silently restored with 1,725 gamerepo01
entries on 2026-09-20 until 2026-10-25. Two checks, both mechanical:

  1. every entry's "file" must name a path that exists in the tree that ships
     the file (the "paths absent from this tree" clause);
  2. every entry's "family" must be declared by the bundled rules file
     .guardrails/prevention-rules/silent-success-rules.json (the "capabilities
     of this repository" clause - an entry for a detector this repo does not
     ship describes another repository's gate);
  3. that family must also be ENABLED there. A declared-but-disabled family
     never evaluates a file, so an entry for it suppresses nothing while
     counting as coverage - the same "a number the gate never uses" defect as
     the 1,727 inert entries, one level down.

What this gate deliberately does NOT claim: prevention-rules files carry globs
("*.go", "Dockerfile") rather than repository paths, so there is no
path-existence predicate to settle for them; and openspec specs are prose whose
"references" cannot be decided mechanically. Both were measured on 2026-10-25
rather than assumed (docs/qa/2026-10-25-baseline-allowlist-ownership.md): the
bundled rule files carried four foreign-project state assertions in `note`
fields, all corrected, and no foreign path claimed to be in this tree. Those
halves remain covered by other gates (spec_traceability.py for requirement ids,
base-specs-01's game-merge pointer rule) and are named here so the omission is
stated, not implied.

Usage:
  python3 scripts/baseline_ownership_check.py [--repo PATH] [--max-report N]

Exit 0 when every bundled allowlist entry is this repository's; 1 on any
finding, and 1 (fail closed) when the bundled files it is supposed to read are
missing or malformed - a gate that cannot read its input must not report green.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWLIST_REL = Path(".guardrails") / "silent-success-allowlist.json"
RULES_REL = Path(".guardrails") / "prevention-rules" / "silent-success-rules.json"


def _load(path: Path, findings: list[str]) -> object | None:
    """Read one bundled JSON file; a missing or malformed file is a finding."""
    if not path.exists():
        findings.append(f"{path}: bundled baseline file is missing (fail closed)")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"{path}: cannot be read as JSON ({exc}) (fail closed)")
        return None


def check(repo: Path) -> tuple[int, list[str]]:
    """Return (exit code, findings) for the bundled baseline files under repo."""
    repo = repo.resolve()
    findings: list[str] = []

    allow_doc = _load(repo / ALLOWLIST_REL, findings)
    rules_doc = _load(repo / RULES_REL, findings)
    if allow_doc is None or rules_doc is None:
        return 1, findings

    entries = allow_doc.get("entries") if isinstance(allow_doc, dict) else None
    if not isinstance(entries, list):
        findings.append(f"{ALLOWLIST_REL}: 'entries' is not a list (fail closed)")
        return 1, findings

    declared = set()
    enabled = set()
    rules = rules_doc.get("rules") if isinstance(rules_doc, dict) else None
    if not isinstance(rules, list):
        findings.append(f"{RULES_REL}: 'rules' is not a list (fail closed)")
        return 1, findings
    for rule in rules:
        if isinstance(rule, dict) and rule.get("family"):
            declared.add(rule["family"])
            if rule.get("enabled") is True:
                enabled.add(rule["family"])

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            findings.append(f"{ALLOWLIST_REL}: entry #{index} is not an object")
            continue
        rel = entry.get("file")
        if not isinstance(rel, str) or not rel.strip():
            findings.append(f"{ALLOWLIST_REL}: entry #{index} has no 'file'")
        else:
            candidate = Path(rel)
            if candidate.is_absolute() or rel.startswith("~"):
                findings.append(
                    f"{ALLOWLIST_REL}: entry #{index} names an absolute path "
                    f"'{rel}' (base-own-01 - a bundled entry may name only a "
                    f"path inside this tree)"
                )
            elif not (repo / candidate).exists():
                findings.append(
                    f"{ALLOWLIST_REL}: entry #{index} names '{rel}', which does "
                    f"not exist in this tree (base-own-01)"
                )
        family = entry.get("family")
        if family not in declared:
            findings.append(
                f"{ALLOWLIST_REL}: entry #{index} names family '{family}', which "
                f"{RULES_REL.as_posix()} does not declare (base-own-01 - not a "
                f"capability of this repository)"
            )
        elif family not in enabled:
            findings.append(
                f"{ALLOWLIST_REL}: entry #{index} names family '{family}', which "
                f"{RULES_REL.as_posix()} ships disabled (base-own-01 - an entry for "
                f"a disabled detector suppresses nothing)"
            )

    return (1 if findings else 0), findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="base-own-01 for the bundled baseline data files"
    )
    parser.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parent.parent),
        help="repository root to check (default: this checkout's DevGate root)",
    )
    parser.add_argument(
        "--max-report",
        type=int,
        default=25,
        metavar="N",
        help="print at most N findings, then a count (default: 25)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"baseline-ownership-check: no such directory: {repo}", file=sys.stderr)
        return 1

    code, findings = check(repo)
    if code == 0:
        print(f"baseline-ownership-check: OK - bundled allowlist entries under "
              f"{repo} are this repository's")
        return 0

    shown = findings[: max(args.max_report, 1)]
    for finding in shown:
        print(f"baseline-ownership-check: {finding}", file=sys.stderr)
    if len(findings) > len(shown):
        print(f"baseline-ownership-check: ... and {len(findings) - len(shown)} more "
              f"finding(s) ({len(findings)} total)", file=sys.stderr)
    print(f"baseline-ownership-check: FAIL - {len(findings)} finding(s)",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
