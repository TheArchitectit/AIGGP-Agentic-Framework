# Bank AI tooling platform fit with AIGGP

November 25, 2026. Assessment for the bank technology team.

The technical plan can use AIGGP/DevGate for OpenSpec, pinned development gates,
CI evidence, and runner monitoring. The plan also requires an access service,
identity and data isolation, authorizations, safe execution, and a recoverable
production environment. Those capabilities must be delivered and accepted at
the layers identified below. No production deployment or entitlement was
verified for this audit.

The planning baseline is the 46-slide *Bank AI Tooling Technical Overview
v2.5* dated November 25. Work IQ located the matching technical and leadership
material. The repository review used AIGGP/DevGate at `1070d3e` and Agent
Guardrails at `c7c4044`. The assessment follows the deck's distinction between
Day 1 requirements and later options. Pricing and vendor terms are estimates
from the deck.

The Agent Guardrails README and its secure cross-product method
describe reusable validation, advisory client wiring, and evidence verified
separately from authorization. Its root Compose example targets local
development. The startup and readiness spec calls for separately controlled
migrations and identifies live dependency recovery and shutdown tests still
to be exercised. Those are deployment qualification gaps for the Guardrails
integration. The older October platform snapshot is historical context.

## Requirement coverage and acceptance

| Plan area and slides | What AIGGP can supply | Evidence needed for the plan |
| --- | --- | --- |
| Stack and client boundaries, slides 1–3 | CI gates, evidence, and tool-integration guidance. A connection is distinct from tool authority. | The bank-owned Day 1 service demonstrates trusted identity, scoped tool discovery, and allow/deny results for each enabled client surface. Document the surfaces where managed controls apply and where tool support is advisory. |
| Microsoft 365 permissions and Purview, slides 4–9 | DevGate can validate configuration-as-code and preserve evidence when the owning team supplies testable inputs. | Confirm entitlements, source permissions, labels, DLP behavior, retention, Audit, eDiscovery, deployment controls, and approved exception and investigation roles in the tenant. Verify each configured surface and retain results by policy version. |
| Existing security services, slides 10–11 | Delivery checks can test adapter configurations and evidence shape. | Enable only supported collectors and scoped evidence queries. Prove source attribution, masking, human review, and accountable response. Keep access-pending services outside Day 1 dependencies. |
| Runtime cluster, networking, admission, and GitOps, slides 12–15 | DevGate can check source and release inputs. Runtime high availability depends on the chosen services and dependencies. | Verify actual host placement, quorum, network policies, VIP failover, TLS, health checks, admission, and pinned GitOps promotion. Validate reserved capacity after a node loss. |
| Tool execution and three-bank isolation, slides 16–17 | Guardrail and DevGate verdicts can be inputs to trusted software. | Server-derived principal and bank context, action-specific authorization and approval, scoped executor credentials, no cross-bank disclosure, and target reconciliation after an uncertain response. Run allowed and denied cases with synthetic identities and actions. |
| Permission-aware retrieval, slide 18 | Independent CI can verify the retrieval service's contract. Native Microsoft 365 grounding remains separately governed. | Enforce current source ACLs and bank scope before retrieval and again on asset access where required. Prove permission revocation, citation integrity, ACL freshness, and controlled handling of stale metadata. |
| Scoped secrets, slide 19 | Delivery gates can detect exposed secrets and check declared policy inputs. | Confirm workload-scoped secret access, dependency recovery, independent bootstrap/key escrow, and redaction. Prove deny behavior for wrong workload and unavailable required secrets. |
| Mandatory guardrails and evidence, slides 20, 32–34 | DevGate supplies software-delivery checks. Agent Guardrails supplies reusable endpoint checks. Advisory clients and the observe-only evidence path have bounded scope. | Required checks run in trusted workflow code or protected CI. Verify immutable policy and subject identity, denied and unavailable-path results, evidence without raw sensitive content, and separate authority before program effects. Keep unqualified optional runtime features disabled. |
| Model routing and future gateway, slides 21–22, 36–40 | CI can test policy fixtures, route eligibility, and safe failure. | Bank model policy governs data classification before quality, cost, or health. Qualify the approved provider, terms, redaction, quotas, and failure behavior. A later gateway requires its own fit, ownership, entitlement, and recovery review. |
| Persistence, observability, failure, and capacity, slides 23–26 | DevGate can provide monitor health and release evidence with the current hub's single-writer model. | Set recovery objectives for each state store, restore independent backups and keys, verify scoped audit access and evidence continuity, and prove safe action handling during dependency or target failure. |
| Software-delivery controls and environments, slides 27–35, 41 | Published consumer CI templates and required source checks are starting points. Upstream self-CI is a separately configured self-hosted lane. | Qualify eligible hosted CI end to end first. Test exact source, required check receipts, authorized approval, immutable image digest, protected promotion, and rollback. Verify the optional self-hosted lane separately where access or cost justifies it. |
| Hardware, storage, and outstanding decisions, slides 42–46 | This repo supplies reusable delivery checks and evidence conventions. | Confirm selected host inventory, support and storage, commercial inputs, role ownership, production acceptance criteria, and recovery independently before activation. |

## Qualification sequence

1. **Delivery pilot.** Use a synthetic consumer application. Run the required
   checks from a clean hosted runner, then demonstrate promotion denial when
   any required result is missing, failing, or bound to a different revision.
   Verify the approved image digest and recovery reference at the GitOps
   boundary.
2. **Runtime read pilot.** Use a single approved tool and synthetic records.
   Test trusted identity, bank and source authorization, revocation, policy
   availability, redacted decisions, and client-specific limitations. The
   bank retains an independent copy of this acceptance evidence.
3. **Controlled action pilot.** Use a simulator before any production
   integration. Verify that a check result cannot authorize an action by
   itself. Test scoped approval, exact target and parameters, credential
   scope, idempotency, reconciliation, and audit for both accepted and
   prevented effects.
4. **Operational acceptance.** Rehearse losing a node, required service, or
   external dependency. Restore data and monitoring state, verify access
   boundaries and evidence continuity, and confirm that no second writer
   or duplicate action was accepted.
5. **Expansion.** Activate each additional client, provider, runner, or
   gateway only when its owner has the required agreements and an equivalent
   acceptance record.

Production launch depends on the validated workflow and runtime controls, not
on every optional phase being ready. The upstream OpenSpec work reduces
engineering gaps. The bank must still own and prove its production controls.
The public readiness work is tracked in [upstream PR #49](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/49).
