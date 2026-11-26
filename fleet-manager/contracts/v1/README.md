# Fleet Manager contracts — v1

Every document that crosses the open-core / Fleet Manager boundary is one of
the three schemas in this directory. Nothing else crosses: no core module
imports `fleet_manager`, and Fleet Manager imports exactly one core module
(`hub.coherence.schemacheck`), pinned by a test.

| schema | direction | what it is |
| --- | --- | --- |
| `capacity-request.schema.json` | core → Fleet Manager | what a job needs (repo, workflow, labels, trust class, demand) |
| `capacity-decision.schema.json` | Fleet Manager → core | `assigned` / `queued` / `refused` / `unavailable`, typed reason when not assigned |
| `operation-receipt.schema.json` | Fleet Manager → evidence plane | what was done, to what, by whom, with an evidence digest when completed |

`fixtures/` holds the two documents the opposite side is represented by in the
contract tests: a capacity request as core would emit it, and the core
consumer's declared minimum expectations.

## Versioning policy

- **The version is in the document** (`contract_version`), not in a URL, a
  header, or the reader's memory. A document that does not say which contract
  it speaks is refused (repo-003-02).
- **A consumer implements one major.** A document declaring another major is
  refused with a version error naming both numbers — it is never read against
  the wrong shape and never silently coerced.
- **v1 is frozen.** These schemas are closed (`additionalProperties: false`),
  so even an "optional new field" would be rejected by every v1 consumer. A
  shape change therefore means a new `contracts/v2/` directory with its own
  schemas, its own fixtures and its own tests; `v1` stays in the tree,
  unchanged, as long as a producer may still emit it.
- **The previous-supported-version leg is not yet testable.** v1 is the first
  version, so there is no previous one to run the current implementation
  against. That leg of REPO-004 re-opens the day `v2/` exists, and the test
  that carries it is named in `fleet-manager/tests/test_contracts_v1.py` where
  it currently documents the gap instead of pretending.

## What the contracts deliberately cannot express

The schemas have no `tier`, `entitlement`, `license`, or `paid` field, and
they are closed. Under OD-001 (no commercial split in Phase 1) this is the
strongest available isolation: a document physically cannot carry a paid-tier
flag that would let a decision depend on it. A test walks the schema files and
fails if such a field appears.

The rules that JSON Schema draft-07 as shipped in this repository cannot
express — "an `assignment` iff `assigned`", "a `reason` iff not `assigned`",
"evidence when `completed`" — are enforced in `fleet_manager/contracts.py` and
tested there. The split is stated so nobody reads the schema as the whole
contract.

## Verifying by hand

```sh
python3 -m pytest fleet-manager/tests -v      # from the repository root
python3 scripts/check_boundary.py --repo .    # the boundary this lives in
```
