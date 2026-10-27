#!/usr/bin/env python3
"""regression_patterns.py — prevention-pattern matching against added diff lines.

Split out of scripts/regression_diff.py to keep both under DevGate's own
500-line hard limit (the same reason regression_diff.py was once split out of
regression_check.py). One file, one concern: the per-line pattern contract
shared with guardrails-scan.mjs — test-file scope, comment-line scope,
guardrails-allow annotations and forbidden_context suppression.

regression_diff.py re-exports `check_diff_against_patterns` from here, so the
helper-module API its callers (regression_check.py, tests) import stays stable.
"""

from __future__ import annotations

import re

# Shared primitives — one implementation (scripts/gate_common.py). The old
# local line_has_allow lived here and in game_regression.py with two tolerances
# for the annotation colon; the shared form requires reason text
# (FAIL-9231181d).
from gate_common import line_has_allow  # noqa: E402


def _is_test_file(rel: str) -> bool:
    """Mirror guardrails-scan.mjs isTestFile — test paths carry no production
    pattern obligations."""
    norm = str(rel).replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    if re.search(r"(^|/)tests?/", norm):
        return True
    if base.endswith(("_test.go", "_test.rs", "_test.py", "_test.zig")):
        return True
    if re.match(r"^(conftest|test_.*|.*\.test\.|.*\.spec\.)", base):
        return True
    # Shared test-fixture modules (`*-test-helpers.ts` / `*-test-utils.ts`) —
    # see guardrails-scan.mjs isTestFile.
    return bool(re.search(r"(^|[.-])test[-_]?(helpers|utils)\.(ts|tsx|js|jsx|mjs|cjs)$",
                          base, re.I))


# Comment families mirror guardrails-scan.mjs isCommentLine: only FULL-line
# comments are out of scope; a trailing comment on a code line is still a
# code line and the code portion is scanned.
_SLASH_COMMENT_EXTS = frozenset(
    (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".svelte", ".rs", ".go",
     ".java", ".kt", ".gd", ".php", ".zig"))
_HASH_COMMENT_EXTS = frozenset((".py", ".rb", ".sh"))
_MARKUP_COMMENT_EXTS = frozenset((".html", ".xml", ".svg"))


def _is_comment_line(line: str, ext: str) -> bool:
    """Mirror guardrails-scan.mjs isCommentLine (scan_comments opt-in aside)."""
    trimmed = line.strip()
    if not trimmed:
        return False
    if ext in _HASH_COMMENT_EXTS:
        return trimmed.startswith("#")
    if ext in _MARKUP_COMMENT_EXTS:
        return trimmed.startswith("<!--")
    if ext in _SLASH_COMMENT_EXTS:
        return trimmed.startswith("//") or trimmed.startswith("/*") or trimmed.startswith("*")
    return False


def check_diff_against_patterns(diff_content: str, rules: list[dict],
                                file_path: str = "") -> list[dict]:
    """Pattern rules against the ADDED lines of one file's diff.

    Per-line semantics, identical to guardrails-scan.mjs (the shared scanner
    contract: gate_common.line_has_allow — "identical semantics intended for
    every scanner", FAIL-9231181d). A hit is silenced when that line carries
    `guardrails-allow <rule_id>: <reason>`, or when the same line carries the
    rule's forbidden_context safe usage — with the test-scoped inversion, so
    context words like (test|spec|mock) suppress only in test files or on
    lines that themselves read as test code. The earlier blob join ignored
    both: editing an annotated observability line re-flagged it, and one test
    word on any added line silenced the rule for the whole file.

    Two more shared-contract exclusions, measured as false positives on the
    vbrainstorm 2026-10-27 acceptance tree (this gate runs --pre-commit in CI
    where they hard-blocked correct code):

    * comment lines are out of scope unless the rule opts in via
      `scan_comments` — doc comments explaining why a pattern exists fire the
      rule on their own prose ("D5): any non-banned member …" matched
      PREVENT-011/PREVENT-VB-001's `:\\s*any` as if it were a type). Same
      rule guardrails-scan.mjs applies.
    * error/critical rules do not apply to test code (`_is_test_file`) —
      synthetic `new Request("http://localhost…")` route fixtures and
      `origin:` Request options are in-process harness plumbing, not network
      calls. guardrails-scan.mjs has always skipped blocking rules on test
      paths; this checker reported them anyway, so the same correct diff
      passed one scanner and failed the other.
    """
    violations = []
    added_lines = []
    for line in diff_content.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])
    test_file = _is_test_file(file_path)
    ext = "." + file_path.replace("\\", "/").rsplit(".", 1)[-1] if "." in file_path else ""
    for rule in rules:
        if rule.get("rule_type") != "pattern":
            continue
        pattern = rule.get("pattern")
        if not pattern:
            continue
        # guardrails-scan.mjs: only severity "warning" is advisory; every
        # other severity is blocking and does not apply to test code.
        if test_file and rule.get("severity") != "warning":
            continue
        try:
            rx = re.compile(pattern, re.MULTILINE)
            forbidden = rule.get("forbidden_context")
            forbidden_rx = re.compile(forbidden, re.MULTILINE) if forbidden else None
            test_scoped = bool(re.search(r"(?:test|spec|mock|__tests__|bench)", forbidden or "", re.I))
        except re.error:
            continue
        rule_id = rule.get("rule_id") or ""
        scan_comments = bool(rule.get("scan_comments"))
        for text in added_lines:
            if not scan_comments and _is_comment_line(text, ext):
                continue
            if rule_id and line_has_allow(text, rule_id):
                continue
            if not rx.search(text):
                continue
            if forbidden_rx is not None and forbidden_rx.search(text):
                line_is_test = bool(re.search(r"(?:test|spec|mock|__tests__|bench)", text, re.I))
                if not test_scoped or test_file or line_is_test:
                    continue
            violations.append({"rule_id": rule.get("rule_id"), "name": rule.get("name"),
                              "message": rule.get("message"), "severity": rule.get("severity", "warning"),
                              "suggestion": rule.get("suggestion"), "failure_id": rule.get("failure_id")})
            break  # one record per rule per file — the report lists rules, not lines
    return violations
