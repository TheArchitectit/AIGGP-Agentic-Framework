# Tasks: add-fleet-manager-contracts-v1

Program package: `devgate-product-tiers-fleet-manager`, Sprint 1 box 1.2
(versioned contracts + bidirectional contract tests). Box 1.3 (extraction
rehearsal) is a separate change.

## 1. The contracts

- [x] 1.1 `fleet-manager/contracts/v1/README.md`: versioning policy — version
      in the document, one major per consumer, v1 frozen, closed schemas mean
      any shape change is v2, and the previous-version leg named as not yet
      testable
- [x] 1.2 `capacity-request.schema.json` — core → Fleet Manager
- [x] 1.3 `capacity-decision.schema.json` — Fleet Manager → core, four typed
      outcomes, reason required when not assigned
- [x] 1.4 `operation-receipt.schema.json` — Fleet Manager → evidence plane,
      evidence required when completed
- [x] 1.5 `fixtures/core-capacity-request.json` and
      `fixtures/core-consumer-expectations.json`: the other side, as data

## 2. The implementation

- [x] 2.1 `fleet-manager/fleet_manager/contracts.py`: load, validate, version
      dispatch, typed refusals, builders that refuse to emit invalid documents
- [x] 2.2 `fleet-manager/fleet_manager/__init__.py`: the package surface
- [x] 2.3 `fleet-manager/manifest.json`: declare `fleet-manager/fleet_manager/**`
      (the boundary gate refused the new package until it was declared)

## 3. The tests

- [x] 3.1 `fleet-manager/tests/test_contracts_v1.py`: direction 1 (core
      producer fixture → Fleet Manager consumer, 9 recorded mutations refused
      with named paths), direction 2 (Fleet Manager producer → core consumer
      fixture minimum), version dispatch, entitlement isolation, pinned
      core-import surface, and a suite floor that lives with the package
- [x] 3.2 CI: `fleet-manager/tests` runs as its own step, so the same command
      is what the extraction rehearsal will use

## 4. Evidence

- [x] 4.1 `docs/qa/2026-10-24-fleet-manager-contracts-v1.md`: gate runs,
      planted cases, what is not covered and why
