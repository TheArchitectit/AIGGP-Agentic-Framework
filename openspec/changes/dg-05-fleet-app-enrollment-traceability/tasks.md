# Tasks

## 1. Per-requirement evidence map

- [x] 1.1 Map `fleet-app-01` through `fleet-app-09` to exact script functions/workflow steps, behavioral tests, assertions, and CI invocation; verify every mapping by reading its code path.
- [x] 1.2 Compare each canonical scenario with actual test assertions; record static-only, absent, skipped, hermetic, and live-only evidence distinctly.

## 2. Sealed verification

- [x] 2.1 Run focused `pytest tests/test_fleet_app_enroll.py` with CI dependencies and record commit/test outcomes; verify no coverage-critical case is skipped.
- [ ] 2.2 Seal per-requirement evidence and run the existing evidence validator; verify bundle integrity, a configured-signer attestation bound to bundle digest and commit, test identity, and absence of secrets; when signing is unavailable, record NOT_RUN.
- [x] 2.3 Mark actual enrollment workflow/live fleet runs NOT_RUN unless a real signed run artifact is reviewed; verify no hermetic result is described as live.
- [x] 2.4 Add source markers only at reviewed enforcing sites and update the mapping; run traceability and verify each marker resolves to that site.
