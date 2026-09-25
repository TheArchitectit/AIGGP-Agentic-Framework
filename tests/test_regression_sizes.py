#!/usr/bin/env python3
"""Fixture-based tests for the file-size gate's scope + classification.

Satisfies the prevention_rule recorded in FAIL-f6228dda: "scope lists and
matchers need a self-test that feeds them a file they MUST flag". A size gate
that evaluates no test file reports '0 over hard limit' — green that inspected
nothing. These tests call check_file_sizes' own API with known-oversize
fixtures and assert what the gate evaluates, at which limit, and under which
classification.

Runnable two ways (DevGate's run-tests.mjs discovers test_*.py via pytest, and
this file also works standalone with plain asserts):

    python3 tests/test_regression_sizes.py     # standalone
    pytest tests/test_regression_sizes.py      # via run-tests.mjs
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from regression_check import PROJECT_ROOT, SOURCE_DIRS  # noqa: E402
from regression_sizes import (  # noqa: E402
    SRC_HARD,
    TEST_HARD,
    check_file_sizes,
)


def _write_fixture(root: Path, rel_path: str, line_count: int) -> Path:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"value_{i} = {i}" for i in range(line_count)) + "\n",
                    encoding="utf-8")
    return path


def _write_sh_fixture(root: Path, rel_path: str, line_count: int) -> Path:
    """A shell fixture. The gate counts lines and does not read the language,
    but a fixture that claims to be a shell script should be one — a reader
    who checks 'does this really exercise .sh?' should get a yes."""
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"true  # line {i}" for i in range(line_count - 1))
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    return path


def test_oversize_test_file_is_flagged_at_test_hard():
    """MUST-flag: a TEST_HARD+1-line pytest file is a blocking violation."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_fixture(root, "tests/test_giant.py", TEST_HARD + 1)
        issues = check_file_sizes(root, ["tests"])
        hard = [i for i in issues if i["kind"] == "hard"]
        assert len(hard) == 1, f"oversize test file not flagged: {issues}"
        v = hard[0]
        assert v["file"] == "tests/test_giant.py", v
        assert v["lines"] == TEST_HARD + 1, v
        assert v["hard"] == TEST_HARD, (
            f"evaluated at hard={v['hard']}, not TEST_HARD — test classification is broken"
        )
        assert v["severity"] == "error", v


def test_gate_really_evaluates_the_directory():
    """The scan above must come from evaluating the fixture, not an empty pass."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_fixture(root, "tests/test_giant.py", TEST_HARD + 1)
        flagged = check_file_sizes(root, ["tests"])
        (root / "tests" / "test_giant.py").unlink()
        clean = check_file_sizes(root, ["tests"])
        assert flagged, "gate reported nothing for a known-oversize fixture"
        assert clean == [], f"unrelated finding leaked: {clean}"


def test_pytest_file_over_source_limit_stays_under_test_hard():
    """gate-size-01 scenario: 550-line tests/test_big.py -> TEST_HARD, not SRC_HARD."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_fixture(root, "tests/test_big.py", 550)
        issues = check_file_sizes(root, ["tests"])
        assert issues == [], (
            f"550-line test file flagged at {issues} — misclassified against SRC_HARD"
        )


def test_non_test_file_at_same_size_is_flagged_at_src_hard():
    """Matcher contrast: classification, not size, separates the two fixtures."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_fixture(root, "tests/test_501.py", SRC_HARD + 1)
        _write_fixture(root, "scripts/helper.py", SRC_HARD + 1)
        issues = check_file_sizes(root, ["tests", "scripts"])
        by_file = {i["file"]: i for i in issues}
        assert "tests/test_501.py" not in by_file, (
            f"pytest file evaluated at source limits: {by_file}"
        )
        assert "scripts/helper.py" in by_file, f"oversize source not flagged: {issues}"
        assert by_file["scripts/helper.py"]["hard"] == SRC_HARD, by_file


def test_oversize_shell_script_is_flagged_at_src_hard():
    """MUST-flag, and the reason task #13 exists: SOURCE_EXTENSIONS named
    sixteen languages and none of them was the one this repository's
    fleet-side scripts are written in. `scripts/` was walked, the `.sh` files
    inside it were not sized, and `scripts/runner-enroll.sh` reached 589 lines
    against a 500-line limit with the gate reporting nothing — the same shape
    as FAIL-f6228dda, where the scope list silently excluded a directory."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_sh_fixture(root, "scripts/giant.sh", SRC_HARD + 1)
        issues = check_file_sizes(root, ["scripts"])
        hard = [i for i in issues if i["kind"] == "hard"]
        assert len(hard) == 1, f"oversize shell script not flagged: {issues}"
        v = hard[0]
        assert v["file"] == "scripts/giant.sh", v
        assert v["lines"] == SRC_HARD + 1, v
        assert v["hard"] == SRC_HARD, (
            f"evaluated at hard={v['hard']}, not SRC_HARD: {v}")
        assert v["severity"] == "error", v


def test_a_shell_test_file_is_judged_at_the_test_limit():
    """The `test_*` prefix convention is not a Python fact — it is how a test
    file is named. Adding `.sh` to the scope without it would judge a shell
    test at SRC_HARD while its Python sibling gets TEST_HARD, which is the
    inconsistency this extension is the one moment to avoid introducing."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_sh_fixture(root, "tests/test_big.sh", 550)
        issues = check_file_sizes(root, ["tests"])
        assert issues == [], (
            f"550-line shell test flagged at {issues} — misclassified against SRC_HARD"
        )
        _write_sh_fixture(root, "tests/test_giant.sh", TEST_HARD + 1)
        issues = check_file_sizes(root, ["tests"])
        assert [i["file"] for i in issues] == ["tests/test_giant.sh"], (
            f"the shell-test fixtures produced other findings: {issues}")
        assert issues[0]["hard"] == TEST_HARD, issues[0]


def test_source_dirs_include_test_directories():
    """FAIL-f6228dda scope defect: tests/ must be a candidate, not just hub/scripts."""
    for candidate in ("tests", "test"):
        if (PROJECT_ROOT / candidate).is_dir():
            assert candidate in SOURCE_DIRS, (
                f"{candidate}/ exists under the project root but SOURCE_DIRS "
                f"skips it — the size gate never walks test files ({SOURCE_DIRS})"
            )


def test_source_dirs_include_the_directory_the_shell_scripts_live_in():
    """Found by the mutation battery, not by a RED: `.sh` in SOURCE_EXTENSIONS
    is inert unless the walk enters scripts/, and nothing asserted that it
    does. `test_source_dirs_include_test_directories` pins tests/ only, so
    dropping "scripts" from the candidate list was uncaught while every shell
    script in this repository — the language this file's scope extension was
    written for — silently stopped being sized. FAIL-f6228dda was a scope list
    drifting from its intent; the scope list needs its own MUST-flag test."""
    assert (PROJECT_ROOT / "scripts").is_dir(), (
        "fixture assumption broken: this repository has no scripts/ directory")
    assert "scripts" in SOURCE_DIRS, (
        f"scripts/ exists under the project root but SOURCE_DIRS skips it — no "
        f"shell script in this repository is sized ({SOURCE_DIRS})"
    )


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
