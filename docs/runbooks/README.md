# Runbooks — Operational Recovery

These runbooks describe the IMPLEMENTED mechanisms only: every command
references code that exists in this repository and behavior covered by
tests or drills. Where a capability is not yet built (S5/S6/S7 remainder),
the runbook says so instead of describing an aspiration.

| Runbook | Scenario | Verified by |
|---|---|---|
| [hub-outage.md](./hub-outage.md) | hub down / poll loop wedged | `scripts/fleet_drill.py` (19 steps, incl. watchdog on dead hub, restart persistence) |
| [policy-rollback-and-key-rotation.md](./policy-rollback-and-key-rotation.md) | rolled-back policy bundle; signer key rotation + emergency revocation | `scripts/negative_controls.py` nc-09/nc-10; `tests/test_hub_coherence_attest.py` |
| [evidence-and-attestation.md](./evidence-and-attestation.md) | verifying/transporting sealed decisions; tamper, substitution, partial upload | `tests/test_hub_coherence_store.py`; `scripts/determinism_drill.py` (100/100 byte-identical) |

## Fast triage

| Symptom | First command | Likely runbook |
|---|---|---|
| spoke watchdog unit failing | `bash scripts/hub-watchdog.sh` | hub-outage |
| coherence exit 31 "policy rollback" | inspect context floor vs bundle epoch | policy-rollback-and-key-rotation |
| `--verify` exits 1 | read the stable reason it prints | evidence-and-attestation |
| benchmark/control says INVALID | fix the task's hidden verifier first | `.benchmarks/README.md` |

## Known external dependencies (not coverable by runbooks yet)

- Registry publishing of the pinned evaluator image (needs credentials;
  the CI container-image job degrades to an explicit SKIPPED without
  podman, never a silent pass).
- GitHub-side enforcement boundaries — required checks / rulesets /
  promotion controllers (coh-pol-07) — need repository admin authority.
- Fleet pilots on real repos (R9 provenance) need owner approval per the
  sprint invariants.
