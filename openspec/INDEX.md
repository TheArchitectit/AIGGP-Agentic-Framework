# OpenSpec index

> **Generated, not typed.** Status is derived from each spec's own closure
> table (the per-requirement `EXERCISED` / `WIRED` / `ABSENT` / `NOT_RUN`
> cells), the state ledger, or its explicit `Status:` line. A spec with no
> closure evidence is reported **UNKNOWN** rather than guessed at.
>
> **UNPROVEN** is not a new state word: it says a requirement claims
> `EXERCISED` while no ledger row proves it. `openspec/state-unproven.jsonl`
> records why, and editing the spec cannot promote a marker — proof is a ledger
> row with two resolved, ordered commits and a sealed evidence bundle, which
> the spec-state gate accepts and no prose edit produces.
>
> **DEFERRED** is a decision, not a backlog item. The single row marked
> DEFERRED below has its owner's answer (base-specs-01: the capability lives
> in the consuming game repo) and stays DEFERRED until that repo builds it —
> it is not closed by relabelling the line.

**56 specs** — CLOSED 1 · DEFERRED 1 · UNPROVEN 42 · PARTIAL 0 · OPEN 0 · UNKNOWN 12

| Spec | Title | Status | Evidence |
|---|---|---|---|
| [`adapters-and-loops/spec.md`](specs/adapters-and-loops/spec.md) | Adapters and loops | **UNKNOWN** | no closure table and no Status line |
| [`add-runner-to-fleet/spec.md`](specs/add-runner-to-fleet/spec.md) | Adding a runner to an existing fleet | **UNPROVEN** | UNPROVEN — 1 of 1 requirement(s) lack a proving ledger row (1 provenance-accepted, awaiting sealed evidence) |
| [`adoption-and-policy/spec.md`](specs/adoption-and-policy/spec.md) | Adoption and Policy | **UNPROVEN** | UNPROVEN — 7 of 7 requirement(s) lack a proving ledger row (7 provenance-accepted, awaiting sealed evidence) |
| [`art-creation-contract/spec.md`](specs/art-creation-contract/spec.md) | Art creation contract | **UNKNOWN** | no closure table and no Status line |
| [`assertions-and-evaluators/spec.md`](specs/assertions-and-evaluators/spec.md) | Assertions and Evaluators | **UNPROVEN** | UNPROVEN — 6 of 6 requirement(s) lack a proving ledger row (6 provenance-accepted, awaiting sealed evidence) |
| [`baseline-ownership/spec.md`](specs/baseline-ownership/spec.md) | Baseline data ownership | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`branch-drift/spec.md`](specs/branch-drift/spec.md) | Branch drift | **UNKNOWN** | no closure table and no Status line |
| [`canonical-identity/spec.md`](specs/canonical-identity/spec.md) | Canonical Identity | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row (5 provenance-accepted, awaiting sealed evidence) |
| [`ci-template-contract/spec.md`](specs/ci-template-contract/spec.md) | CI template contract | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row |
| [`coherence-evaluation/spec.md`](specs/coherence-evaluation/spec.md) | Coherence Evaluation | **UNPROVEN** | UNPROVEN — 6 of 6 requirement(s) lack a proving ledger row (6 provenance-accepted, awaiting sealed evidence) |
| [`container-runtime/spec.md`](specs/container-runtime/spec.md) | Container Runtime | **UNPROVEN** | UNPROVEN — 7 of 7 requirement(s) lack a proving ledger row (7 provenance-accepted, awaiting sealed evidence) |
| [`decision-contract/spec.md`](specs/decision-contract/spec.md) | Decision Contract | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row (5 provenance-accepted, awaiting sealed evidence) |
| [`doc-truth/spec.md`](specs/doc-truth/spec.md) | Documentation truth | **CLOSED** | Status: CLOSED (EXERCISED 2) |
| [`enrollment-and-alerting/spec.md`](specs/enrollment-and-alerting/spec.md) | Enrollment, heartbeat, and alerting | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`evaluation-context/spec.md`](specs/evaluation-context/spec.md) | Evaluation Context | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row (5 provenance-accepted, awaiting sealed evidence) |
| [`evidence-and-attestation/spec.md`](specs/evidence-and-attestation/spec.md) | Evidence and Attestation | **UNPROVEN** | UNPROVEN — 7 of 7 requirement(s) lack a proving ledger row (7 provenance-accepted, awaiting sealed evidence) |
| [`evidence-claims/spec.md`](specs/evidence-claims/spec.md) | Evidence claims | **UNKNOWN** | no closure table and no Status line |
| [`fleet-app-enrollment/spec.md`](specs/fleet-app-enrollment/spec.md) | Fleet app enrollment | **UNKNOWN** | no closure table and no Status line |
| [`fleet-manager-adapter-contract/spec.md`](specs/fleet-manager-adapter-contract/spec.md) | Fleet manager adapter contract | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row |
| [`fleet-manager-agent-channel/spec.md`](specs/fleet-manager-agent-channel/spec.md) | Fleet manager agent channel | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row |
| [`fleet-manager-agent-operations/spec.md`](specs/fleet-manager-agent-operations/spec.md) | Fleet manager agent operations | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row |
| [`fleet-manager-boundary/spec.md`](specs/fleet-manager-boundary/spec.md) | Fleet manager boundary | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row |
| [`fleet-manager-contracts/spec.md`](specs/fleet-manager-contracts/spec.md) | Fleet manager contracts | **UNPROVEN** | UNPROVEN — 6 of 6 requirement(s) lack a proving ledger row |
| [`fleet-manager-domain/spec.md`](specs/fleet-manager-domain/spec.md) | Fleet manager domain | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row |
| [`fleet-manager-extraction/spec.md`](specs/fleet-manager-extraction/spec.md) | Fleet manager extraction rehearsal | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row |
| [`fleet-manager-job-lifecycle/spec.md`](specs/fleet-manager-job-lifecycle/spec.md) | Fleet manager job lifecycle | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row |
| [`fleet-manager-plan/spec.md`](specs/fleet-manager-plan/spec.md) | Fleet manager plan and apply | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row |
| [`fleet-manager-reconciliation/spec.md`](specs/fleet-manager-reconciliation/spec.md) | Fleet manager reconciliation | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row |
| [`fleet-manager-signed-state/spec.md`](specs/fleet-manager-signed-state/spec.md) | Fleet manager signed state | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row |
| [`framework-ci/spec.md`](specs/framework-ci/spec.md) | Framework CI | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`game-regression/spec.md`](specs/game-regression/spec.md) | Game-class regression scanning | **UNPROVEN** | UNPROVEN — 6 of 6 requirement(s) lack a proving ledger row (6 provenance-accepted, awaiting sealed evidence) |
| [`game-session-start/spec.md`](specs/game-session-start/spec.md) | Game session start | **UNPROVEN** | UNPROVEN — 6 of 6 requirement(s) lack a proving ledger row |
| [`game-type-phase-matrix/spec.md`](specs/game-type-phase-matrix/spec.md) | Game-type phase matrix | **DEFERRED** | Status: DEFERRED |
| [`gate-configuration-contract/spec.md`](specs/gate-configuration-contract/spec.md) | Gate configuration contract | **UNPROVEN** | UNPROVEN — 2 of 2 requirement(s) lack a proving ledger row (2 provenance-accepted, awaiting sealed evidence) |
| [`gate-execution-contract/spec.md`](specs/gate-execution-contract/spec.md) | Gate execution contract | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`hub-architecture/spec.md`](specs/hub-architecture/spec.md) | Hub-and-spoke monitor architecture | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row (5 provenance-accepted, awaiting sealed evidence) |
| [`integrations/spec.md`](specs/integrations/spec.md) | Integrations | **UNPROVEN** | UNPROVEN — 7 of 7 requirement(s) lack a proving ledger row (7 provenance-accepted, awaiting sealed evidence) |
| [`open-item-aging/spec.md`](specs/open-item-aging/spec.md) | Open item aging | **UNKNOWN** | no closure table and no Status line |
| [`package-resolution/spec.md`](specs/package-resolution/spec.md) | Package Resolution | **UNPROVEN** | UNPROVEN — 5 of 5 requirement(s) lack a proving ledger row (5 provenance-accepted, awaiting sealed evidence) |
| [`per-screen-tracking/spec.md`](specs/per-screen-tracking/spec.md) | Per-screen feature tracking | **UNPROVEN** | UNPROVEN — 2 of 2 requirement(s) lack a proving ledger row (2 provenance-accepted, awaiting sealed evidence) |
| [`publish-safety/spec.md`](specs/publish-safety/spec.md) | Publish leg safety | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`release-gate-targeting/spec.md`](specs/release-gate-targeting/spec.md) | Release gate targeting and audit classification | **UNPROVEN** | UNPROVEN — 2 of 2 requirement(s) lack a proving ledger row (2 provenance-accepted, awaiting sealed evidence) |
| [`reviewer-surfaces/spec.md`](specs/reviewer-surfaces/spec.md) | Reviewer surfaces | **UNKNOWN** | no closure table and no Status line |
| [`rule-coverage-truth/spec.md`](specs/rule-coverage-truth/spec.md) | Rule coverage truth | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`runner-monitoring/spec.md`](specs/runner-monitoring/spec.md) | Runner health monitoring | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row (4 provenance-accepted, awaiting sealed evidence) |
| [`runner-toolchain-requests/spec.md`](specs/runner-toolchain-requests/spec.md) | Runner toolchain requests | **UNPROVEN** | UNPROVEN — 6 of 6 requirement(s) lack a proving ledger row |
| [`scanner-parsing/spec.md`](specs/scanner-parsing/spec.md) | Scanner parsing correctness | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`secret-rotation/spec.md`](specs/secret-rotation/spec.md) | Secret rotation | **UNKNOWN** | no closure table and no Status line |
| [`security-boundaries/spec.md`](specs/security-boundaries/spec.md) | Security boundaries | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`spec-platform/spec.md`](specs/spec-platform/spec.md) | Spec platform | **UNPROVEN** | UNPROVEN — 3 of 3 requirement(s) lack a proving ledger row (3 provenance-accepted, awaiting sealed evidence) |
| [`spec-state-ledger/spec.md`](specs/spec-state-ledger/spec.md) | Spec state ledger | **UNKNOWN** | no closure table and no Status line |
| [`subjects-3d/spec.md`](specs/subjects-3d/spec.md) | 3D Subjects | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row (4 provenance-accepted, awaiting sealed evidence) |
| [`surface-reach/spec.md`](specs/surface-reach/spec.md) | Surface reach | **UNKNOWN** | no closure table and no Status line |
| [`traceability-and-drift/spec.md`](specs/traceability-and-drift/spec.md) | Traceability and drift | **UNKNOWN** | no closure table and no Status line |
| [`tree-clean/spec.md`](specs/tree-clean/spec.md) | Tree clean | **UNKNOWN** | no closure table and no Status line |
| [`zig-opengl-engine/spec.md`](specs/zig-opengl-engine/spec.md) | Zig + OpenGL Engine Support | **UNPROVEN** | UNPROVEN — 4 of 4 requirement(s) lack a proving ledger row |

## Reading the status

- **CLOSED** — every requirement row is `EXERCISED` **and** a ledger row proves
  it with two resolved, ordered commits and sealed evidence.
- **UNPROVEN** — at least one requirement claims `EXERCISED` (a closure cell or
  a terminal `Status:` line) without a proving ledger row. The marker file
  names each one and why; a spec edit cannot clear it.
- **PARTIAL** — some rows `EXERCISED`, at least one `WIRED`/`ABSENT`/
  `NOT_RUN`/`DIFFERS`. The gap is named in that spec.
- **OPEN** — no requirement reaches `EXERCISED`, or a non-terminal `Status:`
  line is the only authority.
- **UNKNOWN** — no closure table and no `Status:` line. A documentation gap,
  not a claim the work is unfinished. Fix by adding the closure table.
