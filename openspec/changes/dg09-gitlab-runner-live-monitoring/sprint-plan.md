# Sprint plan — DG-09 GitLab runner live monitoring

**Scope:** keep GitLab monitoring optional and dormant until explicit operator adoption.
All tasks 1.1–1.4 are unchecked; the design and `docs/GITLAB-FORGE.md` state that no live instance has been contacted.

## Sequence

### S1 — intake/baseline

- For task 1.1, preserve the 2026-11-15 owner decision and verify docs/spec still say a live instance is not required before adoption.
- Confirm the deployed declaration remains operator-owned; GitHub’s existing monitoring path remains the regression baseline.
- Existing GitLab deployment/monitor fixtures and GitHub monitor tests are regression context only; they do not yet satisfy this package’s forge-dispatch behavior.

### S2 — implementation or evidence collection (conditional)

- For task 1.3, build and test the activation preflight now with API stubs. Cover online, stale-heartbeat, missing or unknown status and API error.
- Task 1.2 starts on operator adoption. Implement forge-dispatched status checks using the declared endpoint and authentication, and test the combination of adapter status and heartbeat freshness.
- Ensure errors cannot be healthy, GitHub behavior remains intact, and private instance details/secrets do not enter repository artifacts or logs.

### S3 — independent qualification

- A separate audit session checks the activation boundary, adapter dispatch, heartbeat conjunction, all refusal outcomes, GitHub regression controls, and artifact/log redaction.
- The auditor can qualify the hermetic preflight independently. Record live connectivity as NOT_RUN until adoption, the instance declaration and scoped access are available.

### S4 — integration/closeout

- Task 1.4 activates only after the operator selects a real instance; run private live acceptance and publish a redacted version/outcome/reference.
- Lead reconciles that receipt, updates the dormant/active disposition, reruns gates, and signs off the exercised scope. If no instance is selected, the adoption-triggered work stays dormant. Adjudicate 1.1 and 1.3 on their own evidence.

## Bounded roles

- The lead owns design, review and sign-off. Luna can implement and collect task 1.3 preflight receipts immediately. On adoption, Luna can also exercise task 1.2 adapter checks. The operator supplies the live task 1.4 receipt.
- Operator: select/configure the instance and authorize live acceptance. A distinct audit session validates redacted receipts; no live work is assigned by this plan.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Design and adoption gate](design.md)
- [GitLab deployment/monitor fixtures](../../../tests/test_gitlab_forge_deployment.py) · [GitHub monitor tests](../../../tests/test_hub_monitor.py)
- [GitLab integration guide](../../../docs/GITLAB-FORGE.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
