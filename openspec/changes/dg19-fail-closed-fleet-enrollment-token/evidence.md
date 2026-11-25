# DG-19 baseline evidence

Independent source review of AIGGP draft #41 at
`6b08ee17b1309aba241f7156b9b9277fb37e4270` found an empty installation-token
branch in `.github/workflows/fleet-app-enroll.yml` that selects the repository
workflow identity. The following shell statements publish the token and mode
as workflow step outputs. No credential value or live enrollment request was
used to establish this finding.

The reconciler's local sealed-value and redacted-report controls belong to
DG-05. They do not cover the issuing action or the workflow's token selection
and file output. Implementation and transport evidence are pending.

## Local workflow revision evidence

- The preflight step now names a missing `vars.DEVGATE_SWEEP_APP_ID` or
  `secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY` and exits before token issuance.
- The workflow no longer chooses `github.token`, creates an `auth` step, or
  writes a second token/mode pair to `$GITHUB_OUTPUT`. The existing pinned
  `actions/create-github-app-token` output is passed directly into
  `FLEET_APP_TOKEN` for the reconciler, whose shell step rejects an empty value
  before launching Python.
- `tests/test_fleet_app_enroll_workflow.py` executes the workflow-authored
  preflight and reconciliation shell blocks with inert values and a fake
  `python3` process. It exercises both missing pair halves, an empty minted
  token, and a valid environment-only handoff. It does not invoke the issuer,
  contact GitHub, or claim a live enrollment.

### Issuer-owned file transport remains unresolved

The action is pinned to
[`fee1f7d63c2ff003460e3d139729b119787bc349`](https://github.com/actions/create-github-app-token/tree/fee1f7d63c2ff003460e3d139729b119787bc349).
Its official bundled source calls `core.setOutput("token", token)` and, with
the existing default token-revoke lifecycle, `core.saveState("token", token)`
in [`dist/main.cjs`](https://github.com/actions/create-github-app-token/blob/fee1f7d63c2ff003460e3d139729b119787bc349/dist/main.cjs#L47738-L47743).
The same pinned bundle implements those operations by writing to
`GITHUB_OUTPUT` and `GITHUB_STATE` respectively
([output implementation](https://github.com/actions/create-github-app-token/blob/fee1f7d63c2ff003460e3d139729b119787bc349/dist/main.cjs#L45454-L45460),
[state implementation](https://github.com/actions/create-github-app-token/blob/fee1f7d63c2ff003460e3d139729b119787bc349/dist/main.cjs#L45505-L45510)).
This is issuer-owned runner transport, not the removed workflow-authored
duplicate. Because the existing file-handling requirement may include these
raw action outputs, fleet-app-08 / `fleet-enroll-auth-02` all-secret transport
acceptance remains **OPEN / NOT_RUN** pending disposition of that boundary.
The pinned action, post-step revocation lifecycle, and current ecosystem are
unchanged; no local test claims to verify the action's internal files.

No real App credentials, installation token, enrolled repository, or live
workflow run was used.

## Verification after review feedback

The focused workflow and reconciler tests pass together (21 passed). The
workflow fixture now checks credential substrings in every fake-reconciler
argument, confirms its disposable `RUNNER_TEMP` is empty, writes only the
inert `handoff-checked` receipt, and skips cleanly when Bash is unavailable.
The pinned strict OpenSpec 2.2.0 validator passes for both DG19 and the DG05
evidence follow-up. `scripts/evidence_claim_check.py --root . --allow
docs/evidence-claim-allowlist.txt` passes (1125 files scanned; 0 unevidenced
markers). The action-owned `GITHUB_OUTPUT` / `GITHUB_STATE` boundary remains
open as stated above.

A disposable full-history LF clone also passed
`python3 scripts/regression_check.py --all --pre-commit`: no potential
regressions, 0 hard-limit violations, and 0 scope gaps. Existing repository
size-limit warnings remain outside this change.

The combined lead candidate passed 29 focused enrollment and drift tests.
Its exact PR range passed the existing content and committed-range corruption
checks, and the evidence-claim gate reported zero unevidenced markers.
The issuer file transport and live enrollment remain open.
