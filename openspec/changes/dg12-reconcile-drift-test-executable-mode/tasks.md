# Tasks

## 1. Reconcile the declared entry point

- [ ] 1.1 Set `tests/test_drift_scan_template.py` to Git index mode `100755` with `git update-index --chmod=+x tests/test_drift_scan_template.py` when needed; verify `git ls-files --stage` reports mode `100755`.
- [ ] 1.2 Keep the `fw-ci-04` marker on `scripts/check_exec_bits.py` and retain its generic index-mode behavior; verify `python3 -m pytest tests/test_fw_guards.py -q` passes, including the non-executable negative control and real-tree positive check.

## 2. Verify the full test and gate path

- [ ] 2.1 Run `./tests/test_drift_scan_template.py` and `python3 -m pytest tests/test_drift_scan_template.py -q`; verify direct invocation and pytest discovery both pass.
- [ ] 2.2 Run the CI command `python3 scripts/check_exec_bits.py`; verify the result lists the tracked shebang count and reports all modes as `100755`.
- [ ] 2.3 Verify `git diff --summary -- tests/test_drift_scan_template.py` shows the executable-mode change and no unrelated source or test changes.

## Workflow follow-up

- Archive after independent review; then run `openspec validate --all --strict`, `scripts/spec_traceability.py`, and update `CHANGELOG.md` according to the repository archive procedure.
