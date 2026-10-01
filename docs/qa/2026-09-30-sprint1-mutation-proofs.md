# Sprint 1 mutation proofs — T-14 / T-15 / T-08 (2026-09-30)

Hard rule #4 shape. These are mutation PROOFS, not an adoption: the
fixtures are synthetic and live on scratch repos that get deleted when
this doc lands (see Cleanup). No secret value appears here — T-15's
canary was generated locally, streamed into a base64 contents-API
payload, and never printed.

## Proof run

- **Run:** https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36665701043
  — `workflow_dispatch` on ref `devgate/secret-gate-adoption` @ 03:43:46Z,
  completed **failure** @ 04:16:29Z (~33 min walk). Red is the PASS
  condition here: the branch carries the two probe declarations (4b30b46)
  and the fixed `hub_alert.py` (0ebb4e8), both merged to main via PR 28.
- Dispatch on the branch ref was deliberate: it exercises the FIXED
  alerting code in a live run before trusting tonight's nightly with it.

## Census (from this run's `secret-fleet-report` artifact, locations only)

declared=135, scanned=131, clean=72, findings=59, unfetchable=4,
unscannable=0, ungated=127 (informational per SGR-10), locations ≈ 478k.
The 478k count is the pre-existing fleet backlog (see
2026-09-29-secret-scan-fleet-first-run.md), not new.

## T-15 — canary found → red run → dedupe (test matrix clause 1–2)

- Fixture: `TheArchitectit/devgate-sgr-t15-probe` (private scratch repo),
  one synthetic `SGRCANARY<40 hex>` line planted via the contents API in
  commit `368f59081cc0` at `.sgr-canary.env:2`.
- Proof: report shows the repo `state=findings`, locations
  `generic-api-key .sgr-canary.env:2` for both working tree and the
  planted commit SHA. Fail-step routed on `sweep rc=1` (log:
  `[fail] sweep rc=1 drift step outcome=success`) → run red.
- Dedupe clause: alert did NOT open a new issue — it commented on the
  existing open issue #24 (`[devgate-monitor] secret_fleet_sweep`).
  Issue #24 now carries two comments: 02:08 (main run 36655872300) and
  04:16 (this proof run). One issue, recurrence comments it.
- Value hygiene: grepping the run's full log for the canary prefix
  returns nothing — the report redacts values, locations carry
  rule+path+line+commit only.

## T-08 — tampered vendored gate → drift names it with both hashes

- Fixture: `TheArchitectit/devgate-sgr-t14-probe` (private scratch repo),
  its `scripts/secret-scan.sh` replaced via contents API with the
  canonical gate carrying ONE tampered byte (commit `90364efec7a9`).
  Canonical (branch copy): `3fe86be54d63…51c0` (verified by
  `sha256sum scripts/secret-scan.sh` at 0ebb4e8's tree); tampered copy:
  `11bb4b20d76d…cae`.
- Proof: report `drift[]` has exactly one entry:
  `repo=devgate-sgr-t14-probe, gate_sha256=11bb4b20d76d…,
  expected=3fe86be54d63…, note="vendored gate hash diverges from the
  canonical copy"` → drift step succeeded computing, fail-step reddened
  the run on `drift_has_divergence` (SGR-06 semantics).
- **Stated finding (assumption, hard rule #5):** the alert BODY names
  locations and unfetchable holes but not drift entries — the drift repo
  is named in the report artifact and the red run, not in issue #24's
  comment. The T-08 matrix clause ("next fleet sweep names the repo with
  both hashes") is met by the report; extending `detail_from_report`
  with a drift section is the same one-block change the T-14 holes
  section was. Filed as follow-up below rather than worked around.

## T-14 — unfetchable repos named in the alert body

- Fixtures: `definitely-not-a-repo-sgr-t14-31365` (include-line
  declaration, proven locally before this window) plus four genuinely
  vanished repos the walk found: rad-gateway, radcode, RADICAL-CODE,
  stitcher-codereview.
- Proof: issue #24's 04:16 comment contains the new section, verbatim
  shape: `could not be scanned (name — reason):` naming all four with
  `unfetchable: could not fetch: remote: Repository not found.` —
  the fix 0ebb4e8 added, exercised live for the first time. The
  02:08 comment (pre-fix main run) only counted them.
- Census consistency: unfetchable=4 counted in summary, 4 named in body.

## Recurrence proof (T-15 clause 2, "same issue, second failing night")

The matrix's two-failing-nights scenario is mechanically satisfied by
**two consecutive failing runs**, and this window produced exactly that
without waiting for the clock: run 36655872300 (main, findings backlog,
red) alerted at 02:08:02Z commenting issue #24, and proof run 36665701043
red again at 04:16:23Z — the dedupe path opened NOTHING new and appended
a second comment to the same issue. #24 is 3145 bytes → 3493 bytes,
comment count 1 → 2.

Note the scheduled nightly cannot prove T-15/T-08 recurrence: the probe
declarations (4b30b46) live on this branch only, never on main, and the
last nightly main saw was 01:35Z (pre-fix). The T-08 drift repo and T-15
canary exist on branch-scoped declarations precisely so the fleet on main
is never dirtied by fixtures.

## Cleanup (task #2 closeout)

- Probe lines removed from `fleet-sweep-include.txt`.
- The generator unions the LIVE owner listing with the include file, so
  include-removal alone does not drop still-existing repos from the
  declaration (commit-parity would have reddened the next sweep). Both
  probes therefore added to `fleet-sweep-exclude.txt` with reasons —
  declaration now 133 = 129 scanned + 4 unfetchable, zero `sgr-t1`.
- Repo deletion blocked on the `delete_repo` gh scope (interactive
  refresh needed). Outcomes, stated: `gh repo delete
  TheArchitectit/devgate-sgr-t14-probe --yes` and the t15 repo, then
  revert both exclude lines (leaving them is a quiet hole per the file's
  own header).

## Follow-ups filed

1. `hub_alert.detail_from_report`: add a capped `drift[]` section
   (repo + got/expected hashes, 12-hex truncate, same shape SGR-06 uses)
   so drift is named in the alert body, not only the artifact.
2. Nightly on main stays red from the pre-existing 58-repo findings
   backlog — SGR-10's informational rule covers ungated, not findings;
   triage is Sprint 2/3 adoption work, tracked in the rollout package.
