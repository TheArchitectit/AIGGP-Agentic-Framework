# AIGGP OpenSpec verification queue

Work sequence, resumed November 27, 2026. The [gap register](2026-11-25-aiggp-gap-register.md)
identifies the owning change and its acceptance tasks.

## Current batch

- [x] DG-21. Finish the one-invocation CI check. Run the launch-failure,
  healthy-sibling, solo recovery, and missing or zero report controls. Verify
  the pinned local and GitHub checks.
- [x] DG-22. Rehearse Release Coverage in disposable Git repositories.
  Exercise tagged and untagged product changes and the generated-report
  exception. Release metadata preparation remains pending.
- [ ] DG-02. Continue reviewing the indexed requirements against
  enforcement, named behavioral tests, ordered commits, and sealed evidence.
  Preserve the original roster and apply lifecycle transitions only for
  requirements with accepted evidence. [Batch 005](../changes/dg-02-evidence-ledger-reconciliation/batches/batch-005/README.md)
  brings detailed coverage to 60 of 182. All 182 remain UNPROVEN. The next row is DG02-U-061.

## Architecture acceptance

- [ ] Qualify monitor recovery. Exercise the supported single-writer restore and convergence path.
- [ ] Qualify consumer delivery evidence. Verify existing attestation, approval, and runtime readback for the selected target.

## Following batch

- [ ] DG-04. Review the historical archive exceptions in batches and retain the
  original task records. Route confirmed live work to its own change.
- [ ] DG-06. Verify the local art-extension and registry process. Record which
  external acceptance evidence is available from the responsible consumer.
- [ ] DG-10. Verify the offline provenance checks against isolated fixtures.
  The [offline baseline](../changes/dg10-gitlab-runner-image-provenance/offline-verification-evidence.md) records existing controls. The runner-specific preflight and authoritative builder and trust evidence remain open.
- [ ] DG-05 and DG-19. Verify any locally testable enrollment evidence and record
  remaining issuer and configured fleet evidence.

Run the task-specific local checks, pinned strict OpenSpec, and Spec State
and traceability checks where applicable. Record the exact commit and test
evidence with the owning change. Use available GitHub checks and merge each
verified PR against its checked base. Live GitLab operational checks apply
upon adoption.
