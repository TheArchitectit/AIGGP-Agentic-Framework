# Tasks

## 1. Monitoring contracts

- [ ] 1.1 Verify API-offline, heartbeat-only stale and healthy controls, including runner and repository details (`mon-online-01`).
- [ ] 1.2 Match queued jobs to registered runner labels, apply per-repository threshold overrides, and include repository, run, label and age in alerts. Test matched, unmatched, unknown-label, multiple-runner and threshold-boundary cases (`mon-queue-01`).
- [ ] 1.3 Verify latest gate results per watched and default branch, failure and timeout, and commit identification (`mon-gates-01`).
- [ ] 1.4 Derive or explicitly configure each scheduled drift period and grace, handle absent or unknown schedules honestly, and test hourly and multi-day schedules and failed scans (`mon-drift-01`).

## 2. Scanner and security contracts

- [ ] 2.1 Qualify comment syntax and generated scaffolding per language, scene connection parsing, Rust test scopes and test-file sizing, including positive and negative controls (`rule-marker-01`, `gate-tscn-01`, `gate-rstest-01`, `gate-size-01`).
- [ ] 2.2 Prove contained-path rejection before reads, including exit class, named path and sealed-evidence non-disclosure (`coh-sec-01`).
- [ ] 2.3 Reconcile the duplicate-enrollment loser response with atomic token consumption; test the exact contract alongside body limits and idle signal shutdown (`mon-sec-01`).
- [ ] 2.4 Qualify token hashing, revocation and output handling through enrollment and CI logs without exposing token material (`mon-sec-02`).
- [ ] 2.5 Establish valid provenance for the shipped template locations; correct the stale `ci-sec-01` closure pointer from `templates/github/workflows/` to the actual `templates/github-workflows/` and align it with the scenario. Test immutable action/image references, adjacent version information, health checks and documented secrets drop-in parsing (`ci-sec-01`).
- [ ] 2.6 Bind each historical claim to accepted, requirement-specific evidence and an expected digest. Independently validate the bundles and submit only qualified transitions to the state gate.
