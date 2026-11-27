"""Run the consumer tests and refuse an empty test discovery result."""

import sys
import unittest


def main() -> int:
    suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
    count = suite.countTestCases()
    if count == 0:
        print("FAIL: no behavior tests discovered", file=sys.stderr)
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"Behavior test cases: {count}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
