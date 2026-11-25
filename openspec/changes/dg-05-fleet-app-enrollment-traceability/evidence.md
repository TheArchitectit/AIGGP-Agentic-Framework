# DG05 writer evidence

- Baseline worktree revision: `6b08ee17b1309aba241f7156b9b9277fb37e4270`.
- Scope is local to enrollment traceability; no external repository was
  contacted and no live credentials were used.
- Focused tests: `python -m pytest tests/test_fleet_app_enroll.py -q` in
  `aiggp-pr41-lead:20261125` — **PASS**, 18 passed, 0 skipped, after final
  test/source-marker edits.
- Regression scan: `python scripts/regression_check.py --all --pre-commit`
  in a disposable LF-normalized clone with actual, non-shallow Git history at
  the baseline SHA — **PASS**, no potential regressions, 0 hard-limit blocks,
  0 scope gaps. The repository-wide scan reports existing size warnings; this
  file is 497 lines, below the 500-line hard limit but above the 300-line soft
  warning. The first attempt directly mounting the linked worktree failed
  before scanning because its `.git` pointer names an unavailable Windows
  sibling path; it was rerun successfully in the clone.
- Traceability: `python scripts/spec_traceability.py --report` in the pinned
  image — `fleet-app-01` through `-09` covered; `-10` and `-11` uncovered.
  The command exits successfully in advisory mode. Coverage is source-marker
  presence, not a verdict that the map itself is correct or that enrollment
  has run live.
- OpenSpec 2.2.0: `openspec validate
  dg-05-fleet-app-enrollment-traceability --strict` **PASS**. Repository-wide
  `openspec validate --all --strict` **FAILED** with six unrelated existing
  spec warnings promoted to failures (`adapters-and-loops`, `dg-06`, `dg-07`,
  `dg-09`, `reviewer-surfaces`, and `traceability-and-drift`); the DG05 change
  itself validated successfully in that run.
- Sealed bundle and configured-signer attestation: **NOT_RUN**. No approved
  signer set or signing material was supplied for this work. No synthetic
  signer was substituted.
- Live fleet/workflow run: **NOT_RUN**. The full scenario map and evidence
  limits are in `traceability-map.md`.

Independent verification on the laptop passed all 18 enrollment tests and
the blocking regression scan in a disposable Linux Git checkout. The
reconciler's code structure matched the reviewed source. The combined
traceability candidate reported 257/284 covered, including the nine reviewed
enrollment IDs. The source marker result is advisory. The DG-19 plan records
the workflow's open authentication and credential transport findings.

## DG-19 workflow follow-up

DG-19 removed the enrollment workflow's fallback to `github.token` and its
duplicate credential-bearing output. The workflow now rejects a missing
installation token and provides the pinned issuer's selected value directly
to the reconciler environment.

The pinned issuer still returns its token through runner-managed output and
state files. The existing `fleet-app-08` transport acceptance remains open.
The focused shell tests used disposable fixture data. Live enrollment and
configured-signer evidence remain unavailable. [DG-19 source and tests](../dg19-fail-closed-fleet-enrollment-token/evidence.md)
