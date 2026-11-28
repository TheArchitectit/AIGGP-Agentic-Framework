# AIGGP future readiness audit

November 25, 2026. Source baseline `1070d3ed917c77773019d2c880d1c911769a2d6f`.

DevGate ships engineering gates, templates, OpenSpec evaluation, and runner
monitoring. The wider AIGGP integration remains a proposal. The project can
start a reference consumer workflow with the current gates, then qualify
protected promotion, a runtime evidence boundary, and monitoring recovery.
Platform or production readiness requires evidence from the intended
deployment and the team that owns it.

The bank assessment maps the 46-slide technical plan to the services that
own each control and the evidence needed to accept it.
[Bank AI tooling platform fit](../openspec/changes/audit-bank-ai-tooling-platform-fit/bank-platform-fit.md).

The DG-02 review covers 156 of 182 rows in detail through batch 013. All 182 remain UNPROVEN. The current catalog and review index track subsequent work alongside the dated baseline below. [OpenSpec index](../openspec/INDEX.md) and [DG-02 review index](../openspec/changes/dg-02-evidence-ledger-reconciliation/README.md).

## Scope and evidence

The review covered the published specs and active changes, current templates
and gate paths, the monitor and fleet-manager boundaries, existing audit
findings, and the upstream PRs that affect the readiness work. The baseline
has 66 canonical specs and 10 active changes. The generated index reports
one `CLOSED`, one `DEFERRED`, 42 `UNPROVEN`, one `OPEN`, and 21 `UNKNOWN`
specs. A source marker, passing fixture, checked task, archived package, and
ledger-proved closure each answer different questions. The status index
records the last of these when the lifecycle rules require it.

The [generated status index](../openspec/INDEX.md) tracks spec state. The
[November 25 audit](../openspec/audits/2026-11-25-aiggp-current-audit.md),
[gap register](../openspec/audits/2026-11-25-aiggp-gap-register.md), and
[integration review](../openspec/audits/2026-11-25-aiggp-integration-gaps.md)
record their own pinned baselines. The
[September roadmap](ROADMAP-2026-09.md) preserves historical decisions.

## Coverage and acceptance

