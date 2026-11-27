# Qualify monitoring, scanner and security evidence gaps

## Why

DG-02 batch 009 found that the queue monitor raises the same stale-run alert with a registered runner list and with an empty list, and the alert does not name a runner label. The implementation uses a global queue threshold. The drift monitor uses a 24-hour period regardless of an individual workflow's schedule. A synthetic result two hours old did not alert when assessed against an hourly schedule and a ten-minute grace window.

The existing security requirement for concurrent duplicate enrollment says the loser receives `already_enrolled`, while the current concurrency test also permits HTTP 401 after token consumption. The `ci-sec-01` historical citation names an absent path; the current template directory has a different name. The reviewed rows lack accepted requirement-specific historical evidence bundles and expected digests.

## What Changes

- Implement and qualify registered-label queue matching, per-repository thresholds and schedule-aware drift recency under the existing monitor contracts.
- Exercise the complete scanner, marker and security scenarios, including distinct concurrency outcomes and the shipped template locations.
- Resolve the enrollment response contract with appropriate security and concurrency tests. Establish valid historical provenance and independently validated evidence before any ledger transition.

## Impact

Hub monitoring and enrollment, scanner and template qualification, fixtures and DG-02 evidence reconciliation. This proposal records follow-up work and makes no implementation or deployment claim.
