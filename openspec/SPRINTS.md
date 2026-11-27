# OpenSpec sprint plans

Use the [capability catalog](INDEX.md#capability-catalog) to open a plan for each published specification. The [active changes](INDEX.md#active-changes) link to package execution plans beside their proposals, tasks and deltas. The [archive routing table](sprints/archive.md) assigns each archived package a historical evidence or owner follow-up route. Plans describe proposed work. The state ledger and accepted evidence determine lifecycle status.

## Sprint sequence

Use these four iterations for a selected workstream. The lead sizes the selected tasks with the accountable owner at intake. Dates and capacity depend on that selection. If a required input is missing, record the dependency and continue another ready workstream.

| Sprint | Ready work and dependencies | Deliverable and exit decision |
| --- | --- | --- |
| S1. Establish the baseline | Start DG-02 at row 145, check the last seal, and pin the reviewed source. In parallel, inventory the active package's unchecked tasks, fixture inputs, authority and current receipts. | Lead accepts a bounded selection of IDs, owner, source revision, expected behavior and evidence destination. Conditional work gets its activation condition. |
| S2. Implement or collect | Start the selected writer after S1. Prioritize the documented contract fixture gap and consumer evidence boundary ahead of downstream promotion claims. Monitoring recovery, native gate qualification and historical evidence collection can proceed independently. | Writer delivers a scoped change or an explicit missing-proof disposition. Collector supplies exact test IDs, input, expected and observed results, digests and candidate SHA. |
| S3. Qualify independently | Give a different audit session the artifacts. Re-run positive and rejection cases and inspect the actual boundary. Compare source and consumer pins, job checkouts, runner identity and skipped steps wherever CI is part of the claim. | Auditor signs a row-level verdict. Missing proof, stale evidence and incomplete runs stay visible. Route discrepancies to the writer with the failed criterion. |
| S4. Integrate and hand off | Lead verifies the audit, reconciles the diff, repeats the gates and pushes the accepted scope. Consumer, release, security, bank or platform owners supply their own external decisions. | Record the commit and exact matching checks. Update the package task and index only for work actually accepted. A lifecycle transition requires its own evidence. |

## Dispatch by agent type

| Agent type | Pickup queue | Handoff |
| --- | --- | --- |
| Lead | Choose the workstream, dependency order and acceptance boundary in S1. Reconcile S3 findings and independently verify the final artifact in S4. | Signed disposition, final gates and direct push. The lead owns design and final sign-off. |
| Writer or implementer | Take the package's S2 slice after the lead scopes it. Use Luna where practical. A published capability with an evidence gap starts with its existing implementation. | Scoped diff, exact entry point, test command, observed result and unresolved cases. |
| Evidence collector | Use Luna to inspect pinned files, named tests, original run logs and relevant historical bundles. Collect independent source receipts for cross-repository claims. | Hand the auditor the artifact, candidate identities, expected digest and evidence locations. |
| Independent auditor | Work in a separate session from the writer. Recompute results from source and inspect independent checks, including a failing control where appropriate. | Per-requirement verdict and reason. Hand the lead a reproducible receipt or an explicit blocker. |
| Accountable owner | Resolve the package's named product, release, consumer, bank or external environment decision when applicable. A role assignment in a plan does not grant production access. | Dated decision, accepted environment or artifact identity, and any limits on use. |

The repository's [write, audit and review process](../docs/WRITE_AUDIT_REVIEW.md) governs these handoffs. The [six bank qualification tasks](changes/audit-bank-ai-tooling-platform-fit/tasks.md#accountable-roles-and-next-receipts) retain their separate owner routes. The [hosted pilot](changes/qualify-consumer-delivery-evidence/hosted-pilot.md) records its approved pilot pin. Hosted consumer qualification belongs on its hosted runner. Lab jobs assigned to UCS03 require their own host evidence and the AI02 App check for the candidate.

## Session adapter matrix

Use the following queues when a selected change affects session startup or its manifest. Each carrier-specific result needs a receipt. A shared backend result alone leaves the carrier pickup open. Most framework and fleet requirements operate below this boundary and use their native entry point.

| Adapter | Writer and collector work | Independent acceptance |
| --- | --- | --- |
| [Claude Code](../templates/hooks/claude-code/session-start.sh) | Feed the shell adapter a synthetic session event in a disposable project. Capture its carrier identity, emitted context and process result. | Verify the valid work case and refused deterministic play case against the session contract, including the session log count. |
| [Codex](../templates/hooks/codex/session-start.sh) | Dispatch the same semantically equivalent event through the Codex adapter. Record the carrier and the shared validator result. | Inspect the Codex receipt and reproduce both outcomes from an independent checkout. |
| [MiMo](../templates/hooks/mimo/session-start.sh) | Exercise the MiMo shell entry point and capture environment-derived scope and the normalized manifest. | Compare the resulting accepted and refused sessions with the expected contract and confirm refusal does not append an accepted session. |
| [OpenCode](../templates/hooks/opencode/session-start.mjs) | Invoke the Node entry point with its fixture shape. Retain its Node version, normalized manifest and returned outcome. | Verify the Node path reaches the session validator and compare the expected accept/refuse outcomes with the shell carriers. |
| [Pi extension](../templates/hooks/pi-extension/session-init.ts) | Use the TypeScript carrier harness and the pinned runtime used in framework CI. Capture the extension callback, validator outcome and failure propagation. | Replay the [carrier test](../tests/test_pi_extension_adapter.py) independently and check both accepted and refused cases. |

The shell and OpenCode test exercises four carriers. The Pi harness exercises the fifth. To replay both controls, set `PI_SESSION_TSX` to the installed `tsx@4.23.15` executable used by framework CI and run the following from the repository root. [CI setup](../.github/workflows/ci.yml) and [carrier fixtures](../tests/test_game_session_start.py).

```sh
python3 -m pytest -q \
  tests/test_game_session_start.py::test_shell_and_opencode_carrier_adapters_accept_and_refuse \
  tests/test_pi_extension_adapter.py
```

The [session-start plan](sprints/capabilities/game-session-start.md) owns cross-carrier parity. The consuming game repository owns the [deferred phase matrix](sprints/capabilities/game-type-phase-matrix.md). A framework plan cannot schedule that owner's implementation.

## Workstream pickup

- **Evidence reconciliation.** Review DG-02 rows 145-156, 157-168, 169-180 and 181-182 in order, with a fresh source pin and independent seal verification for each batch. The final roster requires its own one-to-one reconciliation. Archive-checkbox investigation runs separately under DG-04. [DG-02](changes/dg-02-evidence-ledger-reconciliation/sprint-plan.md) and [DG-04](changes/dg-04-archive-task-reconciliation/sprint-plan.md).
- **Consumer and bank qualification.** Establish trusted scope and exact subject identity, qualify the delivery checks and recovery evidence, then hand the six bank-specific acceptance decisions to their owners. [Consumer boundary](changes/define-consumer-evidence-boundary/sprint-plan.md), [delivery](changes/qualify-consumer-delivery-evidence/sprint-plan.md) and [bank tasks](changes/audit-bank-ai-tooling-platform-fit/sprint-plan.md).
- **Fleet and framework correctness.** Work from the corresponding DG-02 qualification packages and native gate plans. Qualify contract behavior before downstream consumers rely on it. Collect recovery evidence before reopening operator acceptance. [Fleet contract gap](changes/qualify-dg02-boundary-contract-domain-gaps/sprint-plan.md), [gate scope](changes/gate-scope-honesty/sprint-plan.md) and [monitor recovery](changes/qualify-monitor-recovery/sprint-plan.md).
- **Corruption review.** Keep the detached complete-range review and protected exact-transition review as independent, mutually exclusive trusted modes; neither is a fallback for the other. Existing callers stay strict, and stale or absent receipts do not authorize findings. See [detached range review](changes/archive/2026-11-27-consume-detached-corruption-review/sprint-plan.md), its [published capability plan](sprints/capabilities/data-corruption.md), [protected transition review](changes/provision-exact-corruption-reviews/sprint-plan.md), and the [operator procedure](../docs/runbooks/reviewed-corruption-transitions.md).
- **Release and external adoption.** The release owner selects the release candidate. Live GitLab adoption, bank deployment and external art/game receipts depend on the relevant owners. [Release plan](changes/dg22-prepare-approved-main-release/sprint-plan.md), [GitLab plan](changes/add-gitlab-forge-support/sprint-plan.md) and [external art proof](changes/dg-06-art-evolution-external-proof/sprint-plan.md).

When a new capability or active change lands, add its plan and regenerate the [OpenSpec index](INDEX.md). Use the current requirement text and task list at pickup. Record discovered work in the owning package and preserve historical receipts at their reviewed revisions.

The [portfolio publication receipt](sprints/portfolio-ci.md) records the exact sprint-plan commit, its ten App checks, runner assignments and cancelled jobs.
