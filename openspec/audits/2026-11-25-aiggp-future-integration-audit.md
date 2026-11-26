# Future-state integration audit

**Reviewed source** `1070d3ed917c77773019d2c880d1c911769a2d6f`

DevGate provides engineering checks and evidence for an adopting platform. Protected release approval and runtime tool authority remain with their respective owners. The current observe-only pipeline supplies evidence under its supported boundary.

| Boundary | Observed in the reviewed tree | Acceptance work |
|---|---|---|
| Evaluation and required evidence | DevGate supplies versioned OpenSpec, regression and other checks, and evaluator evidence. | Exercise the adopting repository's required check inventory and exception policy. Record outcomes and distinct evidence for permitted local or hosted lanes. |
| Monitor deployment and restore | The canonical monitor spec defines one hub. The implementation writes persistent files using atomic replacement and serializes local writes with a process-local lock. | Verify one supported writer, backup input integrity, restore readback and an independent watchdog. Any coordinated-writer design needs its own state and failure evidence. [DG-23](../changes/dg23-qualify-single-writer-hub-recovery/proposal.md) |
| Artifact promotion | Existing CI records evaluator image identity and provides evidence controls. | Bind an adopting approval and deployment record to verified artifact, source, evaluated revision, applicable policy and selected target. Exercise missing or incompatible evidence. [DG-24](../changes/dg24-bind-adopter-artifact-promotion-evidence/proposal.md) |
| Forge support | Forge parity and template work exist, with operational GitLab activation conditional on adoption. | Prove approved adapters and trust roots where selected. Keep optional forge operation and the adopter's repository and runner policy distinct. See DG-09 and DG-10 in the gap register. |
| Source and lifecycle truth | The existing lifecycle gate requires ordered commit provenance, applicable enforcement and sealed evidence for exercised claims. | Record requirement-level evidence and independent adjudication. DG-02 retains the source inventory and explicit missing proof. |

The downstream access service is the authority for caller, organization, target and operation. Its verified action and audit boundary belongs to the adopting service. Artifact evidence may accompany a deployment approval while preserving those authority boundaries.

- [Monitor architecture](../specs/hub-architecture/spec.md)
- [Monitor service](../../hub/server.py)
- [Monitor registry](../../hub/registry.py)
- [Monitor Quadlet](../../templates/runner-monitor/devgate-hub.container)
- [CI workflow](../../.github/workflows/ci.yml)
- [Gap register](2026-11-25-aiggp-gap-register.md)
- [Verification queue](2026-11-25-aiggp-verification-queue.md)
