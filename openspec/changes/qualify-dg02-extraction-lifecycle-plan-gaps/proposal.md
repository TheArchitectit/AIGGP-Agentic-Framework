# Qualify extraction, lifecycle and plan evidence gaps

## Why

DG-02 rows 145–156 map to the existing extraction rehearsal, job lifecycle and plan/apply requirements. The current row records have empty citations and rejected provenance, so present behavior cannot establish historical closure. Review of the rehearsal also found a Phase B false-green boundary: when Node is unavailable the pattern scan reports `SKIPPED`, but the rehearsal can still exit 0. Plan behavior needs a direct-value construction control: caller-supplied capacity summaries must not bypass simulation and validation merely because the plan is instantiated without the planner.

Lifecycle qualification is model-level. Existing lifecycle and resource-limit tests exercise synthetic values and rendered commands; they do not claim that a host runner collected disposal evidence or executed those commands. Runtime production and consumption of those values remain separately scoped evidence.

## What Changes

- Close the extraction rehearsal's missing-tool path so Phase B cannot report success when its required pattern scan is skipped; test missing Node and a present scanner, plus the extracted workspace boundary.
- Qualify job lifecycle transitions, cleanup evidence, quarantine, resource-limit validation/rendering and typed failures using behavioral tests and distinguishing negative controls. Keep host execution evidence separate from model claims.
- Revalidate plan identity, ordered changes and capacity impact on every supported construction/application path, including direct construction from caller-supplied summaries; reject inconsistent values before apply.
- Recover attributable source/test history and produce independently validated, requirement-specific evidence bundles with expected digests before proposing any ledger transition for rows 145–156.

## Impact

Existing requirements `repo-005-01..03`, `fleet-008-01..05`, and `fleet-002-01..04`; extraction rehearsal, fleet lifecycle and plan/apply tests; and DG-02 reconciliation. No new normative requirement IDs are introduced. This proposal does not claim implementation, historical closure or a state transition.
