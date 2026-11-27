# branch-drift sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Use disposable Git repositories with local-only and published refs and a recorded archive decision. Capture the per-repository outcome and the zero-repository diagnostic. Start at [scripts/branch_drift_check.py](../../../scripts/branch_drift_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`bd-01`](../../specs/branch-drift/spec.md#requirement-a-commit-that-exists-only-on-local-disk-is-a-failure) A commit that exists only on local disk is a failure | local-only feature branch / stale remote-tracking cache |
| [`bd-02`](../../specs/branch-drift/spec.md#requirement-archiving-is-a-recorded-decision-not-silence) Archiving is a recorded decision, not silence | parked branch / tag removed |
| [`bd-03`](../../specs/branch-drift/spec.md#requirement-scale-is-reported-not-flattened) Scale is reported, not flattened | large divergence |
| [`bd-04`](../../specs/branch-drift/spec.md#requirement-no-repositories-scanned-is-never-a-pass) No repositories scanned is never a pass | wrong root |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/branch-drift/spec.md) and [sprint dispatch](../../SPRINTS.md).
