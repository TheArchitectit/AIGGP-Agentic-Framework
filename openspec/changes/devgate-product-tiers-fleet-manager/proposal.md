# Proposal: devgate-product-tiers-fleet-manager

## Why

DevGate can decide and prove gate outcomes, but the live fleet is manually
configured, repo-scoped, durable, and concentrated (hub plus several repo-scoped
runners on one host, five monitor spokes on AI01–AI03). New repositories do not
automatically receive an appropriate runner path; fleet growth is a host-by-host
procedure; and the compliance conversation risks splitting core truth from paid
reporting. This package turns the settled product decisions (product tiers,
Fleet Manager control plane, secret subsystem, onboarding, MissionControl
integration) into one sequenced, dependency-locked change.

## What Changes

- Adds a hard dependency lock: nothing in this package starts until
  `devgate-spec-coherence-service` is accepted with a sealed identity, green
  gates, and a docs/qa/ acceptance record (DEP-001).
- Adds the evidence-plane tier contract: tier-independent truth, no paywalled
  remediation facts, append-only enrichment (TIER-001..003).
- Adds the Fleet Manager control plane (desired state separate from execution),
  runtime adapters (Docker/Podman first, ARC later), outbound host agent, and
  ephemeral one-job runner execution with trust classes (FLEET-, RUN-).
- Adds new-repository onboarding, a first-class secret subsystem with numbered
  classes S0–S6, and MissionControl read-model/mediated-command integration
  (ONB-, SEC-, INT-).
- Adds the delivery plan (Sprints 0–11), acceptance suite (A–J), risk register,
  traceability matrix, ADRs, and open owner decisions OD-001..007.

## Impact

- Affected specs: none yet — this package is PROPOSED and BLOCKED; spec deltas
  are materialized only after predecessor acceptance (handoff step 7).
- Affected code: none — DEP-002 forbids scaffolding before unblocking.
- Full normative package follows verbatim below (author: the architect,
  2026-09-18).

---

Full OpenSpec package
Date: 2026-09-18
Working change ID: devgate-product-tiers-fleet-manager
Status: PROPOSED - BLOCKED
Repository: TheArchitectit/AIGGP-Agentic-Framework
Repository snapshot audited for structure: e9ea400c5bf6a6fcacf55264b82c16ebf5f1c7b0
Predecessor package: devgate-spec-coherence-service
Predecessor document: https://docs.google.com/document/d/1uQKm0Wurg-BTsFHKeSLyBT6FGsEaG172V1K2ErnxM4k/edit

## BLOCKING DEPENDENCY - NO WORK STARTS YET

This entire package is blocked by the DevGate Spec Coherence Service OpenSpec
package. No design implementation, scaffolding, directory creation, license
split, portal work, runner deployment, host-agent work, secret integration,
onboarding automation, paid-tier implementation, or MissionControl integration
defined here may start until devgate-spec-coherence-service is finished and
accepted.

"Finished" means all required predecessor tasks and acceptance criteria are
complete, its current normative package identity is sealed, its
decision/evidence contracts are stable, its required gates pass from a clean
clone, and its completion is recorded in docs/qa/ with the exact accepted
commit and evidence. A partial sprint, locally green subset, provisional
schema, or in-flight branch is not completion.

When the predecessor is accepted, this package MUST import its immutable
package identity and MUST NOT copy, rename, fork, or redefine its decision,
canonical identity, evidence manifest, attestation, policy, evaluation-context,
or container-runtime contracts. If the predecessor changes after this package
is approved, dependency review reopens before implementation.

Normative words MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, and MAY
are used in the RFC 2119 sense.

## PACKAGE MAP

| # | Section |
|---|---------|
| 0 | Dependency lock and audit baseline |
| 1 | Proposal and product boundary |
| 2 | Repository and licensing architecture |
| 3 | Evidence-plane tier contract |
| 4 | Fleet Manager control-plane architecture |
| 5 | Runner execution and runtime adapters |
| 6 | New-repository onboarding |
| 7 | Secret management |
| 8 | MissionControl and portfolio integration |
| 9 | Reliability, rollback, and recovery |
| 10 | Security and trust boundaries |
| 11 | Observability and audit evidence |
| 12 | Delivery plan and sprints |
| 13 | Acceptance suite |
| 14 | Risk register |
| 15 | Traceability matrix |
| 16 | ADRs and owner decisions |
| 17 | Claude Code handoff |

## 0. DEPENDENCY LOCK AND AUDIT BASELINE

### 0.1 Blocking dependency

Requirement DEP-001: hard predecessor gate

The change SHALL remain in BLOCKED status until devgate-spec-coherence-service
is accepted under the completion definition above.

Scenario: predecessor is still in flight

- GIVEN one or more predecessor tasks, schemas, gates, or acceptance records
  are incomplete
- WHEN work is proposed under this package
- THEN the work is rejected before code or infrastructure mutation
- AND the rejection names the predecessor package and missing completion
  evidence.

Scenario: predecessor completes

- GIVEN the predecessor has an immutable accepted package identity, green
  required gates, and a docs/qa/ acceptance record
- WHEN this package is unblocked
- THEN that exact predecessor identity is added as an import
- AND a dependency-review record confirms no contract is being redefined here.

Requirement DEP-002: no parallel speculative scaffold

Before unblocking, the repository SHALL NOT add empty enterprise/,
fleet-manager/, host-agent, portal, tier, license, or secret-provider scaffolds
for this package. Documentation review and threat modeling MAY continue, but
code and deploy artifacts SHALL wait.

### 0.2 Repository-grounded baseline

The repository structure was checked at
e9ea400c5bf6a6fcacf55264b82c16ebf5f1c7b0. This supersedes the earlier 9c322ff
planning pin for structure references because the repository moved while this
package was being written. Implementation MUST start with a fresh
full-repository audit and record its own exact head.

Verified current structures relevant to this package include:

- `.github/workflows/drift-scan.yml` and `.github/workflows/hub-health-probe.yml`
- `docs/NEW_REPO_ONBOARDING.md`, `docs/RELEASE_GATE.md`, `docs/WRITE_AUDIT_REVIEW.md`
- `docs/qa/2026-09-13-full-qa.md` and `docs/qa/external-audit-2026-09-14.md`
- `docs/runner-monitor-monitor-hub.md`
- `scripts/runner-enroll.sh`, `scripts/hub-watchdog.sh`, `scripts/detect-host-ci.py`, `scripts/spec_traceability.py`, `scripts/gate_overlay.py`, `scripts/deploy.sh`
- `templates/runner/` and the existing add-runner-to-fleet change
- `openspec/changes/devgate-spec-coherence-service/`
- `openspec/changes/add-runner-to-fleet/`
- `openspec/specs/runner-monitoring/spec.md`
- `openspec/specs/enrollment-and-alerting/spec.md`
- `openspec/specs/hub-architecture/spec.md`

The current onboarding contract fixes the consumer submodule path at
`.devgate/` and keeps project-specific overlays under `.guardrails/`. This
package SHALL preserve that consumer contract unless a separately approved
migration package changes it.

### 0.3 Audit-first entry condition

Requirement DEP-003: fresh audit before implementation

