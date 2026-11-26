# Design

## Context

See proposal.md. `scripts/fleet-app-enroll.py`, `.github/workflows/fleet-app-enroll.yml`, and `tests/test_fleet_app_enroll.py` are the current surfaces. Existing tests cover pagination, archived repositories, variable reconciliation, secret creation/rotation, dry-run, per-repository failure, redaction, missing token, and workflow contract.

## Goals / Non-Goals

**Goals:** trace every ID to observable behavior and produce evidence with scope labels and integrity checks.

**Non-Goals:** altering the enrollment flow, claiming fleet-wide operation, or requiring live credentials in tests.

## Decisions

- Maintain a nine-row mapping that names exact functions, workflow lines, tests, assertions, and CI job. A static YAML assertion is identified as static evidence, not behavior.
- Use the existing sealed evidence format and validator for bundle integrity, plus the existing HMAC attestation/verifier and configured signer set for an attestation bound to the manifest digest and commit. Identify exact test status; never place secrets in artifact fields. If a valid signer is unavailable, do not make a terminal EXERCISED claim.
- Label fixture evidence hermetic and live evidence separately. An absent live artifact is recorded NOT_RUN.
- Add requirement markers only at verified enforcement functions and relevant tests during implementation; never on a file header to inflate coverage.

## Risks / Trade-offs

- [Test evidence may not match live GitHub] -> keep local and live proof types distinct.
- [Marker mapping could overclaim shared helpers] -> reviewers confirm the code path and assertion per ID before accepting a binding.

## Migration Plan

Review all nine scenarios, map code/tests/CI, run the focused suite, build/seal proof artifacts, validate them, then add only justified source markers and rerun traceability. Leave any live-only claims NOT_RUN.
