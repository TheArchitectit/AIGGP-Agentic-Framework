# Tasks

## 1. Implementation and verification

- [ ] 1.1 Preserve dormant 2026-11-15 decision in docs/spec; verify no live instance is required before explicit adoption.
- [ ] 1.2 On adoption, add forge-dispatched GitLab runner checks using declared endpoint/auth; test with API stubs that GitLab online status comes from the declared GitLab adapter and is combined with heartbeat freshness, while GitHub continues using its current API path.
- [ ] 1.3 Add activation preflight and tests for online, stale-heartbeat, missing/unknown status, and API-error outcomes; verify errors cannot read healthy, GitHub behavior remains intact, and secrets/instance data do not enter repo artifacts or logs.
- [ ] 1.4 After an operator selects a live instance, run the private live acceptance drill and publish redacted version/outcome/reference; keep dormant until then.