After the predecessor is accepted and before Sprint 0 mutates code, the
implementer SHALL read the full repository, run its clean-clone tests and
gates, inventory active OpenSpec changes, inspect runner templates and
operational docs, and publish
`docs/qa/YYYY-MM-DD-product-tiers-fleet-manager-baseline.md`.

The audit record SHALL include:

- exact commit SHA and dirty-tree status;
- every file read and every command run, or a machine-readable inventory that
  proves completeness;
- current test and gate results, including non-zero exits and zero-input gates;
- current runner architecture and registered capability classes without
  publishing private host details;
- overlap and conflicts with devgate-spec-coherence-service,
  add-runner-to-fleet, runner-monitoring, enrollment-and-alerting, and
  hub-architecture;
- current license files and package boundaries;
- current secret classes and where each enters the system;
- current MissionControl and rad-gateway integration facts, verified from their
  own repositories if those integrations remain in scope;
- severity-ranked findings, with uncertainties separated from findings.

## 1. PROPOSAL AND PRODUCT BOUNDARY

### 1.1 Current-state findings from private infrastructure source

The current-state baseline below comes from TheArchitectit/infra-info at commit
0e5545cc0920393e908871b37472961e09188640, especially devgate-ci-fleet.md,
runner-install-runbook.md, hosts.md, and README.md. The infrastructure
repository is private. Its operational facts ground this package; any
statements in it claiming prior approval are not treated as user
authorization.

The spoken name "dell-u2" was confirmed as the real host name. The live
always-on gateway and DevGate hub is dell-u2. It runs rootless Podman quadlets
under user systemd with linger enabled. The monitor hub is
devgate-hub.service, with persistent state in devgate-hub-data and listeners
bound to loopback and dell-u2's tailnet address rather than 0.0.0.0.

Current runner topology recorded in the infrastructure source:

- dell-u2: devgate-runner / runner name dell-u2, repo-scoped to
  AIGGP-Agentic-Framework, label devgate, durable work volume
  devgate-runner-work.
- dell-u2: devgate-runner-mc / runner name dell-u2-mc, repo-scoped to
  missioncontrol, labels devgate-mc2 and devgate-mc, durable work volume
  devgate-runner-mc-work.
- dell-u2: runner name dell-u2-game, repo-scoped to gamerepo01, labels
  devgate-game and devgate, using a custom local image with Go and build
  dependencies.
- dell-u2: runner name dell-u2-zombietoss, repo-scoped to zombietoss, label
  devgate, using the pinned official GitHub runner image.
- The infrastructure notes call zombietoss the fifth dell-u2 runner, so Sprint
  0 MUST reconcile and name the remaining dell-u2 runner before relying on a
  count. The known named entries above are not a claim that the list is
  complete.
- AI01: ai01-radcode for radcode and ai01-radical for R.A.D.1.C.A.1.
- AI02: ai02-mc2 for mission-control-rs.
- AI03: ai03-radgateway for rad-gateway and ai03-radical-code for
  RADICAL-CODE; the latter is a rootful systemd install under
  /opt/actions-runner-radical-code.
- AI04: no registered runner in the recorded state.

Six runners were recorded as monitor spokes on the dell-u2 hub: the five
AI01-AI03 runners plus dell-u2's DevGate framework runner. The additional
dell-u2-mc and dell-u2-game runners were explicitly not enrolled as spokes in
the same record; Sprint 0 MUST verify whether that remains true and whether
dell-u2-zombietoss is now enrolled. Monitoring polls each registered
repository every 60 seconds for runner/API status, 300-second heartbeats,
queue age, watched-branch check conclusions, and drift-scan recency.

The existing execution model is one durable Podman container and durable
credential/work volume per repository, with distinct labels and repo scope.
Registration identity survives restart. The stock runner-enroll.sh assumes one
runner per host; AI01 and AI03 needed per-runner heartbeat env files and
per-runner systemd unit names to avoid clobbering tokens. The proposed
ephemeral one-job pools are therefore a migration, not a description of
today's state.

Current secret handling is on-box chmod-600 drop-ins and env files. The
dell-u2 hub record identifies an over-scoped GitHub CLI token, one armed hub
enrollment token, per-runner registration-token drop-ins, and per-spoke
heartbeat env files. These are findings to replace safely, not secret values
to copy. Registration tokens can be burned by crash loops, and hub restarts
can re-arm tokens from the drop-in.

The practical reliability problem is not "exactly one runner." It is manual
per-repository provisioning, durable post-job state, repo/label mismatch risk,
incomplete spoke coverage, multi-runner unit-name exceptions, and
concentration of the hub plus several runners on dell-u2. The target
architecture MUST preserve current working capacity while it moves to central
desired state and ephemeral execution.

Source links, access-controlled:

- https://github.com/TheArchitectit/infra-info/blob/0e5545cc0920393e908871b37472961e09188640/devgate-ci-fleet.md
- https://github.com/TheArchitectit/infra-info/blob/0e5545cc0920393e908871b37472961e09188640/runner-install-runbook.md
- https://github.com/TheArchitectit/infra-info/blob/0e5545cc0920393e908871b37472961e09188640/hosts.md

### 1.2 Problem

DevGate can decide and prove gate outcomes, but today the live fleet is larger
than the speech-to-text premise suggested, but it remains manually configured,
repo-scoped, durable, and concentrated. The current hub and several
repo-scoped runners are on dell-u2, while five additional runners on AI01-AI03
report as monitor spokes. New repositories do not automatically receive an
appropriate runner path. Fleet growth is a host-by-host procedure instead of a
desired-state system. The compliance conversation also risks splitting core
truth from paid reporting, which would weaken trust and create contract drift.

This change turns the settled product decisions into one sequenced package.
DevGate remains the gate and evidence authority. Fleet Manager supplies
execution capacity. MissionControl presents and coordinates. rad-gateway
remains outside the trust path while its gates are red. Compliance is a paid
use of the evidence plane, not a second truth engine.

### 1.3 Desired outcomes

1. Every DevGate gate emits the same trustworthy decision and minimum evidence
   regardless of paid tier.
2. Paid features add aggregation, retention, dashboards, control mappings,
   approvals, audit exports, and support without changing gate truth.
3. DevGate stays in one repository, with a directory-level commercial boundary
   and contract tests.
4. Fleet Manager expresses desired state separately from the runner fleet that
   executes it.
5. Phase 1 supports Docker and Podman warm pools, a second physical host, and
   tested dell-u2 drain/failover.
6. A repository can enroll through one portal/API workflow and receive policy,
   labels, runner capacity, and health monitoring without hand-editing host
   state.
7. Kubernetes support uses GitHub Actions Runner Controller as a later adapter
   rather than recreating a Kubernetes autoscaler.
8. Runners are treated as arbitrary-code boundaries with ephemeral job
   execution, trust-class isolation, short-lived enrollment, signed
   configuration, and separate secret classes.
9. Every control-plane mutation and runner lifecycle transition produces
   auditable evidence.
10. Rollback is designed before scale-out.

### 1.4 Non-goals

This package does not:

- replace or fork the predecessor's canonical decision or evidence contracts;
- create a standalone compliance product or compliance gate engine;
- make MissionControl a source of truth;
- put rad-gateway in the release, secret, evidence, or runner trust path while
  it is red;
