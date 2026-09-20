## Required conformance fixtures

- Fixture A: forged-credential runner - rejected, evidence refused.
- Fixture B: expired enrollment - heartbeat refused, unenrolled transition.
- Fixture C: under-classed scheduling - refused.
- Fixture D: stale signed state - execution refused.
- Fixture E: silent runner - suspect then drained, workloads migrated.
- Fixture F: bad bundle rollout - canary detects, rollback evidenced both directions.
- Fixture G: cross-class secret request - denied and logged.

## Release acceptance criteria

- All fixtures pass; drills run in CI; ai01 and the fleet runners migrate onto the protocol; Mission Control renders runner state from verified ledger evidence only.

## Open questions requiring owner decisions

- Enrollment credential mechanism (platform-issued certificates vs workload-identity federation per host).
- Whether the existing ai01 monitor is retired immediately on protocol migration or kept as a redundant view during a transition window.

## Handoff

Start from the salvaged fleet machinery and the ai01 monitor's real operational lessons. The hostile-runner drill is the demo: show a forged runner being rejected and its evidence refused, then show Mission Control displaying only what the ledger verifies.
