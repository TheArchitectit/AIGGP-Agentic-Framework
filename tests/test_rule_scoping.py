#!/usr/bin/env python3
"""Rule-scope contract: file_glob + exclude_glob (rules_for_file).

regression_check.py and guardrails-scan.mjs `ruleAppliesTo` must agree on
which files a rule covers — a divergence flagged postSeo.ts's JSON-LD URL
literals in one scanner and not the other (2026-10-27).

    python3 tests/test_rule_scoping.py     # standalone
    pytest tests/test_rule_scoping.py      # via run-tests.mjs
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from regression_check import rules_for_file  # noqa: E402

# --- tests ------------------------------------------------------------------


def test_rule_exclude_glob_skips_boundary_files():
    """A rule's exclude_glob exempts its boundary files (PREVENT-029 shape).

    regression_check must agree with guardrails-scan.mjs `ruleAppliesTo`:
    JSON-LD URL literals in an exempt `src/lib/**` file are data, not network
    calls — and the same pattern must still fire in core modules.
    """
    rule = {
        "rule_id": "PREVENT-TEST029",
        "rule_type": "pattern",
        "pattern": r"https?://",
        "file_glob": ["src/**/*.ts"],
        "exclude_glob": ["src/lib/**", "src/worker.ts"],
    }
    assert rules_for_file([rule], "src/lib/postSeo.ts") == [], "exclude_glob not honored on src/lib"
    assert rules_for_file([rule], "src/worker.ts") == [], "exclude_glob not honored on exact path"
    assert rules_for_file([rule], "src/community/identity.ts") == [rule], "file_glob over-narrowed"


def test_rule_exclude_glob_applies_without_file_glob():
    """exclude_glob is honored for every rule shape, not only glob-scoped ones
    (guardrails-scan.mjs `ruleAppliesTo` agrees after the 2026-10-27 fix)."""
    bare = {
        "rule_id": "PREVENT-BARE",
        "rule_type": "pattern",
        "pattern": r"https?://",
        "exclude_glob": ["docs/*"],
    }
    assert rules_for_file([bare], "docs/notes.md") == [], "exclude_glob ignored on unscoped rule"
    assert rules_for_file([bare], "src/app.py") == [bare], "unscoped rule over-excluded"