- promise multi-tenant SaaS, public internet exposure, billing, or customer
  identity federation in Phase 1;
- build a new Kubernetes operator or compete with Actions Runner Controller;
- support arbitrary host shells as a first-class runtime adapter;
- store long-lived repository or cloud credentials inside runner images,
  repository files, signed configuration, logs, or evidence bundles;
- extract a second repository now.

### 1.5 Portfolio responsibility matrix

DevGate core:

- owns gate execution contracts, canonical decisions, minimum evidence, policy
  evaluation, and pass/fail/error truth;
- is available without a paid entitlement for those core truth functions.

DevGate commercial modules:

- own paid aggregation, extended retention, compliance control mappings,
  approval workflows, audit exports, enterprise dashboards, enterprise policy
  administration, and support integration;
- consume core contracts and MUST NOT alter them.

Fleet Manager:

- owns desired runner state, runtime adapter orchestration, host-agent
  coordination, repository-to-pool assignment, capacity, draining, replacement,
  and lifecycle evidence;
- MUST NOT decide whether a product gate passed.

Runner fleet:

- executes jobs assigned under Fleet Manager policy;
- is replaceable capacity, not the control plane or evidence authority.

MissionControl:

- reads supported APIs and presents status, trends, requests, and operator
  actions;
- MAY initiate an authorized command through Fleet Manager or DevGate APIs;
- MUST NOT invent, rewrite, or directly persist authoritative gate, evidence,
  runner, or secret state.

rad-gateway:

- stays outside every trust path while red;
- MAY be observed as an external subject, but SHALL NOT proxy secrets,
  attestations, approvals, runner commands, or promotion decisions.

## 2. REPOSITORY AND LICENSING ARCHITECTURE

### 2.1 One-repository decision

Requirement REPO-001: single repository

All work in this package SHALL land in
TheArchitectit/AIGGP-Agentic-Framework. No fleet-manager, compliance,
evidence, or enterprise repository SHALL be created by this package.

Reason: one repository keeps contract changes atomic, avoids duplicate CI and
release choreography, and makes the extraction boundary prove itself before
organizational separation.

### 2.2 Directory-level license boundary

Requirement REPO-002: visible open/commercial split

The root and existing DevGate core remain under the repository's approved
open-core license. Commercial code SHALL live only under one top-level
boundary selected during Sprint 0, with `enterprise/` preferred unless the
audit proves `fleet-manager/` is the clearer single commercial root.

Proposed structure:

```
/
  core contracts and existing DevGate open source
  openspec/
  scripts/
  templates/
  docs/
  enterprise/                      <- LICENSE
    README.md
    evidence-plane/
    fleet-manager/
      api/
      domain/
      adapters/
        docker/
        podman/
        arc/
      host-agent/
    portal/
    compliance/
    support/
    contracts/
      v1/
    tests/
      contract/
```

The final name MUST be chosen once. Commercial code MUST NOT be scattered
across the open root. The commercial boundary SHALL contain a license notice,
contribution rules, dependency rules, and a machine-readable manifest of
commercial paths.

Scenario: unlicensed build

- WHEN the repository builds without a valid commercial entitlement
- THEN DevGate core gates and minimum evidence remain fully functional
- AND commercial services do not start
- AND the absence of an entitlement cannot turn a core failure into pass,
  suppress required evidence, or reduce failure visibility.

Scenario: directory leakage

- WHEN CI scans changed files and dependency edges
- THEN open-core packages MUST NOT import implementation code from the
  commercial directory
- AND a violation fails the repository boundary gate.

### 2.3 Contract boundary and extraction readiness

Requirement REPO-003: contracts cross the boundary

Every call between open core and commercial modules SHALL use versioned
contracts under `contracts/v1/` or the exact predecessor-owned contract
locations. Cross-boundary imports of internal classes, database models, or
non-versioned schemas are forbidden.

Requirement REPO-004: contract tests

Contract tests SHALL run both directions:

- core provider against commercial consumer fixtures;
- commercial provider against core consumer fixtures;
- previous supported contract version against current implementation;
- entitlement absent, expired, malformed, and revoked;
- commercial module unavailable while core gates continue.

Requirement REPO-005: extraction rehearsal

At each major release, CI SHALL build and test the commercial module using
only declared contract packages and published build inputs. At least once
before general availability, a temporary extraction rehearsal SHALL copy the
module into an isolated workspace and prove there are no hidden
repository-relative imports. This rehearsal is evidence, not authorization to
create a second repository.

### 2.4 License enforcement safety

Entitlement checks SHALL guard paid services, storage duration, dashboard
access, exports, mappings, approvals, and support workflows. Entitlement
checks SHALL NOT sit inside the canonical core decision path. A licensing
outage SHALL degrade paid views or paid mutations explicitly; it SHALL NOT
change a gate result.

## 3. EVIDENCE-PLANE TIER CONTRACT

### 3.1 Product decision

Compliance remains a DevGate capability built on the evidence plane. It is not
a standalone truth engine. The moat remains the evidence plane: exact subject,
exact package, exact policy, exact evaluator, exact result, and verifiable
evidence linked by stable identity.

### 3.2 Tier matrix

Core, free:

- canonical pass/fail/error decision;
- minimum evidence needed to prove each finding;
- local or configured evidence manifest;
- stable exit codes and machine-readable results;
- deterministic replay inputs allowed by predecessor policy;
- basic current-run human-readable report;
- no false green when paid services are absent.

Team or paid operations:

- multi-repository aggregation;
- longer evidence retention;
- fleet health and queue dashboards;
- trend views and policy rollout views;
- role-aware approval queues;
- scheduled exports and operational support.

Compliance or enterprise:

- control-library mappings;
- evidence coverage reports by control and scope;
- approval separation-of-duties;
- signed audit packages and export manifests;
- extended retention and legal-hold integrations;
- SSO/RBAC integrations when separately approved;
- support, policy packs, and deployment assistance.

### 3.3 Truth invariants

Requirement TIER-001: truth is tier-independent

For identical immutable inputs and predecessor-defined evaluation context,
core decision bytes and minimum evidence identity SHALL be identical
regardless of entitlement, dashboard availability, retention tier, approval
UI, support plan, or MissionControl connection.

Scenario: entitlement expires during a run

- WHEN a commercial entitlement expires after evaluation begins
- THEN the core evaluation completes under its pinned evaluation context
- AND the canonical result is not recomputed or rewritten
- AND paid post-processing either completes under a recorded grace rule or
  fails explicitly outside the core decision.

Requirement TIER-002: no paywalled remediation facts

The identity of the failed gate, failed requirement, finding key, evidence
digest, and minimum actionable failure reason SHALL remain available in core.
Paid tiers MAY add fleet history, control mapping, cross-repository impact,
and support guidance.

Requirement TIER-003: append-only enrichment

Commercial aggregation SHALL reference canonical core objects by digest and
add detached enrichment. It SHALL NOT mutate or replace signed core objects.

### 3.4 Compliance mapping

