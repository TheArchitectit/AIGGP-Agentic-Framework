# Design

## Context

The fixed `.devgate/` path anchors scanner project-root resolution. `docs/SUBMODULE_WIRING.md` says CI must clone locally because `PREVENT-SUB-001` blocks `.gitmodules`. At the reviewed source snapshot, `drift-scan.yml`, `specs.yml`, and `text-integrity.yml` rely on recursive submodule checkout but have no equivalent pinned bootstrap. Each invokes scripts under `.devgate/`. `spec-coherence.yml` contains a distinct existing bootstrap and remains outside this gap; the bundle-size and file-size workflow files mention `.devgate` only in explanatory comments and do not invoke it.

## Goals / Non-Goals

**Goals:** Reproducible clean consumer jobs, fail-closed setup, preserved root contract.

**Non-Goals:** Change the consumer pin without review, use a submodule, or fetch a moving branch.

## Decisions

For every affected workflow job, require a consumer-owned 40-character commit SHA, provision the tooling at `.devgate/`, detach at that SHA, verify `HEAD` and the workflow's declared required paths, then execute gates. Test each real setup block in a clean consumer with no `.gitmodules` using a local bare fixture repository and its approved commit SHA; do not contact or clone the public upstream in hermetic tests. Also cover malformed/wrong pins, partial checkout, missing files, wrong root, and no green gate marker on failure.

The workflow-specific preflight list must correspond to the actual job commands: the drift workflow's detector and four scan entry points; the specs workflow's strict negative control, traceability and gap scanner; and the text-integrity workflow's charset, encoding, corruption, common helper, and any `.devgate/tests/` controls it executes. Keep its full-history requirement for range corruption checks. Do not replace or weaken its named checks.

DG-08 owns the GitHub reusable workflow path; DG-11 owns GitLab mirror bootstrap. They share the immutable-SHA, ignored in-tree checkout, and fail-closed preflight contract. A common helper is appropriate only if both forge templates can invoke the same tested interface without sharing forge-specific credentials or execution assumptions. A moving ref would simplify setup but make results non-reproducible; `$RUNNER_TEMP` violates root anchoring.

## Risks / Trade-offs

[Clone unavailable] -> fail before scans and report setup failure; [unreviewed pin] -> expose the SHA in the consumer workflow diff and preflight output.
