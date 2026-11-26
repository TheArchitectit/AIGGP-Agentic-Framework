# DG-12 verification

The drift template test is indexed at mode `100755` and can import its
existing platform helper when invoked directly. Direct execution passed
five tests from the repository and from a different working directory.
Pytest passed five drift template checks and seven framework guard checks,
including the negative mode diagnostic and the real-tree positive control.

The CI command `python3 scripts/check_exec_bits.py` verified all 160 tracked
shebang entry points as mode `100755`. The integrity checker carries
`fw-ci-04` and its checking behavior is unchanged. Failure record
`FAIL-af61592d` documents the original mode mismatch.