Control mappings SHALL be versioned data that point from a control-library
release to DevGate requirement IDs, assertion IDs, evidence types, and
coverage status. A mapping MUST distinguish proved, partially proved,
operator-attested, and not covered. A dashboard SHALL NOT label a control
compliant solely because a mapped gate passed.

Scenario: incomplete control evidence

- GIVEN a control requires technical evidence and a human approval
- WHEN the technical gate passes but approval is absent
- THEN the control view reports partial coverage, not compliant.

### 3.5 Approvals and exports

Approval records SHALL be detached, signed or otherwise strongly
authenticated, immutable after submission, and bound to exact digests, scope,
actor, role, time, reason, and expiry. Audit exports SHALL carry a manifest,
object digests, export time, filter scope, schema versions, and missing-object
list. Export generation SHALL fail closed if it cannot distinguish complete
from partial evidence.

## 4. FLEET MANAGER CONTROL-PLANE ARCHITECTURE

### 4.1 Separation of manager and fleet

Requirement FLEET-001: desired state is separate from execution

Fleet Manager SHALL store and reconcile desired state. Host agents and runtime
adapters SHALL create, drain, replace, and remove runner instances. A runner
process or host SHALL NOT become the authoritative desired-state database.

### 4.2 Proposed components

Fleet Manager API:

- authenticated repository, pool, host, policy, capacity, drain, and status
  endpoints;
- idempotency keys on mutations;
- optimistic concurrency on desired-state revisions;
- append-only audit events.

Desired-state store:

- repositories and their trust class;
- pools, labels, runtime type, image digest, min/max/warm capacity;
- host capabilities and allowed pools;
- rollout version, assignment, drain and maintenance state;
- references to secrets, never secret values.

Reconciler:

- computes desired versus observed state;
- emits bounded plans;
- applies rate limits and disruption budgets;
- records every action and outcome;
- never runs arbitrary repository-provided control commands.

Outbound host agent:

- initiates a mutually authenticated outbound connection or polling exchange
  to Fleet Manager;
- verifies signed desired-state envelopes;
- calls only installed, allowlisted runtime adapters;
- returns observations and signed action receipts;
- has no general-purpose remote shell API.

Runtime adapters:

- implement a stable lifecycle interface for Docker, Podman, and later ARC;
- expose capabilities, not runtime-specific objects, to the domain layer.

Portal:

- renders desired and observed state;
- provides reviewable onboarding, drain, failover, and rollback actions;
- calls the same authenticated API used by automation;
- holds no signing or repository credentials in browser storage.

### 4.3 Desired-state model

Each runner pool SHALL declare:

- pool_id and revision;
- trust_class;
- allowed repositories or runner group;
- required labels;
- runtime adapter;
- pinned runner image digest;
- architecture and host constraints;
- ephemeral mode;
- warm_min, warm_max, scale ceiling, and idle timeout;
- job timeout and cleanup timeout;
- network and filesystem profile;
- secret profile reference;
- update channel and rollback image;
- maintenance and disruption budget;
- owner and escalation route.

### 4.4 Reconciliation safety

Requirement FLEET-002: plan before apply

Every multi-runner mutation SHALL produce a deterministic plan showing
creates, drains, replacements, deletions, and capacity impact. Destructive
changes require an authorized apply against the same desired-state revision.

Requirement FLEET-003: bounded convergence

Reconcilers SHALL cap concurrent drains, replacements, and host mutations.
Loss of Fleet Manager SHALL leave running jobs untouched, stop unsafe new
mutations, and preserve enough local state for controlled recovery.

Requirement FLEET-004: no inbound home-network dependency

Phase 1 host agents SHALL initiate outbound communication. Fleet Manager SHALL
NOT require a public inbound path to home-lab hosts.

## 5. RUNNER EXECUTION AND RUNTIME ADAPTERS

### 5.1 Phase 1 architecture

Phase 1 supports Docker and Podman warm pools on dell-u2 plus at least one
independently powered second physical host. The same runner image, entrypoint
contract, cleanup contract, and job receipt schema SHOULD apply to both
runtimes. Runtime differences SHALL be isolated inside adapters.

### 5.2 Adapter contract

Each adapter SHALL implement:

- discover_capabilities;
- validate_host;
- ensure_image by immutable digest;
- create_runner from one-time registration material;
- observe_runner;
- mark_drain;
- cancel_or_timeout only under explicit policy;
- destroy_runner;
- prove_cleanup;
- report resource and action receipts;
- rollback adapter configuration.

Adapter calls SHALL be idempotent or carry a durable operation key. Adapters
SHALL return typed errors: invalid desired state, unavailable host,
registration failure, runtime failure, cleanup failure, capacity exhaustion,
policy denial, and unknown state.

### 5.3 Ephemeral execution

Requirement RUN-001: one job per runner instance

Phase 1 job runners SHALL be ephemeral: one registered runner instance accepts
at most one job and is destroyed after completion, timeout, cancellation, or
uncertain disconnect. Warm pools MAY keep pre-pulled images or stopped clean
containers, but MUST NOT keep a previously used job filesystem.

Requirement RUN-002: clean-by-proof

A replacement instance SHALL NOT join capacity until the previous instance's
cleanup is proven or its resources are quarantined. Cleanup evidence SHALL
include instance identity, image digest, job identity if known, volume/network
disposal result, and timestamps.

### 5.4 Trust classes

At minimum define:

- trusted-owned: protected branches and repositories fully controlled by the
  owner;
- owned-untrusted-change: pull requests or change contexts that can execute
  modified workflow code;
- external-untrusted: forks or outside contributors;
- privileged-release: deployments or signing operations.

Pools SHALL NOT mix privileged-release with untrusted classes. Repositories
and workflows SHALL target runner groups or equivalent pool assignments, not
self-selected labels alone. A repository cannot raise its own trust class
through committed configuration.

### 5.5 dell-u2 drain and failover

Requirement RUN-003: dell-u2 is drainable

dell-u2 SHALL be represented as a host, not as the fleet. Operators SHALL be
able to prevent new assignments, allow current jobs to finish, verify zero
active work, and remove dell-u2 without losing fleet service.

Requirement RUN-004: second-host proof

Before Phase 1 acceptance, at least one independently powered physical host
other than dell-u2 SHALL carry eligible warm capacity for each required
non-privileged Phase 1 pool.

Failover exercise:

1. Confirm both hosts healthy and eligible.
2. Queue a controlled test workload.
3. Drain dell-u2 before assignment and prove the second host takes it.
4. Start a controlled workload on dell-u2, request drain, and prove no new
   dell-u2 assignment.
5. Simulate dell-u2 loss and prove detection, capacity response, and queue
   behavior.
6. Restore dell-u2 using signed desired state, not hand-edited drift.
7. Save receipts and GitHub run evidence under docs/qa/.

### 5.6 Kubernetes later through ARC

ARC SHALL be a later runtime adapter. Fleet Manager MAY declare a
Kubernetes-backed pool, but ARC owns Kubernetes runner scale-set mechanics.
The adapter SHALL translate Fleet Manager policy into supported ARC
configuration and read ARC observations. It SHALL NOT fork ARC, recreate its
listener protocol, or directly manage individual Kubernetes runner pods
outside supported interfaces.

No ARC implementation starts until Docker/Podman acceptance and dell-u2
failover pass.

