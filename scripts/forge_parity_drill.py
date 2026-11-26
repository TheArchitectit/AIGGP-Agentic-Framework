#!/usr/bin/env python3
# // spec: GLF-01, GLF-02, GLF-03
"""forge_parity_drill.py — blocking forge-parity gate over the seeded corpus.

Runs the pinned corpus (`hub/forge/corpus.lock.json`) through both forge
paths and exits non-zero on a divergence or a seed that no longer exercises
its gate. This is the CI entry point; the drill itself lives in
`hub/forge/parity.py`.

Scope, stated honestly: the gates run locally against seeded trees. This does
not stand in for a two-live-forge parity run, which is blocked on the
operator-supplied GitLab instance (Sprint 0).

Exit codes: 0 parity holds | 1 divergence or a broken/stale seed | 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hub.forge.parity import (  # noqa: E402
    LOCK_PATH,
    ParityDivergence,
    ParityDrillError,
    corpus_lock,
    run_forge_parity_drill,
)

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-lock", action="store_true",
                    help="regenerate the corpus pin and exit")
    ap.add_argument("--no-pin-check", action="store_true",
                    help="run the corpus without asserting it matches the pin")
    args = ap.parse_args(argv)

    if args.write_lock:
        LOCK_PATH.write_text(
            json.dumps(corpus_lock(), indent=1) + "\n", encoding="utf-8"
        )
        print(f"corpus pin written: {LOCK_PATH}")
        return EXIT_OK

    try:
        results = run_forge_parity_drill(verify_pin=not args.no_pin_check)
    except ParityDivergence as e:
        print(f"FAIL: forge parity divergence: {e}", file=sys.stderr)
        return EXIT_FAIL
    except ParityDrillError as e:
        print(f"FAIL: parity drill: {e}", file=sys.stderr)
        return EXIT_FAIL
    except (OSError, RuntimeError) as e:
        print(f"FAIL: parity drill could not run: {e}", file=sys.stderr)
        return EXIT_FAIL

    for result in results:
        verdict = "pass" if result.passed else "fail"
        print(
            f"{result.case_id}: {verdict} (exit {result.exit_code}, "
            f"rule {result.rule_id})"
        )
    print(f"parity drill: {len(results)} case(s), identical findings on both forge paths")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
