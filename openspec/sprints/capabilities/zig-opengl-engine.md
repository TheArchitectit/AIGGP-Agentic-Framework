# zig-opengl-engine sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework tooling maintainer and the consuming game owner**. Bring a disposable project with explicit engine, session or scene inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept framework behavior and any outstanding consumer evidence. |
| S2. Luna writer | Review engine detection and screen/regression inventory in a synthetic Zig project with a declared scope. Bind any real game-specific confirmation to its consumer owner. Start at [engines](../../../engines). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for framework behavior and any outstanding consumer evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`zig-engine-01`](../../specs/zig-opengl-engine/spec.md#requirement-engine-detection-follows-the-manifest-then-project-files) engine detection follows the manifest then project files | Zig project without a manifest |
| [`zig-ui-inv-01`](../../specs/zig-opengl-engine/spec.md#requirement-zig-ui-screens-are-inventoried-under-srcui) Zig UI screens are inventoried under src/ui | handler with no connecting button |
| [`zig-scope-01`](../../specs/zig-opengl-engine/spec.md#requirement-scan-scope-is-declared-by-the-project-manifest) scan scope is declared by the project manifest | vendored cache excluded |
| [`zig-regress-01`](../../specs/zig-opengl-engine/spec.md#requirement-zig--opengl-regression-classes-block-staged-changes) Zig + OpenGL regression classes block staged changes | compile error pattern reintroduced |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-179, DG02-U-180, DG02-U-181, DG02-U-182. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md).

[Published specification](../../specs/zig-opengl-engine/spec.md) and [sprint dispatch](../../SPRINTS.md).