## 6. NEW-REPOSITORY ONBOARDING

### 6.1 Goal

A repository should connect once and receive a reviewable DevGate and fleet
configuration. Current docs/NEW_REPO_ONBOARDING.md remains the source for
`.devgate/` and `.guardrails/` layout. The existing add-runner-to-fleet
walkthrough remains an operator procedure, but this package adds automation
above it.

### 6.2 Onboarding flow

1. Operator authenticates and selects an accessible repository.
2. Fleet Manager reads repository metadata and current DevGate state.
3. It produces a plan: `.devgate/` status, `.guardrails/` overlay, workflow
   templates, required runner group/pool, trust class, labels, secrets
   references, branch policies, monitoring, and predecessor contract
   compatibility.
4. Operator reviews the plan.
5. An authorized apply creates platform-side runner group/pool assignments and
   proposes repository changes through the approved repository workflow.
6. A verification run proves the workflow reached an eligible runner and
   produced a non-vacuous DevGate result.
7. Onboarding records exact commit, workflow run, runner class, policy
   revision, evidence digests, and rollback instructions.

Requirement ONB-001: no token in repository

Repository onboarding SHALL store references and platform installation
identities, not registration tokens, personal access tokens, app private
keys, cloud credentials, or host credentials.

Requirement ONB-002: automatic does not mean silent

Every onboarding apply SHALL show the repository, default branch, trust class,
pool, workflows, required permissions, and mutations. A partial apply SHALL
report exact completed and remaining steps and be safe to resume.

Requirement ONB-003: prove job pickup

Onboarding is incomplete until a controlled workflow targets the intended
pool, is picked up, runs the required non-vacuous gates, and leaves a
verifiable record.

### 6.3 Configuration pull

Repositories MAY pull a signed, non-secret configuration bundle from Fleet
Manager by repository identity and revision. The bundle SHALL contain policy
references, pool assignment, workflow compatibility, and public keys or trust
roots. It SHALL NOT contain runnable shell supplied by the repository, secret
values, or an authority to change host-agent behavior.

## 7. SECRET MANAGEMENT

### 7.1 Numbered design objective

Secret management is a first-class subsystem. It is not a final
environment-variable step. The design separates control-plane identity, host
enrollment, GitHub registration, job/runtime credentials, DevGate evaluation
secrets, release credentials, signing keys, evidence-store credentials, and
commercial entitlement data.

### 7.2 Secret classes

S0 public configuration:

- endpoints, public verification keys, schema versions, image digests.

S1 bootstrap and enrollment:

- one-time host enrollment tokens;
- one-time or short-lived runner registration material.

S2 service identity:

- Fleet Manager service credentials;
- host-agent mTLS private keys or workload identity;
- GitHub App installation credentials.

S3 job-scoped credentials:

- repository checkout token;
- package registry credential;
- test service credential;
- expires with the job and is scoped to that job.

S4 privileged release credentials:

- production deployment, signing, publishing, or cloud mutation authority;
- only privileged-release pools may receive them.

S5 evidence and attestation:

- attestation signing keys;
- evidence-store write/read credentials;
- control mapping and approval verification identities.

S6 commercial operations:

- entitlement verification material;
- support connectors and enterprise identity-provider credentials.

### 7.3 Secret invariants

Requirement SEC-001: references in desired state

Desired state, signed config, repository config, logs, plans, evidence
manifests, and receipts SHALL contain opaque secret references and metadata,
never secret values.

Requirement SEC-002: least scope and short life

Runner registration and job credentials SHALL be minted just in time with the
narrowest repository, operation, audience, and lifetime supported. A runner
that has not received a job SHALL not possess job credentials.

Requirement SEC-003: runner cannot read control-plane roots

Runner instances SHALL never receive Fleet Manager database credentials,
host-agent identity keys, entitlement signing keys, attestation root keys, or
credentials for other trust classes.

Requirement SEC-004: no secret in command arguments

Provisioning and adapters SHALL pass sensitive values through a protected file
descriptor, tmpfs file with restrictive permissions, or supported secret
mount. They SHALL NOT put secrets in command-line arguments, process titles,
committed env files, images, or shell history.

Requirement SEC-005: redact and detect

Logs and evidence emitters SHALL use structured redaction before persistence.
CI SHALL include seeded canary fixtures to prove common token and key forms
are redacted. Redaction failure is ERROR for the affected operation.

Requirement SEC-006: rotation and revocation

Every non-public secret class SHALL define owner, issuer, scope, TTL or
rotation period, storage provider, consumers, revocation procedure, and
incident response. Host removal, repository removal, pool trust change, and
operator removal SHALL trigger bounded revocation workflows.

### 7.4 Secret-provider interface

Define a provider-neutral interface:

- resolve_reference(metadata, workload_identity);
- mint_lease(scope, audience, ttl);
- inject_lease(target, delivery_method);
- renew_lease where explicitly permitted;
- revoke_lease;
- audit_access without logging value;
- health and capability discovery.

Phase 1 MAY support one provider selected after audit. Provider choice remains
an owner decision if the repository and home-lab baseline do not make it
clear. The contract MUST avoid binding domain logic to a single vendor.

### 7.5 GitHub authentication

Prefer a GitHub App or supported platform identity with installation-scoped
permissions over broad personal tokens. Runner registration material SHALL be
requested just in time and consumed once. Runner groups SHALL restrict which
repositories can use each pool. Workflow code from untrusted changes SHALL not
gain platform administration credentials.

### 7.6 DevGate evaluation secrets

The predecessor's container-runtime and evaluation-context contracts control
what a DevGate evaluator may receive. This package SHALL not widen that
channel. Evaluators SHOULD receive no secrets by default. When an assertion
requires one, the policy SHALL declare its secret class, purpose, scope,
network destination, result redaction, and whether the assertion is allowed to
authorize promotion.

### 7.7 Signing keys

Attestation and signed desired-state keys SHALL use separate key hierarchies
and audiences. Compromise of a host-agent key SHALL not authorize DevGate
attestations. Compromise of an attestation signer SHALL not authorize fleet
mutations. Root material SHOULD remain outside general application storage and
routine runner hosts.

### 7.8 Secret failure behavior

Unknown reference: reject before scheduling.

Mint failure: no runner assignment; explicit retryable or terminal state.

Injection failure: destroy/quarantine runner; no job start.

Expiry during job: follow declared job policy; never silently substitute
broader credentials.

Revocation: stop new use immediately and drain or terminate affected instances
according to trust class.

Provider outage: preserve running jobs without adding new secret-bearing work
unless policy explicitly allows cached leases.

## 8. MISSIONCONTROL AND PORTFOLIO INTEGRATION

Requirement INT-001: read model only

MissionControl SHALL read DevGate and Fleet Manager APIs and display source
identity, revision, and freshness. It SHALL not query their databases directly
or become the only copy of state.

Requirement INT-002: command mediation

Any MissionControl action SHALL create an authenticated command against the
owning API. The owning service validates authority, preconditions,
idempotency, and desired-state revision and returns an authoritative receipt.

Requirement INT-003: rad-gateway quarantine

