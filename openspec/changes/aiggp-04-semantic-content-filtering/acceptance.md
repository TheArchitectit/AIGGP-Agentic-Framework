## Required conformance fixtures

- Fixture A: credential in commit - redacted, hash recorded, block at boundary.
- Fixture B: personal data in outbound send - held for escalation per policy.
- Fixture C: benign code resembling secrets - allowed within false-positive budget.
- Fixture D: classifier timeout at boundary - escalate, not allow.
- Fixture E: version bump without re-run - stale status reported.

## Release acceptance criteria

- All fixtures pass; per-category budgets met on pinned corpora; envelope validation rejects identity-less decisions; drift monitor demonstrates one detected behavior change in test.

## Open questions requiring owner decisions

- Classifier provider(s) for the core categories and their local-vs-hosted posture.
- Escalation routing (who decides held sends) for solo vs team deployments.

## Handoff

Start with secrets/credentials: the clearest category, the easiest corpus, the fastest trust win. Keep every category honest about both failure directions - the published failure-mode table is a reputation asset, not an admission of weakness.
