# Tasks

## 1. Reconcile the delivered manifest

- [x] 1.1 Add the `fw-ci-05` source marker to the existing checksum verifier;
  verify it names the code path that checks tracked-file coverage and digests.
- [x] 1.2 Confirm the final supported tracked script inventory and regenerate
  `CHECKSUMS.sha256`; verify the diff adds every missing entry and updates each
  changed digest without changing the verifier's file-selection scope.
- [x] 1.3 Run `python3 scripts/gen-checksums.py verify` against the candidate
  tree; verify tracked scripts are represented and stale or extra entries are
  absent. Pinned LF script bytes were temporarily materialized on Windows;
  generation and verification both passed for 160 entries.
- [x] 1.4 Guard the CI verifier invocation against Bash `errexit` and print
  the verifier's original path-specific output before failing; append a scoped
  regression entry preventing an unguarded command-substitution assignment.

## 2. Candidate verification and review

- [x] 2.1 Run the repository's pinned CI workflow on the candidate commit;
  verify the release-checksum step passes at that exact head.
- [x] 2.2 Independently inspect the manifest and CI evidence; verify the
  reported revision matches the candidate and no local-only result is
  represented as hosted verification.

## Workflow follow-up

Archive only after pinned OpenSpec validation, manifest verification, hosted
CI, and independent review. Then run the repository archive procedure and
update the changelog.