No architecture diagram, deployment, or implementation in this package SHALL
place rad-gateway between repositories/runners and DevGate, Fleet Manager,
secret provider, evidence store, or MissionControl. Re-entry requires a
separate green-gate acceptance decision.

### 8.1 Dashboard views

Core operational views MAY show current job/gate status from authoritative
APIs. Paid views MAY add cross-repository trends, retention, control mappings,
approvals, and export workflows. Every view SHALL state source, last
observation time, and whether data is current, delayed, partial, or
unavailable.

## 9. RELIABILITY, ROLLBACK, AND RECOVERY

### 9.1 Rollback domains

Each release SHALL independently roll back:

- Fleet Manager application;
- desired-state schema migration;
- host agent;
- Docker adapter;
- Podman adapter;
- runner image;
- commercial evidence/dashboard services;
- control mappings;
- MissionControl client integration.

A rollback SHALL not require reverting canonical DevGate evidence. Schema
migrations SHALL document forward and backward compatibility and take a
verified backup before destructive changes.

### 9.2 Safe modes

Control plane unavailable:

- running jobs continue if safe;
- no uncontrolled scale-up;
- host agents retain last verified desired state for bounded observation only;
- destructive reconciliation stops.

GitHub unavailable:

- stop new registration attempts after bounded retries;
- retain no unused registration secret beyond TTL;
- show queue and status as unknown, not healthy.

Secret provider unavailable:

- do not schedule secret-bearing work;
- do not fall back to a broader static credential.

Evidence aggregation unavailable:

- core local gate decision remains intact;
- paid aggregation reports delayed/unavailable;
- policy decides whether remote durability is required for promotion, using
  predecessor contracts.

### 9.3 Backup and restore

Desired state and audit events SHALL have documented backup, integrity checks,
restore tests, and retention. Restore SHALL not restore expired tokens as
usable credentials. A recovery exercise SHALL rebuild Fleet Manager,
re-establish host identities, reconcile without duplicate runners, and
preserve audit lineage.

## 10. SECURITY AND TRUST BOUNDARIES

### 10.1 Runner threat model

A runner executes repository-controlled code and MUST be treated as
compromised after a job. Container isolation reduces operational spread but is
not assumed to be a complete hostile-code boundary. Host access, Docker/Podman
sockets, privileged mode, host mounts, network reach, and sibling workloads
SHALL be minimized per trust class.

### 10.2 Required controls

- no privileged containers by default;
- no broad host filesystem mounts;
- no reusable Docker socket in untrusted pools;
- read-only root filesystem where compatible;
- isolated per-job work and temp volumes;
- bounded CPU, memory, disk, process count, and duration;
- default-deny or narrowly allowlisted egress for privileged pools where
  practical;
- pinned images by digest and verified provenance;
- vulnerability and dependency scanning of images;
- separate hosts or stronger boundaries for privileged-release if the audit
  finds containers insufficient;
- host-agent allowlist of adapters and operations;
- mutually authenticated control traffic;
- replay protection on desired-state envelopes and action requests;
- signed configuration with revision, audience, expiry, and nonce or monotonic
  sequence;
- append-only security events.

### 10.3 Authorization model

Separate permissions for view, plan, apply, drain, emergency stop, host
enroll, repository onboard, secret policy administer, control mapping
administer, approval submit, export, and support access. No single paid
dashboard permission implies fleet mutation or secret access.

### 10.4 Supply chain

The runner image, host agent, Fleet Manager, adapters, and commercial modules
SHALL have reproducible or attestable build provenance, dependency
inventories, signed release artifacts where supported, and pinned deployment
digests. Update rollout SHALL canary on non-privileged capacity, verify health
and a controlled job, then expand within a disruption budget.

## 11. OBSERVABILITY AND AUDIT EVIDENCE

### 11.1 Required events

Record:

- desired-state proposal, approval, revision, and apply;
- repository onboarding plan and result;
- host enrollment, key rotation, revoke, and last-seen;
- runner create, register, eligible, assigned, busy, completed, cleanup,
  quarantine, destroy;
- drain, failover, rollback, and emergency stop;
- adapter call and typed outcome;
- secret lease metadata and access outcome without value;
- entitlement decision outside core truth;
- evidence aggregation and export completion/partial failure;
- MissionControl command and authoritative receipt.

### 11.2 Metrics and alerts

At minimum:

- eligible, idle, busy, draining, offline, quarantined runners by pool/host;
- queued job age by required pool;
- warm capacity versus target;
- reconciliation lag and failures;
- registration and cleanup failures;
- secret mint/injection failures;
- dell-u2 and second-host capacity health;
- gate pass/fail/error counts by immutable contract version;
- delayed aggregation and missing evidence objects;
- control mapping coverage states;
- stale host-agent config and signature failures.

Existing runner-monitoring requirements for online detection, queue-drain
detection, gate-result tracking, and drift-scan recency remain applicable.
This package SHALL extend rather than fork them.

## 12. DELIVERY PLAN AND SPRINTS

All sprints are blocked until the predecessor acceptance gate passes.

Sprint 0: audit, import, and boundary freeze

- run the full audit in DEP-003;
- import exact predecessor identity;
- reconcile overlaps with active runner and monitor specs;
- choose `enterprise/` versus `fleet-manager/` commercial root;
- inventory licenses and obtain an owner-approved commercial license text;
- freeze v1 cross-boundary contracts;
- produce threat model and secret inventory;
- record owner decisions and baseline under docs/qa/.

Exit: audit accepted, no unresolved P0/P1 architecture conflict, predecessor
imported, contract and license boundary approved.

Sprint 1: repository and contract gates

- create the selected commercial boundary and license manifest;
- add dependency-direction and changed-path license gates;
- add versioned shared contracts and fixtures;
- build entitlement isolation tests;
- add extraction rehearsal in CI;
- prove core gates run with commercial code absent.

Exit: boundary tests green from clean clone and core truth invariant proven.

Sprint 2: Fleet Manager domain and desired state

- implement repository, host, pool, assignment, capacity, drain, and rollout
  models;
- implement plan/apply with revisions and idempotency;
- implement audit events;
- add API authentication and authorization skeleton;
- create deterministic reconciliation fixtures.

Exit: domain and plan/apply contract tests green; no runtime mutation yet.

Sprint 3: host agent and signed configuration

- implement outbound host-agent channel;
- implement enrollment, identity rotation, signature verification, replay
  protection, operation allowlist, and receipts;
- preserve compatibility or migration from scripts/runner-enroll.sh and
  existing monitor-hub duties;
- add failure and revocation fixtures.

Exit: two test hosts reconcile signed no-op desired state;
compromised/replayed commands fail closed.

Sprint 4: Docker and Podman ephemeral adapters

- implement the stable adapter contract;
- build pinned ephemeral runner image and warm-pool behavior;
- implement one-job lifecycle, cleanup proof, quarantine, resource limits, and
  typed errors;
- exercise both adapters against controlled repositories.

Exit: controlled jobs complete on Docker and Podman with destroyed job
environments and complete receipts.

Sprint 5: secret subsystem

- select and implement one provider adapter;
- add just-in-time registration and job credentials;
- add protected injection, redaction, canaries, rotation, revocation, and
  outage behavior;