| Requirement | Current evidence | Remaining work and owner |
| --- | --- | --- |
| Reproducible consumer tooling | `.devgate/` is the fixed local tooling path. Consumer workflow templates already bootstrap pinned tooling for several checks. | DevGate maintains a clean reference workflow and exact tool revisions. Consumers keep the tooling out of their tracked source and document their own overlay. [Wiring contract](SUBMODULE_WIRING.md). |
| Eligible hosted CI and optional private runners | Several published templates select hosted Linux. The coherence workflow selects a configured label or `devgate`. Upstream CI uses the project's own runner lane. | Qualify the full reference check set on a clean hosted runner. Qualify other lanes only when adopted, including their dependencies, isolation, evidence parity, and safe handling of missing required inputs. [Delivery evidence proposal](../openspec/changes/qualify-consumer-delivery-evidence/proposal.md). |
| Required check enforcement | On the upstream project, spec validation is a CI gate. The lifecycle and open-item workflows include push-time detection. Applicable release preflight gates cover a separate boundary. | A consumer owner verifies organization and protected deployment rules with failed and missing check controls. The reference evidence states which checks are required and where they enforce. [CI template contract](../openspec/specs/ci-template-contract/spec.md). |
| Promotion and recovery evidence | The source project has release coverage, release preflight, artifact integrity, and CI checks. DG-22 is an active plan for upstream release coverage. | Bind successful required checks, source commit, immutable artifact digest, approval reference, and recovery reference at the consumer's protected promotion boundary. Verify rejection for evidence from another candidate. The consumer owns the signing, authorization, and promotion policy. [DG-22](../openspec/changes/dg22-prepare-approved-main-release/proposal.md). |
| Non-authorizing evaluation evidence | The coherence service produces digest-bound decision and evidence artifacts. Its OAP v2 producer is observe-only. The receiver and action path belong to the consuming system. | Define versioned interoperability and mandatory versus advisory behavior. The trusted consumer validates subject and policy binding, independently authorizes any effects, and proves failure cases using test fixtures. [Consumer evidence proposal](../openspec/changes/define-consumer-evidence-boundary/proposal.md). |
| Identity, tool access, and scoped information | Consumer templates, overlays, and evaluator contracts can test declarations and produce proof. Managed client and endpoint controls have declared enforcement scopes. | Runtime service owners verify trusted principal and scope, data entitlements, target-specific authorization, credential handling, and revocation. Integration claims apply only to the surfaces tested. [Evidence and attestation](../openspec/specs/evidence-and-attestation/spec.md). |
| Safe runtime failure and durable audit | DevGate can test these contracts. Its current monitor and evaluation services have their own specific state and evidence boundaries. | Exercise required policy or evaluator unavailability, timeouts, and ambiguous target results with a simulator. The runtime owner records approvals and outcomes in its own durable audit and verifies its retry and reconciliation rules. [AIGGP integration boundary](../README.md#proposed-integrations-and-roadmap). |
| Recoverable fleet monitoring | The monitor uses instance-local state and documents one hub. Health and alerts base their decisions on existing heartbeat and forge evidence. | DevGate and the operator document a single active writer and exercise a replacement or re-enrollment procedure. Record restoration checks, state coverage, and elapsed recovery. Shared-state replication requires a separate design and proof. [Monitor recovery proposal](../openspec/changes/qualify-monitor-recovery/proposal.md). |
| Optional forge and operator paths | GitLab support has hermetic exercises. The current owner decision makes live instance adoption and related operator checks conditional. | Keep tests runnable against fixtures. The adopter verifies a real instance, live parity, storage, and restore when that path is selected. [GitLab tasks](../openspec/changes/add-gitlab-forge-support/tasks.md). |
| Fleet management and optional product integrations | The fleet-manager boundary includes contracts, planners, and fixture-based tests. Its documentation describes the live integration boundary. | Each supporting product owns its live adapter, execution authority, and acceptance on a pinned version. The initial consumer can use engineering governance without depending on future extensions. [Fleet-manager boundary](../fleet-manager/README.md). |
| Requirement closure and maintenance | The state ledger and generated index distinguish `UNPROVEN` from terminal closure. DG-02 records 182 candidate dispositions and preserves their current proof state. | Keep work in the existing DG-02, DG-04, and DG-06 packages. Add executed evidence and review before changing status. Use the generated index when reporting maturity. [DG-02](../openspec/changes/dg-02-evidence-ledger-reconciliation/tasks.md), [DG-04](../openspec/changes/dg-04-archive-task-reconciliation/tasks.md), [DG-06](../openspec/changes/dg-06-art-evolution-external-proof/tasks.md). |

## Release and roadmap decisions

The upstream release plan has an isolated rehearsal of the actual coverage
check. Its fixtures accepted a matching annotated tag and release notes,
rejected a wrong tag or missing notes, and exercised both the generated-only
exemption and the normal mixed-diff path. Authorized version and candidate
selection, fresh preflight, and release verification remain open. Review
current open-item triage and gate receipts before the next release. At the
audit baseline, OI-005 and OI-006 were open. The recorded November 22 review
date for OI-006 had passed. Resolve or update the recorded dispositions before
the next release preflight.
[DG-22 evidence](../openspec/changes/dg22-prepare-approved-main-release/evidence.md),
[open-item ledger](open-items-ledger.md).

A repository consolidation or shared control plane needs a separately agreed
owner and migration plan. Record source ownership, supported version pins,
history and evidence continuity, a reversible rollout, and cutover
acceptance before advancing that option. Product-specific actors keep the
execution and data authority assigned to their contracts.
[AIGGP disposition](../openspec/changes/AIGGP-DISPOSITION-2026-10-03.md).

## Delivery sequence

1. **Qualify a reference consumer.** Choose an eligible hosted lane, test the
   published bootstrap in a clean repository, and pin the required check set
   and receipts. Demonstrate that a failing or missing required result blocks
   promotion.
2. **Verify the release handoff.** Tie the protected source and successful
   checks to an approved artifact digest and a recovery reference. Reject a
   wrong-digest or wrong-source fixture at the same enforcement point.
3. **Prove one runtime evidence integration.** In a test consumer, call the
   required checker through trusted code. Verify a matching positive result,
   a denied result, unavailability, stale evidence, and an invalid subject.
   Exercise the action boundary only against a simulator under separately
   configured authorization.
4. **Rehearse operations.** Qualify single-writer monitor replacement and
   verify restored state or controlled re-enrollment. Record which state was
   recovered and what needed explicit reconstruction.
5. **Expand supported paths.** Qualify each additional runner class, forge,
   client, or product adapter when an owner takes it on. Report the pinned
   source, actual environment, operational limits, and acceptance evidence.

The first rollout can use hosted delivery and narrowly scoped monitoring.
Platform teams retain responsibility for runtime access, production action
authority, data controls, operating objectives, and deployment acceptance.
The proposed changes define the DevGate contracts and the handoff evidence
those teams can qualify.

## Upstream OpenSpec work

- [Audit AIGGP future readiness](../openspec/changes/audit-aiggp-future-readiness/tasks.md)
  maintains the source baseline and readiness record.
- [Qualify consumer delivery evidence](../openspec/changes/qualify-consumer-delivery-evidence/tasks.md)
  owns the reference workflow, required gate verification, and artifact evidence.
- [Define the consumer evidence boundary](../openspec/changes/define-consumer-evidence-boundary/tasks.md)
  owns compatible evidence handling and receiving-side trust boundaries.
- [Qualify monitor recovery](../openspec/changes/qualify-monitor-recovery/tasks.md)
  owns the single-writer recovery rehearsal and evidence.
