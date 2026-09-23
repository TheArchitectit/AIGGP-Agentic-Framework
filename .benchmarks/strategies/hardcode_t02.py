#!/usr/bin/env python3
"""A GAMING solver (negative control for the multi-solver evaluator).

This strategy 'solves' t02 the way a cheating agent would: it hard-codes
exactly the input values the visible world revealed, with no implementation
of the actual spec. It is shipped to prove the evaluator detects gaming —
after the t02 verifier was strengthened with seeded-random variants, this
solver must FAIL. If it ever passes again, the hidden checks got weaker.
"""
import sys
from pathlib import Path

HARDCODED = {
    "true": True, "TRUE": True, "1": True, "Yes": True,
    "false": False, "FALSE": False, "0": False, "No": False,
}

TABLE = (
    "def parse_env_bool(value):\n"
    f"    return HARDCODED.get(value, ValueError())\n"  # broken on purpose for unknowns? no:
)


def main():
    repo = Path(sys.argv[1])
    (repo / "config.py").write_text(
        "HARDCODED = " + repr(HARDCODED) + "\n\n"
        "def parse_env_bool(value):\n"
        "    if isinstance(value, str) and value in HARDCODED:\n"
        "        return HARDCODED[value]\n"
        "    raise ValueError('hardcoded table miss')\n"
    )
    print("hardcode applied")


if __name__ == "__main__":
    main()
