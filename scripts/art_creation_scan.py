#!/usr/bin/env python3
"""art_creation_scan.py - entry point for the art creation contract scan.

Reads a title's declared art brief and provenance ledger, plus the pipeline
stages declared inline in the manifest, and fails on the conditions
`openspec/changes/add-art-creation-contract` states. There is no separate
pipeline-document path: the stage contract is the manifest's `stages` list.

The checks themselves are split at the source soft limit:
  art_checks.py        declaration and inventory (brief, stages, ledger, rights)
  art_check_outcome.py did it survive, get accepted, and reach a player

This file owns the manifest lookup, the check orchestration and the
exit-code contract, including the NOT_APPLICABLE rule.

A title declares its paths in a manifest (default `art-creation.json` at the
root). A title that declares nothing is **NOT_APPLICABLE**, never green. A
zero-input run that reports success is exactly the failure `art-draw-01` exists
to prevent.

Exit codes:
    0   every applicable check passed
    1   at least one contract failure
    2   usage error
    3   NOT_APPLICABLE - this title declares no art pipeline

`--selftest` runs built-in fixtures and never reads a title.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Re-exported so the fixture suite and any other consumer can import the
# public surface from the entry point, unchanged.
from art_checks import (  # noqa: F401
    DIGEST_STAGES,
    Finding,
    check_brief,
    check_ledger,
    check_rights,
    check_stages,
    load_json,
)
from art_check_outcome import (  # noqa: F401
    check_acceptance,
    check_bytes,
    check_draw,
    check_quantity,
)

MANIFEST_NAME = "art-creation.json"


def find_manifest(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = (root / explicit) if not Path(explicit).is_absolute() else Path(explicit)
        return p if p.is_file() else None
    p = root / MANIFEST_NAME
    return p if p.is_file() else None


def run_checks(cfg: dict, root: Path) -> list:
    """Run every applicable check in dependency order and return the findings."""
    out: list[Finding] = []
    rows = check_ledger(cfg, root, out)
    stage_enum = check_stages(cfg, root, out)
    if rows:
        check_brief(cfg, root, rows, out)
        check_bytes(cfg, rows, out)
        check_acceptance(cfg, rows, stage_enum, out)
        check_rights(rows, out)
        check_quantity(rows, out)
    check_draw(cfg, out)
    return out


def report(findings: list, declared: bool, counted: int) -> int:
    # The zero-input rule lives here: a title that declares no pipeline is
    # NOT_APPLICABLE, never green. This is the exit-code contract, not the
    # target-draws requirement: `report` never inspects targets, captures,
    # renderer or geometry, so it cannot be that requirement's enforcement
    # site. `check_draw` in art_check_outcome.py is, and its marker lives
    # there. A marker here would keep traceability green after the real check
    # was deleted - the lie the gate cannot catch.
    if not declared:
        print("art-scan: NOT_APPLICABLE - this title declares no art pipeline")
        print("art-scan: a zero-input run is not a green run")
        return 3
    for f in findings:
        print(f.line())
    if findings:
        reqs = sorted({f.req for f in findings})
        print(f"art-scan: {len(findings)} contract failure(s) across "
              f"{len(reqs)} requirement(s): {', '.join(reqs)}")
        return 1
    print(f"art-scan: pass - {counted} asset(s), every applicable check green")
    return 0


# --- selftest ---------------------------------------------------------------
# The fixture suite lives in test_art_creation_scan.py (test-file size limit).
# It imports run_checks from here and asserts the EXACT requirement set each
# negative trips. `--selftest` is kept so the entry point is unchanged.

def selftest() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_art_creation_scan import selftest as _run
    return _run()


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="art_creation_scan.py")
    ap.add_argument("--root", default=".")
    ap.add_argument("--config", default=None,
                    help=f"path to the manifest (default {MANIFEST_NAME} at root)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = Path(args.root).resolve()
    manifest = find_manifest(root, args.config)
    if manifest is None:
        # An explicitly named manifest that is not there is a usage error, not
        # a title that declares nothing. Returning 3 here turned a typo'd
        # --config into "NOT_APPLICABLE", which reads like a clean skip.
        if args.config:
            print(f"art-scan: manifest not found: {args.config}", file=sys.stderr)
            return 2
        return report([], declared=False, counted=0)

    cfg = load_json(manifest)
    if isinstance(cfg, Exception):
        print(f"art-scan: manifest unreadable: {cfg}", file=sys.stderr)
        return 2
    # Valid JSON is not a valid manifest. A list (or a string, number, null)
    # parsed cleanly and then died on `cfg.get(...)` inside the checks - a
    # traceback instead of the exit-2 usage error the docstring promises.
    if not isinstance(cfg, dict):
        print(f"art-scan: manifest is not a JSON object: {manifest}", file=sys.stderr)
        return 2
    findings = run_checks(cfg, root)
    counted = 0
    rel = cfg.get("ledger")
    if isinstance(rel, str) and rel:
        data = load_json(root / rel)
        if not isinstance(data, Exception):
            rows = data.get("assets") if isinstance(data, dict) else data
            counted = len(rows) if isinstance(rows, list) else 0
    return report(findings, declared=True, counted=counted)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
