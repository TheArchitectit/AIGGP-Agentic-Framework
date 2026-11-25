# Design

## Context

The executable-integrity behavior is a focused capability with its own verification contract. The existing `framework-ci` specification is terminally CLOSED and carries historical requirement counts and ledger claims; adding a requirement there would inherit that closure and imply ledger authority that this remediation does not establish. The delta therefore lives under `tracked-executable-integrity`, where it publishes the gate behavior without adding top-level status or ledger rows.


`tests/test_drift_scan_template.py` begins with `#!/usr/bin/env python3` and ends with a `unittest.main()` entry point. It is exercised by pytest in `.github/workflows/ci.yml`, and can also run directly. No repository documentation or workflow invokes it by another path. Its Git index mode is `100644` at both `d10f2f1` and `fd2c11f`.

`scripts/check_exec_bits.py` explicitly reads the Git index and requires every tracked shebang file to be `100755`; the main CI workflow runs it in the “Exec-bit integrity” step. At the current head it fails only on this test file. The existing `tests/test_fw_guards.py` negative control confirms that the gate detects a shebang committed as `100644` and passes after the index mode is corrected.

## Goals / Non-Goals

**Goals:**

- Make the test's declared shebang entry point directly runnable from a clean checkout.
- Keep the index-based CI gate authoritative when working-tree mode detection is unreliable.
- Verify both direct execution and normal pytest discovery.

**Non-Goals:**

- Change the CI gate to ignore the file or remove the shebang while retaining an apparent direct-entry-point declaration.
- Change any other test's behavior, runner placement, or release policy.

## Decisions

- Commit `tests/test_drift_scan_template.py` at mode `100755`. The shebang and `unittest.main()` provide a direct test-runner entry point, and the same repository gate already requires this mode for tracked shebang files.
- Set the Git index mode explicitly with `git update-index --chmod=+x tests/test_drift_scan_template.py` when needed; `core.fileMode` can otherwise prevent a filesystem `chmod` from appearing in the index.
- Preserve the general guard. Its real-tree test and synthetic negative control exercise both the passing and failing behavior, so no exception or special case is needed.
- Add the `fw-ci-04` traceability marker to the checker when implementing this requirement; leave the existing CI invocation unchanged.

## Risks / Trade-offs

- [Mode-only edits can be lost when `core.fileMode=false`] → verify with `git ls-files --stage` and the index-based checker before commit.
- [An unrelated shebang file may remain mismatched] → run the full `scripts/check_exec_bits.py` gate, not just a direct test invocation.

## Migration Plan

There is no runtime migration. Update the index mode, run the drift test both directly and through pytest, run the executable-integrity unit tests and full gate, then verify the committed diff records `100644 => 100755` for the test module.