- segregate signing, host identity, job, evidence, release, and entitlement
  secret classes.

Exit: secret threat tests green; no value appears in logs, repository, plans,
evidence, process arguments, or retained runner state.

Sprint 6: second host, dell-u2 drain, and failover

- enroll the second physical host;
- distribute required Phase 1 pools;
- implement drain and disruption budgets;
- execute the full failover exercise;
- prove recovery and rollback.

Exit: dell-u2 can disappear without eliminating eligible required capacity;
evidence filed under docs/qa/.

Sprint 7: onboarding portal and API

- implement repository discovery and plan;
- automate pool/group assignment and DevGate workflow proposal;
- implement partial-resume and rollback;
- prove controlled verification run reaches the intended pool and non-vacuous
  gates.

Exit: a new test repository onboards end to end without host hand-editing or
committed secret material.

Sprint 8: evidence-plane paid services

- implement tier-independent core fixture;
- implement detached aggregation and retention policy;
- implement control mappings, approvals, exports, and support integration
  boundaries;
- test entitlement failure and commercial-service outage.

Exit: identical core result bytes across tiers; paid services add detached
records only.

Sprint 9: MissionControl presentation

- implement read-only views with source/freshness;
- implement mediated commands with authoritative receipts;
- prove MissionControl loss has no effect on source state;
- verify rad-gateway remains absent from the trust path.

Exit: views and commands pass contract tests without direct database access.

Sprint 10: ARC adapter, deferred

Entry requires Sprints 0-9 accepted and Phase 1 stable.

- validate current supported ARC/runner scale-set interfaces;
- map Fleet Manager pool policy to ARC configuration;
- implement observation and error translation;
- test without reimplementing ARC lifecycle internals.

Exit: Kubernetes pool works through ARC and the same Fleet Manager domain
contract.

Sprint 11: release acceptance

- clean-clone build and full gates;
- contract compatibility and extraction rehearsal;
- security, failover, restore, rollback, and entitlement-isolation tests;
- documentation and operator runbooks;
- docs/qa/ release record with exact SHA, commands, runs, evidence, known
  limits, and rollback versions.

Exit: all acceptance requirements below pass. No "mostly green" release.

## 13. ACCEPTANCE SUITE

A. Dependency and package

- A1. Predecessor completion and immutable import are recorded.
- A2. This package validates with unique requirement IDs and complete scenario
  coverage.
- A3. No predecessor-owned canonical contract is copied or redefined.

B. Core truth and tiers

- B1. Same inputs across free and paid entitlements produce byte-identical
  canonical decisions and minimum evidence identities.
- B2. Commercial outage cannot turn fail/error into pass or hide the minimum
  failure reason.
- B3. Expired/malformed entitlement disables only paid functions with an
  explicit state.
- B4. Compliance controls distinguish proved, partial, attested, and
  uncovered.
- B5. Audit exports declare completeness and verify all included digests.

C. Repository boundary

- C1. Open core builds and runs without commercial code.
- C2. Open core has no implementation import from the commercial root.
- C3. Cross-boundary calls pass v1 contracts and compatibility fixtures.
- C4. Temporary extraction rehearsal passes.
- C5. Commercial paths and licenses are machine-verifiable.

D. Fleet control plane

- D1. Plan/apply is revision-bound and idempotent.
- D2. Replayed or stale commands fail.
- D3. Loss of Fleet Manager stops unsafe mutations without killing safe
  running work.
- D4. Host agents expose no general remote shell.
- D5. Every mutation has an authoritative audit receipt.

E. Runner lifecycle

- E1. Each ephemeral runner accepts at most one job.
- E2. Job filesystem, temp, and credentials do not survive cleanup.
- E3. Unknown cleanup quarantines capacity.
- E4. Trust classes cannot be raised by repository configuration.
- E5. Privileged-release capacity is isolated from untrusted work.
- E6. Docker and Podman run the same lifecycle fixtures.

F. dell-u2 and second host

- F1. dell-u2 drains without new assignments.
- F2. Second host accepts controlled work while dell-u2 is drained.
- F3. dell-u2 loss is detected and does not erase all eligible required
  capacity.
- F4. dell-u2 restores from signed desired state.

G. Onboarding

- G1. New repository receives a reviewable plan.
- G2. Apply is resumable after induced partial failure.
- G3. Verification run reaches intended pool and produces non-vacuous DevGate
  evidence.
- G4. No secret value lands in repository state.
- G5. `.devgate/` and `.guardrails/` conventions remain correct.

H. Secrets

- H1. Every secret class has issuer, scope, consumer, TTL/rotation, provider,
  revoke, and incident procedure.
- H2. Seeded secret canaries are absent from all persisted logs and evidence.
- H3. Secrets do not appear in process arguments or runner images.
- H4. Revocation prevents new use within the declared bound.
- H5. Secret-provider outage never falls back to broader static credentials.
- H6. Host, attestation, job, release, and entitlement keys are
  cryptographically and operationally separated.

I. Rollback and recovery

- I1. Fleet Manager, host agent, each adapter, runner image, and commercial
  service roll back independently.
- I2. Restore does not resurrect expired credentials.
- I3. Recovery does not create duplicate active runners.
- I4. Canonical DevGate evidence remains valid across paid-service rollback.

J. Portfolio integrations

- J1. MissionControl reads authoritative APIs and marks freshness.
- J2. MissionControl command returns the owning service's receipt.
- J3. MissionControl outage leaves source systems correct.
- J4. rad-gateway is absent from every trust-path deployment and diagram.

## 14. RISK REGISTER

R1 Critical: runner escape or credential theft

Mitigation: ephemeral one-job instances, trust-class isolation, no
privileged/default socket, narrow mounts and egress, short-lived secrets,
quarantine on uncertain cleanup.

Owner: security and fleet implementation owner.

Gate: security fixtures and host-boundary review.

R2 Critical: paid tier changes truth

Mitigation: entitlement outside core decision path, byte-identity fixtures,
detached enrichment, free minimum evidence.

Owner: DevGate core owner.

Gate: TIER-001 acceptance matrix.

R3 Critical: predecessor contract fork

Mitigation: hard dependency, immutable import, no implementation until
acceptance, contract-diff gate.

Owner: package maintainer.

Gate: DEP-001 and package validation.

R4 High: dell-u2 remains a hidden single point of failure

Mitigation: second physical host, pool eligibility checks, mandatory
drain/loss exercise.

Owner: fleet operator.

Gate: F1-F4.

R5 High: secret sprawl

Mitigation: numbered secret subsystem, provider abstraction, inventory,
references only, redaction canaries, rotation/revocation.

Owner: security owner.

Gate: H1-H6.

R6 High: one repo becomes license spaghetti

Mitigation: one top-level commercial root, dependency-direction gate, path
manifest, contract boundary, extraction rehearsal.

Owner: repository maintainer.

Gate: C1-C5.

R7 High: host agent becomes remote shell

Mitigation: signed desired state, typed allowlisted operations, no arbitrary
command endpoint, receipts, replay protection.

Owner: fleet implementation owner.

Gate: D2-D4.

R8 High: onboarding grants excessive GitHub authority

Mitigation: installation-scoped identity, plan/review, least permissions,
runner groups, no admin credential in workflows.

