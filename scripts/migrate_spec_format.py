#!/usr/bin/env python3
"""One-shot migration: house spec format -> OpenSpec CLI format (spec-fmt-01).

House format (12 structured specs):
    # Spec: <title>
    ## Requirement: <name>
    <!-- id: x-01 -->
    ...
    #### Scenario: ...
CLI format:
    # <title>
    ## Purpose
    <purpose paragraph>
    ## Requirements
    ### Requirement: <name>
    <!-- id: x-01 -->
    ...
    #### Scenario: ...

Ids, requirement prose, and scenarios are preserved byte-for-byte; only
heading levels and the two added sections change. Idempotent (skips files
already carrying '## Purpose').
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPECS = REPO / "openspec" / "specs"

# Hand-authored per capability — grounded in the requirement titles each spec
# actually contains, never invented capabilities.
PURPOSES = {
    "baseline-ownership":
        "Every file bundled in this repository is owned, accurate, and free of "
        "foreign-project data: bundled entries reference only paths that exist "
        "in this tree, leftover documents from absorbed projects are rewritten "
        "or removed, and instance data never ships in the baseline.",
    "ci-template-contract":
        "The shipped GitHub Actions workflow templates are drop-in correct: "
        "valid YAML, honest triggers and verdicts, pinned action references, "
        "and no advertised behavior the template does not implement. A "
        "consumer copying a template gets what its header claims.",
    "doc-truth":
        "Documentation equals the tree. Rule counts, script inventories, file "
        "names, and feature claims in README, AGENTS.md, templates, and "
        "CHANGELOG must match the files that actually ship; a doc that "
        "describes a smaller or older repo is a defect, not a nitpick.",
    "enrollment-and-alerting":
        "Spokes enroll with one-time tokens, authenticate heartbeats with "
        "per-runner revocable tokens, and the hub raises deduplicated GitHub "
        "issue alerts keyed by (repo, check-class, runner) with an append-only "
        "JSONL audit trail.",
    "gate-configuration-contract":
        "Gates are configured by data, not edits to the framework: rule and "
        "registry files have validated shapes, a project overlay may "
        "strengthen but never weaken the bundled baseline (merge by id), and "
        "an explicit path collapses resolution to that single source.",
    "gate-execution-contract":
        "Gates execute and report honestly: a scope that evaluated zero inputs "
        "never reads as a clean pass, severity ladders agree between report "
        "text and exit codes, undiffable bases fail loud, and blocking "
        "decisions are distinguishable from advisory ones.",
    "hub-architecture":
        "The runner monitor is ONE hub service bound to loopback by default; "
        "the fleet registry is instance state on the hub volume and never "
        "committed; each spoke runs a local watchdog that detects hub death "
        "without depending on the hub or on GitHub-hosted runners.",
    "publish-safety":
        "The deploy pipeline orders every reversible step before the one "
        "immutable publish: clean tree, gates, version bump, commit, tag, "
        "push, tag-reached-remote verification, and artifact verification all "
        "precede publishing, so any failure aborts with nothing published.",
    "release-gate-targeting":
        "Release and drift gates target the right tree at the right scope: "
        "release gates evaluate the project being published, drift sweeps run "
        "on a schedule rather than the PR path, and gate findings carry an "
        "audit classification instead of a bare pass/fail.",
    "rule-coverage-truth":
        "Shipped rule data is real: every rule file that ships is loaded and "
        "enforced by a named gate, every declared rule is reachable by the "
        "scanners its file_glob names, and dead rulesets do not ship in the "
        "baseline.",
    "runner-monitoring":
        "The hub polls the GitHub API for four independent check classes per "
        "watched repo — runner online status, queue-drain age, check-run "
        "conclusions on watched branches, and scheduled drift-scan recency — "
        "and raises an alert when any check fails.",
    "scanner-parsing":
        "Scanners parse their inputs correctly: diff hunks carry accurate line "
        "numbers, glob semantics match their documented fnmatch behavior, "
        "file-size classification distinguishes test files, and Godot text "
        "scenes are parsed by their real grammar.",
}


def convert(path: Path) -> bool:
    text = path.read_text()
    if "## Purpose" in text:
        return False  # already migrated
    lines = text.splitlines()
    title_line = lines[0]
    assert title_line.startswith("# "), path
    title = title_line[len("# "):].removeprefix("Spec: ").strip()
    body = lines[1:]
    # Demote requirement headings.
    out = [f"# {title}", ""]
    out += ["## Purpose", "", PURPOSES[path.parent.name], ""]
    out += ["## Requirements", ""]
    for line in body:
        if line.startswith("## Requirement:"):
            out.append("### Requirement:" + line[len("## Requirement:"):])
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n")
    return True


def main() -> int:
    changed = []
    for spec in sorted(SPECS.glob("*/spec.md")):
        cap = spec.parent.name
        if cap in ("game-regression", "game-type-phase-matrix",
                   "per-screen-tracking"):
            continue  # dispositioned separately (see the migration change)
        if convert(spec):
            changed.append(cap)
    print("converted:", ", ".join(changed) if changed else "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
