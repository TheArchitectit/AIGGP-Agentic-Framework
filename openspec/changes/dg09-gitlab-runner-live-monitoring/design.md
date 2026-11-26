# Design

## Context

`hub/monitor.py` constructs a GitHub API polling client. `runner-enroll.sh` accepts GitLab, while `docs/GITLAB-FORGE.md` says no live instance has been contacted and `hub/forge/monitor.py` audits declarations rather than probing. The 2026-11-15 owner decision makes this conditional on adoption.

## Goals / Non-Goals

**Goals:** Keep dormancy explicit and define the monitor behavior that activates with live GitLab adoption.

**Non-Goals:** Start/discover an instance, require live proof for the fixture-supported option, or publish infrastructure details.

## Decisions

Require an operator-owned declaration before GitLab live polling. Dispatch by declared forge; use isolated credentials and explicit check-class coverage. For online state, require both forge-adapter status and heartbeat freshness. A missing, unknown, or errored GitLab observation is unknown/error and alerts; heartbeat alone cannot yield healthy. Preserve GitHub status and its two-heartbeat bound. Test with local stubs first; after adoption, keep live evidence private. Treating the optional fixture-tested capability as a defect before adoption would contradict the owner’s scope decision.

## Risks / Trade-offs

[API differences] → contract-test supported versions and expose unsupported classes; [unintended network access] → require explicit activation and operator-provided endpoint/credentials outside git.
