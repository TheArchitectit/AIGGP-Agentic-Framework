#!/usr/bin/env python3
"""check_diff_against_patterns must honor the shared scanner contract.

FAIL-9231181d pins `guardrails-allow <ID>: <reason>` as "identical semantics
intended for every scanner". regression_diff.check_added_against_registry and
game_regression.py honored it; the prevention-pattern checker joined the added
lines into one blob and ignored annotations entirely, so editing an annotated
observability line (worker.ts's structured Cloudflare drain) re-flagged it and
a single test word on any added line silenced the rule for the whole file.

Runnable standalone or via pytest (same as test_regression_check.py):

    python3 tests/test_diff_pattern_allow.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from regression_diff import check_diff_against_patterns  # noqa: E402


def _rule(**over) -> dict:
    base = {
        "rule_type": "pattern",
        "rule_id": "PREVENT-012",
        "name": "TypeScript/JS: console.log in production",
        "pattern": r"console\.(log|debug|info)",
        "message": "console.log left in production code",
        "severity": "warning",
    }
    base.update(over)
    return base


def _diff(*added: str) -> str:
    body = "\n".join(f"+{line}" for line in added)
    return f"diff --git a/src/worker.ts b/src/worker.ts\n--- a/src/worker.ts\n+++ b/src/worker.ts\n@@ -1,1 +1,{len(added)} @@\n{body}\n"


def test_allow_annotation_silences_the_named_rule():
    """The worker.ts case: an edited observability line that carries its
    per-line reason must not re-fire."""
    diff = _diff(
        'console.log(JSON.stringify({ msg: "api_request" })); // guardrails-allow PREVENT-012: structured Cloudflare request-drain log',
    )
    assert check_diff_against_patterns(diff, [_rule()], "src/worker.ts") == []


def test_unannotated_line_in_same_diff_still_fires():
    """Annotations are per line — one allowed line must not silence the rest."""
    diff = _diff(
        'console.log(a); // guardrails-allow PREVENT-012: intentional observability',
        "console.log(b);",
    )
    violations = check_diff_against_patterns(diff, [_rule()], "src/worker.ts")
    assert len(violations) == 1, f"unannotated hit missed: {violations}"


def test_allow_for_other_rule_does_not_silence():
    """Substring-only matching would let any allow silence every pattern."""
    diff = _diff("console.log(a); // guardrails-allow PREVENT-999: unrelated exemption")
    violations = check_diff_against_patterns(diff, [_rule()], "src/worker.ts")
    assert len(violations) == 1, f"unrelated allow leaked silence: {violations}"


def test_forbidden_context_is_per_line_not_blob():
    """A test word on an unrelated added line must not silence the whole file
    (the blob-join defect), and safe usage on the hit line must silence it."""
    rules = [_rule(forbidden_context=r"(test|spec|mock|__tests__)")]
    # Unrelated test-ish line + bare hit: must fire (old blob form suppressed).
    diff = _diff("// testing the drain", "console.log(x);")
    violations = check_diff_against_patterns(diff, rules, "src/worker.ts")
    assert len(violations) == 1, f"blob-wide context leaked silence: {violations}"
    # Same line carries the safe usage: must not fire.
    diff_ok = _diff('console.log(x); // my test harness output')
    assert check_diff_against_patterns(diff_ok, rules, "src/worker.ts") == []


def test_test_scoped_context_does_not_silence_production_lines():
    """PREVENT-003's (example|placeholder|test|sample) context must not silence
    a production line that merely matches a context word (guardrails-scan.mjs
    test-scoped inversion)."""
    rules = [_rule(rule_id="PREVENT-003", pattern=r"password\s*=", forbidden_context=r"(example|placeholder|test|sample)")]
    prod = _diff('password = "sample_key"')
    violations = check_diff_against_patterns(prod, rules, "src/app.py")
    assert len(violations) == 1, f"production line silenced by context word: {violations}"
    # The same line in a test file keeps the exclusion.
    assert check_diff_against_patterns(prod, rules, "tests/test_app.py") == []


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
