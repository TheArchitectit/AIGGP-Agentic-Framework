# DG-05 local enrollment verification checkpoint

**Reviewed tree:** public GitHub `main` was observed on 2026-11-26 at `1b29c5ae1715cee7e2297654f9418dc429c5f5c1`. The worktree is detached at this commit. Hashes below are SHA-256 of raw Git blob bytes from that commit, read with `git cat-file blob <commit>:<path>`.

## What the local fixtures establish

The existing [`traceability-map.md`](traceability-map.md) maps canonical `fleet-app-01` through `fleet-app-09` to reconciler code, workflow checks, tests, and CI. At the reviewed commit, I ran `python3 -m pytest tests/test_fleet_app_enroll.py -q` in a Linux container with networking disabled: **18 passed, 0 skipped**. The fixture uses an in-memory `FakeGitHub`, disposable test keys, and temporary report paths. It covers repository pagination and untrusted next-link refusal, archived-repository skip, variable create/update/no-op, secret create/retain/rotate, dry-run, per-repository failure isolation, redaction, invalid/missing inputs, and workflow contract checks.

This is hermetic reconciler evidence only. It does not show that a configured GitHub App can enumerate or update any real repository, nor does it prove that the scheduled/manual workflow ran. No live fleet or credential was accessed.

## DG-05 acceptance still open

DG-05 task 2.2 remains open. No approved signer set or signed, requirement-specific evidence bundle bound to this commit and test result is supplied in the owning change. The local pytest result is neither a signed attestation nor a live run. Do not substitute synthetic signer material or mark `fleet-app-11` terminal from this run. The owning change’s `evidence.md` and `traceability-map.md` retain those limits.

## Raw source fingerprints

| Path at reviewed commit | Raw-blob SHA-256 |
|---|---|
| `openspec/changes/dg-05-fleet-app-enrollment-traceability/tasks.md` | `2fc7149c50cead70f0e5ffd91fc68fd821d310e958b611854843581ea08db9df` |
| `openspec/changes/dg-05-fleet-app-enrollment-traceability/evidence.md` | `4ec1d7cd8aae61eaaa4d93eb973714e73bb1556f07a5f811f16567de7b55dbd8` |
| `openspec/changes/dg-05-fleet-app-enrollment-traceability/traceability-map.md` | `7975c794a3a0851404e61caf38ec80623becee65dcb76d566dd4b364d14f7713` |
| `openspec/specs/fleet-app-enrollment/spec.md` | `684f6a418ab30204b8a14c1ec4dee186169b960cd2008282fb199b6ba45c2d22` |
| `scripts/fleet-app-enroll.py` | `cd3e2db155028dbb02d810ccff966342513377c79b84152ee9e17e48afe3a110` |
| `.github/workflows/fleet-app-enroll.yml` | `a5b47bbfa84519281a6630e2942614f1f0eefaa8bf09de7e9a3266e546ffad7f` |
| `tests/test_fleet_app_enroll.py` | `e655b8173b9f9f9c9d83ea2f421fc7d4a395956d23df54c2ca17c38b7c641263` |

DG-05 remains distinct from DG-19: this file records reconciler behavior and the missing configured-signer/live evidence. DG-19 separately records the workflow issuer/token handoff boundary.
## Repository checks on this snapshot

- The CI-pinned OpenSpec 1.14.3 validator passed all 81 current items. An independent Linux replay against main a3090bbb3706803f2aec908e3beab08b74848724 also passed both fixture suites (24 tests), index, Spec State, and corruption checks.
- `python3 scripts/spec_index.py --check` and `python3 scripts/spec_state_gate.py` passed.
- `python3 scripts/evidence_claim_check.py --root . --allow docs/evidence-claim-allowlist.txt` passed: 1,172 files scanned, zero unevidenced markers.
- `python3 scripts/regression_check.py --all` passed with existing repository size warnings.
- `python3 scripts/spec_traceability.py` is advisory: 261/304 covered; `fleet-app-10` and `fleet-app-11` remain uncovered, consistent with the missing signed evidence.
- `git diff --cached --check` passed for the staged DG-05 checkpoint.