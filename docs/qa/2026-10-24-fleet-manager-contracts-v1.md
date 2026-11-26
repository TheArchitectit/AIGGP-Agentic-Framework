# Fleet Manager v1 contracts — evidence

Date: 2026-10-24 (UTC). Program package `devgate-product-tiers-fleet-manager`,
Sprint 1 box 1.2 (versioned `contracts/v1/` + bidirectional contract tests).
Openspec change: `add-fleet-manager-contracts-v1` (requirements
`repo-003-01/02`, `repo-004-01..04`).

## What landed

Three documents cross the boundary, and only these three:

| schema | direction | closed? |
| --- | --- | --- |
| `capacity-request.schema.json` | core → Fleet Manager | yes |
| `capacity-decision.schema.json` | Fleet Manager → core | yes |
| `operation-receipt.schema.json` | Fleet Manager → evidence plane | yes |

`fleet-manager/fleet_manager/contracts.py` is the Fleet Manager's side:
`validate` returns every violation, `parse` raises `ContractInvalid` with the
same list, the `build_*` functions validate what they built and raise rather
than return an invalid document, and `check_version` refuses a major it does
not implement with a message naming both numbers.

`fleet-manager/tests/test_contracts_v1.py` runs 23 tests from the package
alone.

## Gate runs (all re-run in this window)

| gate | result |
| --- | --- |
| `npx --no-install openspec validate --all --strict` | **35/35 items** (34 before this change) |
| `bash scripts/specs-validate-negative-control.sh` | exit 0 |
| `python3 tests/gen_floors.py --check` | OK — 125 suites, 1741 tests |
| `python3 scripts/check_manifest_join.py --repo .` | OK — 1 join, both directions |
| `node scripts/guardrails-scan.mjs` | pattern scan clean (32 non-blocking warnings) |
| `python3 scripts/spec_traceability.py --root . --ratchet` | **91/137**, ratchet raised 85 → 91 |
| `python3 scripts/regression_check.py --base origin/main --fail-if-empty --pre-commit` | rc 0, 0 over hard limit |
| `python3 scripts/artifact_hygiene.py --repo . --audit` | audit OK |
| `python3 -m pytest fleet-manager/tests -q` | **23 passed, 18 subtests** |
| `python3 scripts/check_boundary.py --repo .` | OK — 11 files under the root, all declared; no open-core reference to the boundary |

## The boundary gate caught the new package before the manifest did

Running `check_boundary.py` immediately after writing
`fleet-manager/fleet_manager/` produced, unprompted:

```
[boundary] FAIL: 2 violation(s)
  - fleet-manager/fleet_manager/__init__.py: under the boundary but matched by no declared path ...
  - fleet-manager/fleet_manager/contracts.py: under the boundary but matched by no declared path ...
exit=1
```

That is box 1.1's gate doing its job on the next package that touched the root:
the boundary grew a directory, and the declaration had to catch up in a reviewed
diff (`manifest.json` + `fleet-manager/fleet_manager/**`) before anything could
read green. It is recorded here because a gate whose first live catch is its own
successor is the only evidence that matters for it.

## Planted cases (each is a test, not a claim)

Direction 1 — core-producer fixture → Fleet Manager consumer. Nine recorded
mutations, each refused with the offending path named and as a typed
`ContractInvalid` (never a leaked `KeyError`/`TypeError`):

| mutation | expected in the refusal |
| --- | --- |
| `request_id` removed | `request_id` |
| `demand.concurrency` set to `"1"` | `concurrency` |
| `runner.labels` emptied | `runner.labels` |
| `runner.trust_class` = `"commercial"` | `trust_class` |
| `created_at` = `"yesterday"` | `created_at` |
| `repository` = `"REPO"` (no owner) | `repository` |
| `demand.ephemeral` = `false` | `ephemeral` |
| `workflow.event` removed | `missing required property 'event'` |
| undeclared `priority` added | `unexpected property 'priority'` |

Hostile non-documents (`None`, a string, a list, an int) are refused with a
version error rather than crashing.

Direction 2 — Fleet Manager producer → core-consumer fixture
(`fixtures/core-consumer-expectations.json`, which declares the required paths,
allowed outcomes, reason-code enum, and "absent decision means `unavailable`"):

- an `assigned` decision satisfies every declared path;
- `unavailable` is an explicit document whose reason code is in the core
  side's enum, and the core's rule for an absent decision is the same word;
- a completed receipt satisfies every declared path;
- a producer cannot emit `assigned` without `assignment`, cannot emit
  `assigned` with a `reason`, cannot emit `refused`/`unavailable` without one,
  cannot emit `completed` without evidence, and cannot emit a digest that is not
  `sha256:<64 hex>`.

Version dispatch: `1` accepted; `2` refused naming both numbers **and refused
as a version error alone** (one error, not a pile of shape errors from a schema
that was never meant to describe a v2 document); a missing version refused as
missing; `"1"` refused rather than coerced.

Phase-1 entitlement isolation (OD-001): every v1 schema is walked and fails if
any key is `tier`, `entitlement`, `entitlements`, `license`, `paid`, `plan` or
`subscription`; every schema is asserted closed. There is no entitlement
lifecycle test because there is no entitlement — that leg of REPO-004 is not
applicable in Phase 1, and saying so is the honest form of covering it.

Import surface: the only open-core module the package imports is
`hub.coherence.schemacheck`, pinned by a test that fails on any second import.

## A marker-format bug the traceability gate caught

The first pass put `# spec: repo-003-01 repo-003-02 …` (space-separated) in
both files. `spec_discovery` parses markers **comma-separated**, so only the
first ID registered and coverage read 86/137 instead of 91/137 — a real,
silent under-count. Fixed to the comma form; the ratchet then moved 85 → 91,
which is the arithmetic the change should produce (six new requirements, all
covered).

## What is deliberately not covered

1. **The previous-supported-version leg of REPO-004.** v1 is the first
   version. A test now would test a version that does not exist; the leg
   re-opens when `contracts/v2/` exists.
2. **The entitlement matrix** (absent / expired / malformed / revoked).
   OD-001 descoped the commercial split; the structural isolation above is what
   Phase 1 can prove.
3. **A real core producer.** Core emitting a `capacity-request` is Sprint 2
   (plan/apply) and Sprint 4 (adapters). Today the core side is a fixture —
   data, small, and changed by reviewed diff rather than by an undocumented
   assumption.
4. **An extraction rehearsal.** That is box 1.3; this suite is runnable from the
   package alone precisely so 1.3 can use the same command.

## Stated limits of the design

- The schemas are closed, so **any** shape change — including an "optional"
  added field — is a `contracts/v2/`, not a v1 edit. That is written in
  `contracts/v1/README.md`, because it is the kind of consequence that gets
  rediscovered late.
- Three rules live in code, not in the schema (`assignment` iff `assigned`,
  `reason` iff not `assigned`, `evidence` when `completed`), because the shipped
  stdlib validator has no `if/then`. The split is documented in the module and
  the README; the schema is not presented as the whole contract.
