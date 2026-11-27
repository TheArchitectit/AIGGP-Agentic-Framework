# Tasks

## 1. Enforce local network posture

- [ ] 1.1 Define allowed loopback and explicitly configured LAN address ranges, DNS resolution and change handling, IPv4 and IPv6, and fail-closed startup behavior for wildcard, public, invalid and unresolved addresses.
- [ ] 1.2 Implement the contract at the server boundary and test direct, environment and resolved-address inputs, including rejected wildcard and public addresses and accepted local addresses.
- [ ] 1.3 Update deployment instructions and independently verify the running listener and required firewall and outbound-only assumptions in a controlled environment.

## 2. Qualify hub behavior

- [ ] 2.1 Exercise the one-hub deployment and runner template endpoint and no-peer configuration (`mon-hub-01`).
- [ ] 2.2 Prove API checks for a registered repository runner that has never sent a heartbeat and independently verify heartbeat-only stale detection (`mon-channels-01`).
- [ ] 2.3 Verify persistent registry placement and committed runner-monitor data hygiene with negative controls (`mon-registry-01`).
- [ ] 2.4 Verify watchdog systemd failure and hosted-runner exclusion with disabled-polling and failure controls (`mon-deadman-01`).

## 3. Qualify integration behavior

- [ ] 3.1 Compare local and CI canonical outputs for identical immutable inputs and exercise full fleet metadata preservation (`coh-int-01`, `coh-int-02`).
- [ ] 3.2 Exercise actual consumer promotion and central advisory policy, changed candidate invalidation, and signed-but-unevaluated rejection (`coh-int-03`, `coh-int-04`).
- [ ] 3.3 Exercise timeout and malformed-result error semantics and skipped gate propagation from CI to hub (`coh-int-05`, `coh-int-06`).
- [ ] 3.4 Exercise two independent repositories, watched-branch filtering and empty watched branches (`coh-int-07`).
- [ ] 3.5 Record row-specific results and historical provenance, seal and independently validate accepted evidence bundles, and submit only supported transitions to the state gate.
