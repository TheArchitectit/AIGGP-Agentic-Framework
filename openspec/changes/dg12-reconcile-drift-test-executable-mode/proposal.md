# Proposal: Reconcile drift-test entry-point mode

## Why

The current `tests/test_drift_scan_template.py` declares a Python shebang and `unittest.main()` entry point, but its Git index mode is `100644`; the repository's CI executable-integrity step therefore fails on current `fd2c11f`. The mismatch has been present since the test was introduced at `ab3693b`, despite the runner-portability package recording the test behavior as verified.

## What Changes

- Keep the test module's declared direct execution path and commit it with index mode `100755`.
- Preserve the existing generic index-based executable check and its negative control; require both direct test execution and the CI integrity gate to pass.
- Record the full-tree gate result so local behavior and hosted CI use the same declared entry-point contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `framework-ci`: specify the relationship between a tracked shebang entry point and its Git index mode, including the failure result for a mismatch.

## Impact

Affected files are `tests/test_drift_scan_template.py`, `scripts/check_exec_bits.py`, and the framework CI specification/test surface. The change corrects a tracked mode mismatch and records the existing gate contract; it does not weaken or bypass CI checks. The test module remains discoverable by pytest.
