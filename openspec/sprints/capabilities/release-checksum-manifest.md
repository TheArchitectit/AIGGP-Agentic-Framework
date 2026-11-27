# release-checksum-manifest sprint plan

At `cb2205c` the index recorded **OPEN**. Select an unresolved requirement with its owner. Establish the intended behavior and delivery boundary before implementation.

Route acceptance to the **release owner**. Bring a named candidate and disposable packaging or release fixtures to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept version, target, artifacts and owner disposition. |
| S2. Luna writer | Rebuild the checksum inventory from tracked Git paths and compare it byte-for-byte. Retain diagnostics from malformed, duplicate and missing entries. Start at [tests/test_gen_checksums.py](../../../tests/test_gen_checksums.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for version, target, artifacts and owner disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fw-ci-06`](../../specs/release-checksum-manifest/spec.md#requirement-checksum-manifest-records-are-unambiguous-and-well-formed) Checksum manifest records are unambiguous and well-formed | malformed digest is present / duplicate normalized path is present |
| [`fw-ci-05`](../../specs/release-checksum-manifest/spec.md#requirement-the-shipped-script-checksum-manifest-matches-tracked-scripts) The shipped script checksum manifest matches tracked scripts | a tracked script is added or changed / the manifest is stale or incomplete / CI verifier reports the underlying manifest mismatch |
| [`fw-ci-07`](../../specs/release-checksum-manifest/spec.md#requirement-the-checksum-inventory-preserves-supported-git-paths) The checksum inventory preserves supported Git paths | a quoted Unicode path is included / a pathname cannot be represented by the manifest / an unresolved index repeats a path / the supported inventory remains scoped |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [dg22-prepare-approved-main-release](../../changes/dg22-prepare-approved-main-release/sprint-plan.md).

[Published specification](../../specs/release-checksum-manifest/spec.md) and [sprint dispatch](../../SPRINTS.md).