Owner: integration owner.

Gate: onboarding permission fixture and security review.

R9 Medium: Docker and Podman drift

Mitigation: common adapter contract and fixtures, runtime-specific capability
checks, typed unsupported states.

Owner: adapter owners.

Gate: E6.

R10 Medium: ARC scope expands too early

Mitigation: deferred Sprint 10 and explicit entry gate; ARC adapter, not
replacement.

Owner: program owner.

Gate: Sprint ordering.

R11 Medium: dashboards imply compliance too broadly

Mitigation: coverage states, control-version identity, partial/missing flags,
no gate-pass-equals-compliance rule.

Owner: compliance module owner.

Gate: B4-B5.

R12 Medium: restore duplicates runners or revives credentials

Mitigation: idempotent identity, reconciliation quarantine, expired
credentials never restored as active, recovery drill.

Owner: operations owner.

Gate: I2-I3.

## 15. TRACEABILITY MATRIX

| Source requirements | Sprint | Acceptance |
|---------------------|--------|------------|
| DEP-001, DEP-002 | Sprint 0 | A1, A3 |
| DEP-003 | Sprint 0 | baseline docs/qa/ acceptance |
| REPO-001..005 | Sprints 1 and 11 | C1..C5 |
| TIER-001..003 | Sprints 8 and 11 | B1..B5 |
| FLEET-001..004 | Sprints 2 and 3 | D1..D5 |
| RUN-001..004 | Sprints 4 and 6 | E1..E6, F1..F4 |
| ONB-001..003 | Sprint 7 | G1..G5 |
| SEC-001..006 | Sprints 3, 5, 11 | H1..H6 |
| INT-001..003 | Sprint 9 | J1..J4 |
| Rollback requirements | Sprints 6, 9, 11 | I1..I4 |
| Observability requirements | Sprints 2..11 | D5 and docs/qa/ evidence |

## 16. ARCHITECTURE DECISION RECORDS

ADR-001: sequence after spec coherence

Decision: devgate-spec-coherence-service is a hard predecessor. No
implementation from this package starts before predecessor acceptance.

Status: accepted product direction; package remains blocked.

ADR-002: compliance stays inside DevGate

Decision: compliance is a paid evidence-plane capability, not a standalone
truth engine.

Consequence: gate truth and minimum evidence remain free and tier-independent.

ADR-003: one repository

Decision: use DevGate's repository for open core and commercial modules.

Consequence: directory and license gates are mandatory; no second repository
now.

ADR-004: directory-level commercial boundary

Decision: commercial code lives under one top-level boundary with its own
license and versioned contracts.

Open detail: `enterprise/` versus `fleet-manager/` root is selected in Sprint 0
after audit, once only.

ADR-005: extraction-ready, not extracted

Decision: enforce contracts and run extraction rehearsals. A future
independent evidence repository requires a new owner decision and package.

ADR-006: Fleet Manager differs from fleet

Decision: Fleet Manager owns desired state; replaceable hosts/runners execute
it.

ADR-007: outbound host agent

Decision: home-lab host agents initiate authenticated communication and accept
only signed, typed, allowlisted operations.

ADR-008: Docker and Podman first

Decision: Phase 1 uses warm pools across dell-u2 and a second physical host.

ADR-009: ARC later

Decision: Kubernetes support is an ARC adapter after Phase 1, not a new
autoscaler.

ADR-010: runners are arbitrary-code boundaries

Decision: default to ephemeral one-job instances and trust-class pools with
strict credential and host isolation.

ADR-011: secret management is its own subsystem

Decision: define provider-neutral leases, classes, injection, redaction,
rotation, and revocation before privileged workloads.

ADR-012: MissionControl is presentation and coordination

Decision: it consumes APIs and authoritative receipts; it is not source of
truth.

ADR-013: rad-gateway stays outside trust

Decision: no dependency or proxy role while its own gates are red.

## 17. OPEN OWNER DECISIONS

These choices are intentionally not guessed. They block only the sprint named,
not document review:

- OD-001, Sprint 0: approve the exact commercial license text and contribution
  policy. "GitLab-style" defines architecture, not a reusable license grant.
- OD-002, Sprint 0: choose `enterprise/` or `fleet-manager/` as the single
  commercial root after the dependency audit.
- OD-003, Sprint 5: select the Phase 1 secret provider from the audited
  home-lab environment.
- OD-004, Sprint 3: choose the initial Fleet Manager deployment host and
  recovery target without placing it on the only remaining runner host.
- OD-005, Sprint 7: choose the repository mutation workflow, direct
  owner-controlled commits or a review branch, consistent with current
  repository practice.
- OD-006, Sprint 8: set actual tier names, retention periods, support terms,
  and entitlement issuer. This package defines invariants, not prices.
- OD-007, Sprint 10: approve Kubernetes scope only after Phase 1 evidence.

## 18. CLAUDE CODE HANDOFF

Do not implement this package yet.

First, finish and accept devgate-spec-coherence-service. Then:

1. Pin the accepted predecessor package identity and read its full package.
2. Audit every file in TheArchitectit/AIGGP-Agentic-Framework at the new
   current head.
3. Run all repository tests and gates from a clean clone. Treat zero-input
   gates as no evidence.
4. Publish `docs/qa/YYYY-MM-DD-product-tiers-fleet-manager-baseline.md` with
   exact commands, results, file inventory, overlaps, secrets inventory,
   license inventory, and current runner facts.
5. Reconcile this package with active runner-monitoring, enrollment-and-
   alerting, hub-architecture, add-runner-to-fleet, and
   devgate-spec-coherence-service requirements. Extend them; do not create
   duplicate truth.
6. Stop for the Sprint 0 owner decisions on commercial license, one commercial
   root, secret provider, and deployment/recovery placement.
7. Materialize this package under `openspec/changes/devgate-product-tiers-fleet-manager/`
   using numbered normative spec files, package identity, proposal, design,
   tasks, risks, traceability, ADRs, acceptance, and handoff.
8. Implement strictly in sprint order. No portal, runner deployment, paid
   tier, or secret-bearing path before its entry gates.
9. After each sprint, run the full affected gate chain and publish an exact
   docs/qa/ record with commit and evidence.
10. Do not call the program complete until Sprint 11 is fully green, dell-u2
    failover is proven on a second physical host, secrets tests pass,
    tier-independent truth is byte-proven, and rollback/recovery drills are
    recorded.

## SOURCE NOTES

Repository and current paths:

https://github.com/TheArchitectit/AIGGP-Agentic-Framework

Predecessor OpenSpec:

https://docs.google.com/document/d/1uQKm0Wurg-BTsFHKeSLyBT6FGsEaG172V1K2ErnxM4k/edit

GitHub self-hosted runner reference:

https://docs.github.com/en/actions/reference/runners/self-hosted-runners

GitHub runner scale sets:

https://docs.github.com/en/actions/concepts/runners/runner-scale-sets

GitHub Actions Runner Controller deployment:

https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/deploy-runner-scale-sets

GitHub Actions secure-use reference:

https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions

GitLab directory-level enterprise-feature precedent:

https://docs.gitlab.com/development/ee_features/

END OF PACKAGE
