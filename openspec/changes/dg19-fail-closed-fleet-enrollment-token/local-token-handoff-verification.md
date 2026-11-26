# DG-19 local token-handoff verification checkpoint

**Reviewed tree:** public GitHub `main` was observed on 2026-11-26 at `1b29c5ae1715cee7e2297654f9418dc429c5f5c1`. The worktree is detached at this commit. Hashes below are SHA-256 of raw Git blob bytes from that commit, read with `git cat-file blob <commit>:<path>`.

## Workflow-authored handoff fixtures

I ran `python3 -m pytest tests/test_fleet_app_enroll_workflow.py -q` in a Linux container with networking disabled: **6 passed, 0 skipped**. The tests execute the workflow-authored Bash blocks using inert App ID/private-key/token strings and a fake `python3` reconciler. They cover both absent App-pair halves, a synthetic configured pair, an empty minted-token refusal before the fake reconciler starts, and a valid synthetic environment-only handoff. Assertions verify credential strings do not appear in captured output, fake reconciler arguments, temporary report files, or the fixture’s `GITHUB_OUTPUT` / `GITHUB_STATE` files; the valid path writes only a status receipt. A static workflow-contract test checks that the pinned action output feeds `FLEET_APP_TOKEN` directly, and that the workflow has no `github.token` fallback or workflow-authored `$GITHUB_OUTPUT` write.

The reconciler suite was also run separately: `python3 -m pytest tests/test_fleet_app_enroll.py -q` — **18 passed, 0 skipped**. Together the two focused suites reported **24 passed**. The reconciler tests use an in-memory `FakeGitHub`; the workflow tests use synthetic values and a stub process. Neither invokes the issuer action, mints a real token, contacts GitHub, or enrolls a repository.

## Boundary that remains open

DG-19 task 2.1 remains open for the issuer-owned output/state transport acceptance. The test files exist only during the fake shell run; they do not execute `actions/create-github-app-token` or observe its runner-managed `GITHUB_OUTPUT` / `GITHUB_STATE` writes. The pinned action’s internals, actual App configuration, configured issuer permissions, real token issuance, live workflow run, and configured fleet result remain **NOT_RUN** in this checkpoint. No credentials or production request were used. DG-19 task 2.2 also remains open pending independent review and the required final integration checks.

DG-05 is a separate domain: its local `FakeGitHub` reconciler behavior and missing configured signer-set evidence are recorded in [the DG-05 checkpoint](../dg-05-fleet-app-enrollment-traceability/local-enrollment-verification.md). A green reconciler fixture is not proof of the issuer boundary.

## Raw source fingerprints

| Path at reviewed commit | Raw-blob SHA-256 |
|---|---|
| `openspec/changes/dg19-fail-closed-fleet-enrollment-token/tasks.md` | `b5c5f701fe4f6531e6b9bfd3c0008f39697088972c8b98dfb726a09c0070d1a3` |
| `openspec/changes/dg19-fail-closed-fleet-enrollment-token/evidence.md` | `1ce0f3513b45107db386f25ea506fdd674e44cb481c8ff3a33c54c9b495f331f` |
| `openspec/changes/dg19-fail-closed-fleet-enrollment-token/specs/fleet-enrollment-token-handoff/spec.md` | `f63637df1dd049ab18aa432b2565ab2a5195a4c17e43dd8ce8437a1d50fb6bfb` |
| `.github/workflows/fleet-app-enroll.yml` | `a5b47bbfa84519281a6630e2942614f1f0eefaa8bf09de7e9a3266e546ffad7f` |
| `tests/test_fleet_app_enroll_workflow.py` | `dc7a37207d84f151ba38d16ae561720930d612e7dd7d5276f0b01250831fb41a` |
| `tests/test_fleet_app_enroll.py` | `e655b8173b9f9f9c9d83ea2f421fc7d4a395956d23df54c2ca17c38b7c641263` |

No workflow, issuer, trust configuration, credential, live repository, or production state was changed.
## Repository checks on this snapshot

- The CI-pinned OpenSpec 1.14.3 validator passed all 81 current items. An independent Linux replay against main a3090bbb3706803f2aec908e3beab08b74848724 also passed both fixture suites (24 tests), index, Spec State, and corruption checks.
- `python3 scripts/spec_index.py --check` and `python3 scripts/spec_state_gate.py` passed.
- `python3 scripts/evidence_claim_check.py --root . --allow docs/evidence-claim-allowlist.txt` passed: 1,172 files scanned, zero unevidenced markers.
- `python3 scripts/regression_check.py --all` passed with existing repository size warnings.
- `git diff --cached --check` passed for the staged DG-19 checkpoint.