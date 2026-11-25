# Design

## Context

The fixed `.devgate/` path anchors scanner project-root resolution. `docs/SUBMODULE_WIRING.md` says CI must clone locally because `PREVENT-SUB-001` blocks `.gitmodules`. AIGGP’s own workflow demonstrates clone then full SHA checkout, but the reusable template relies on submodules.

## Goals / Non-Goals

**Goals:** Reproducible clean consumer jobs, fail-closed setup, preserved root contract.

**Non-Goals:** Change the consumer pin without review, use a submodule, or fetch a moving branch.

## Decisions

Require a consumer-owned 40-character commit SHA, clone into `.devgate/`, detach at that SHA, and verify `HEAD` and required scripts before proceeding. Test the real setup step in a clean consumer with no `.gitmodules` using a local bare fixture repository and its approved commit SHA; do not contact or clone the public upstream in hermetic tests. Also cover wrong pin and partial checkout cases. DG-08 owns the GitHub reusable workflow path; DG-11 owns GitLab mirror bootstrap. They share the immutable-SHA, ignored in-tree checkout, and fail-closed preflight contract. A common helper is appropriate only if both forge templates can invoke the same tested interface without sharing forge-specific credentials or execution assumptions. A moving ref would simplify setup but make results non-reproducible; `$RUNNER_TEMP` violates root anchoring.

## Risks / Trade-offs

[Clone unavailable] → fail before scans and report setup failure; [unreviewed pin] → expose the SHA in the consumer workflow diff and preflight output.
