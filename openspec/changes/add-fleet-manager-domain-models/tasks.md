# Tasks: add-fleet-manager-domain-models

Program package: `devgate-product-tiers-fleet-manager`, Sprint 2 box 2.1
(repository, host, pool, assignment, capacity, drain, rollout models —
FLEET-001). Predecessors: `add-fleet-manager-boundary` (1.1),
`add-fleet-manager-contracts-v1` (1.2), `add-fleet-manager-extraction-rehearsal`
(1.3).

## 1. The model

- [x] 1.1 `fleet_manager/model.py` — frozen `Repository`, `Pool`, `Host`,
      `Assignment`, `Capacity`, `Drain`, `Rollout`; `DesiredState` with
      revision-per-transition
- [x] 1.2 Validation in the types: bounds, pinned digests, allowed-repositories
      XOR runner group, `ephemeral` Phase-1 const, reference-shaped secret
      profile
- [x] 1.3 Transitions: assign, release, drain, complete drain, return to
      service, rollout — each refusing an impossible state by name

## 2. The separation and the wire form

- [x] 2.1 `fleet_manager/observation.py` — observed runners as a type desired
      state cannot be built from; no import in either direction, proven by test
- [x] 2.2 `fleet_manager/documents.py` — closed `to_document()` /
      `from_document()`, missing field named, unknown field refused, secret-
      shaped keys refused without echoing the value
- [x] 2.3 Round-trip: document → state → document is byte-identical for the
      fixture fleet

## 3. Evidence

- [x] 3.1 `tests/test_model_v1.py` with a suite floor; every requirement's
      scenarios as named tests
- [x] 3.2 `docs/qa/2026-10-24-fleet-manager-domain-models.md` — what the model
      refuses, the planted cases, and what it deliberately does not do
