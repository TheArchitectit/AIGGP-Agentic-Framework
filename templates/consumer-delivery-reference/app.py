#!/usr/bin/env python3
"""Tiny synthetic application for hosted delivery qualification."""

import argparse
import sys


def evaluate(value: int) -> int:
    """Return a deterministic synthetic result, rejecting invalid input."""
    if value < 0:
        raise ValueError("value must be non-negative")
    return value * 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("value", type=int, help="synthetic input value")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.value)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"synthetic result: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
