# Contract & Fixture Inventory (fw-floor-01, R9)

Every contract the project enforces maps to the test path that locks it.
Unmapped claims belong in the README's verification table discipline
(GREEN requires a hosted run; anything else is OPEN with a reason).

Current floor state: 52 suites, 763 tests; floors in
`tests/expected-counts.json` (CI 'Test-count floors' step fails on shrinkage).

## Suite inventory (count at inventory time)

- `tests/test_coherence_local_wrapper.py` — 14 tests
- `tests/test_coherence_workflow_template.py` — 11 tests
- `tests/test_evidence_integrity.py` — 20 tests
- `tests/test_findings_to_spec.py` — 5 tests
- `tests/test_fw_guards.py` — 7 tests
- `tests/test_game_regression.py` — 6 tests
- `tests/test_gate_overlay.py` — 7 tests
- `tests/test_hub_alerts.py` — 9 tests
- `tests/test_hub_coherence.py` — 48 tests
- `tests/test_hub_coherence_adoption_ledger.py` — 10 tests
- `tests/test_hub_coherence_adoption_policy.py` — 31 tests
- `tests/test_hub_coherence_allowlist.py` — 4 tests
- `tests/test_hub_coherence_antirollback.py` — 17 tests
- `tests/test_hub_coherence_assertion_schema.py` — 15 tests
- `tests/test_hub_coherence_attestation.py` — 32 tests
- `tests/test_hub_coherence_cache.py` — 26 tests
- `tests/test_hub_coherence_conformance.py` — 30 tests
- `tests/test_hub_coherence_container.py` — 34 tests
- `tests/test_hub_coherence_decision.py` — 6 tests
- `tests/test_hub_coherence_evidence.py` — 10 tests
- `tests/test_hub_coherence_exitcodes.py` — 34 tests
- `tests/test_hub_coherence_fw.py` — 15 tests
- `tests/test_hub_coherence_invoke.py` — 9 tests
- `tests/test_hub_coherence_issue.py` — 17 tests
- `tests/test_hub_coherence_ladder.py` — 8 tests
- `tests/test_hub_coherence_launcher.py` — 34 tests
- `tests/test_hub_coherence_modes.py` — 18 tests
- `tests/test_hub_coherence_modes_cli.py` — 6 tests
- `tests/test_hub_coherence_normative.py` — 3 tests
- `tests/test_hub_coherence_report.py` — 9 tests
- `tests/test_hub_coherence_retention.py` — 14 tests
- `tests/test_hub_coherence_runtime.py` — 17 tests
- `tests/test_hub_coherence_schema.py` — 24 tests
- `tests/test_hub_coherence_store.py` — 7 tests
- `tests/test_hub_coherence_verify_cli.py` — 12 tests
- `tests/test_hub_enroll_heartbeat.py` — 6 tests
- `tests/test_hub_monitor.py` — 12 tests
- `tests/test_hub_registry.py` — 9 tests
- `tests/test_hub_spec_coherence.py` — 13 tests
- `tests/test_hub_watchdog.py` — 8 tests
- `tests/test_metamorphic.py` — 24 tests
- `tests/test_python_root_anchor.py` — 7 tests
- `tests/test_quickstart_init.py` — 4 tests
- `tests/test_regression_check.py` — 27 tests
- `tests/test_regression_corpus.py` — 14 tests
- `tests/test_regression_sizes.py` — 5 tests
- `tests/test_resource_governance.py` — 18 tests
- `tests/test_runner_enroll.py` — 20 tests
- `tests/test_scope_contract.py` — 5 tests
- `tests/test_silent_success_gate.py` — 4 tests
- `tests/test_silent_success_overlay.py` — 6 tests
- `tests/test_spec_traceability.py` — 12 tests

## Claims without locks (must stay empty)

Audited 2026-09-23: no unmapped claims found. The README verification
table cites hosted runs; the trust-surface claims cite
`docs/threat-model.md` A1-A12, each of which cites a test path.

## Key contract -> test map (high-value subset)

- Strict spec validation refuses malformed material -> `specs job + specs-validate-negative-control.sh`
- Scanner root containment -> `tests/test_python_root_anchor.py`
- Evidence tamper + containment + fail-closed verify -> `tests/test_hub_coherence_fw.py, tests/test_hub_coherence.py`
- Attestation signer-set/revocation/substitution -> `scripts/negative_controls.py nc-10, tests/test_hub_coherence_conformance.py`
- Policy anti-rollback -> `scripts/negative_controls.py nc-09`
- Decision claims cannot self-verify -> `tests/test_evidence_integrity.py`
- Scope contract singularity + cache-tree exclusion -> `tests/test_scope_contract.py`
- Allowlist growth advisory -> `tests/test_fw_guards.py`
- Exec-bit integrity -> `tests/test_fw_guards.py + CI 'Exec-bit integrity' step`
- Fleet path (enroll/heartbeat/revoke/restart/watchdog) -> `scripts/fleet_drill.py`
- Decision determinism -> `scripts/determinism_drill.py (CI: 30 runs)`
- Mutation strength (evidence module) -> `CI 'Mutation strength on evidence module' (21/21)`
- Benchmark corpus validity (both directions) -> `CI benchmark steps`
- Test-count floors -> `CI 'Test-count floors' + tests/gen_floors.py`
