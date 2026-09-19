# Proposal: consolidate-shared-gate-logic

## Problem

The 2026-09-19 scripts review mapped the framework's shared logic and found
it implemented N times with N divergent behaviors — every divergence is either
a live bug or a future one:

| Logic | Implementations | Divergence |
|---|---|---|
| Project-root detection | 6 | `regression_check.py:83` / `failure_registry_check.py:48` (CWD walk, different markers), `scene_inventory.py:16`, `run-tests.mjs:28` + `semantic-scan.mjs:23` (walk-up **returns the start dir** — both broken standalone), `silent-success-scan.sh:59`, vs the correct contract in `guardrails-scan.mjs:23`, `game_regression.py:48`, `gate_overlay.devgate_root()` |
| Overlay merge | 3 | canonical `gate_overlay.merge_by_id`, inlined reimpl in `failure_registry_check.py:146-175`, JS mirror in `guardrails-scan.mjs:60-70`; `silent-success-scan.sh` merges nothing (M2) |
| JSONL registry parse | 3 | `gate_overlay._read_jsonl` (silent skip), `regression_diff.load_failure_registry` (status filter), `failure_registry_check._load_entries` (error reporting) |
| `guardrails-allow` annotation | 3 semantics | `regression_diff`==`game_regression` (verbatim dup, bare-colon ok), `guardrails-scan.mjs:317` (requires reason text), `semantic-scan.mjs:110` (hardcoded rule id + previous-line allowed) — FAIL-9231181d mandates identical handling in every scanner |
| Glob engine | 4 | verbatim JS copy `guardrails-scan.mjs:77`==`semantic-scan.mjs:62`, plus `regression_diff.glob_matches/_expand_globstars` and `matches_glob` in silent-success-scan.sh |
| SKIP_DIRS | 5 sets | each list drifts (`.crew`/`egg-info`/`worktrees` in only some) |
| Package-manager detect | 2 | `deploy.sh:83` (go/godot aware), `regression_audit._detect_package_manager` (not) |

This is why fixes port poorly (the guardrails-scan root fix never reached the
other two scanners) and why parity claims in comments are unverifiable.

## Solution

1. **Python**: one `scripts/gate_common.py` (stdlib-only, importable by every
   gate): `find_project_root()` (the guardrails-scan contract), `devgate_root()`,
   `merge_overlay()` (re-export of gate_overlay), `read_jsonl_registry()`,
   `allow_annotation()` (one regex, reason required — the strictest existing
   behavior, matching the documented contract), `glob_match()`, `SKIP_DIRS`,
   `NOTHING_SCANNED` reporting helper. Migrate each gate; delete local copies.
2. **Node**: extract `scripts/lib/gate_common.mjs` (root detection, glob,
   walk with error handling, allow-annotation) shared by guardrails-scan,
   semantic-scan, run-tests — one place to port the next fix.
3. **Parity tests**: a shared fixture matrix (root layouts × annotation forms
   × glob shapes × skip dirs) asserted against BOTH the Python and Node
   implementations — parity becomes enforced, not asserted in comments.
4. Behavior-freeze: every existing gate test must stay green untouched; where
   the consolidation deliberately tightens behavior (e.g., reason-required
   annotations everywhere), that lands as its own checked task with fixtures.

## Impact

- All `scripts/*.py` and `scripts/*.mjs` gates (imports only; behavior
  preserved), new `scripts/gate_common.py` + `scripts/lib/gate_common.mjs`,
  new `tests/test_gate_common.py` + `tests/test_gate_common_parity.mjs`.
- No spec deltas: `gate-configuration-contract` / `scanner-parsing` /
  `rule-coverage-truth` already define the contracts being unified;
  this is conformance + refactor (skip_specs).
