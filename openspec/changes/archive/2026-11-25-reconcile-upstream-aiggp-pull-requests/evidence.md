# Upstream intake and final merge evidence

**Evidence updated:** 2026-11-26 UTC. **Initial intake observed:** 2026-11-25
local time. Current-state claims below are bounded to the GitHub/API snapshots
and commits named here; older states and receipts remain historical.

Upstream is `TheArchitectit/AIGGP-Agentic-Framework`. The intake snapshot used
`main` at `2bf84ddab55695340e91ceb026b319fcae7de3e4`. At intake, GitHub showed
#32/#33 open and conflicted, and #46/#47/#48 open drafts. This describes only
the November 25 snapshot, not their final or present disposition.

## Initial intake snapshot — November 25, 2026

| PR | Intake head / base | Change and initial receipt |
| --- | --- | --- |
| [#32](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/32) | `8ee6f7c1dc771991c607bb25af6d914d39603e46` / `b4de795201bb07e650552b01e6607464380c106d` | Toolchain tasks and evidence. [October CI passed on this older head](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/40051060624). |
| [#33](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/33) | `951af6314cf856954bd781304ecdeb536ad9bda3` / `b4de795201bb07e650552b01e6607464380c106d` | Historical GitLab discovery note. [October CI passed on this older head](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/40051994882). |
| [#46](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/46) | `c854ddae78237a0e96ccfe4dc8c729e2e74b7ed5` / `2bf84ddab55695340e91ceb026b319fcae7de3e4` | DG-22 release planning. [CI passed](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45724643650). |
| [#47](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/47) | `fb6af3aa5d8aa5595035c59efec7b913ad5484d8` / `2bf84ddab55695340e91ceb026b319fcae7de3e4` | DG-02 candidate provenance covering 182 `UNPROVEN` rows. [CI passed](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45724645907). |
| [#48](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/48) | `aa3e2f6012f49f38f1572491bdcbb1e0413c1064` / `2bf84ddab55695340e91ceb026b319fcae7de3e4` | DG-21 process-launch handling and OpenSpec. [Initial CI failed at failure-registry hygiene](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45724712482); the reproduced registry record had no implementing commit at intake. This was later corrected and superseded. |

## Review and reconciliation evidence

- At intake, OpenSpec 1.14.3 strict validation passed on the pinned `main`
  (75/75), #46 (76/76), and #47 (75/75). The six applicable jobs on #46 and
  #47 passed, including tests, DevGate, and OpenSpec with traceability.
- #47 merged as `8e42f7b066894801440781c6ad6e05d894e81832`; all 182 rows remain
  `UNPROVEN`. Row-specific enforcement and test evidence, sealing, and state
  transitions were not established by that provenance-only PR.
- #46 merged as `1070d3ed917c77773019d2c880d1c911769a2d6f`. The pre-existing
  `main` Release Coverage failure remained a separate DG-22 release task. The
  approved plan did not itself publish a release.
- #32's reconciled ancestry reaches
  `72202477a30f307f4dbb68fb371505b596c9347a`. Its only disposition change adds
  historical attribution for tasks 5.0, 5.7, 6.6, and 6.7 in the archived
  package. The capability remains `UNPROVEN`; the old active package path stays
  retired. All six applicable CI jobs passed:
  [run 45742217241](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45742217241).
- #33's reconciled ancestry reaches
  `0ecbf56358621327a383e3bc0568ddad529fd81f`. Its only disposition change
  links the October discovery as history. Later owner decisions govern
  GitLab adoption and scope. All six applicable CI jobs passed:
  [run 45742223987](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45742223987).
- Both reconciliations passed staged-diff review, strict OpenSpec validation
  (75/75 each), scoped regression, and failure-registry hygiene.

## DG-22 rehearsal

The exact Release Coverage Bash step from #46 was run in five isolated fixture
repositories. An annotated tag at `HEAD` with matching changelog notes passed.
An older tag and a missing release heading each failed. A generated-only sweep
diff exercised the exemption. A mixed sweep and product diff used the normal
enforcement path and failed against an older tag. Each fixture's `HEAD` and
refs were unchanged. The rehearsal used synthetic tags only.

## PR #48 follow-up and PR #49 — November 26, 2026 UTC

- #48's runner/workflow implementation was independently reviewed at
  `a41ce6519105aa866207d2d942257f566a593ed2`. Four focused launch controls and
  three workflow receipt controls passed. Follow-up commits added the source
  marker for `gate-test-count-01` and reconciled the evidence and PR summary.
  A concurrent update brought in current `main` and archived DG-21 at
  `afc32a8d0f64808f13501ea77f27044df93ec5d4`; it preserved the runner code and
  workflows. Local validation passed 77 OpenSpec items and 160 checksums.
  The earlier workflow result was superseded. The archive head's
  [CI run 45745222798](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45745222798)
  passed all six applicable jobs and the Open-item check. PR #48 merged at
  `2026-11-26T03:19:39Z` as
  `96632e91ad605970014d900686ae6f62e2762065`.
- In a disposable review, the DG-21 archive head merged cleanly with the audit
  already on current `main`. The integrated tree passed 81 OpenSpec items,
  generated index validation, and traceability (261/303 covered).
- [#49](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/49)
  carried the public future-readiness audit and four OpenSpec packages at
  `31566e535fecc562cf7274638c8d8f1352bba9ce`. Strict validation passed 80 items.
  Independent review, scoped regression, configured pattern scan, registry
  hygiene, and text integrity passed locally. The canonical inventory matched
  66 capabilities and 267 requirements; traceability passed at 259/301 with
  remaining IDs reported as advisory. All six applicable jobs and the Open-item
  check passed. PR #49 merged at `2026-11-26T03:03:28Z` as
  `a1a48a602b1b3b6520e9bdf404f77b1981891f34`.
  [Hosted CI run 45743755213](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45743755213).
- The optional strict pattern scan reported 50 warnings on both the unchanged
  intake baseline and readiness candidate. The configured scan reported zero
  violations; the warnings remained advisory.

## Final verification — snapshot at `96632e91ad605970014d900686ae6f62e2762065`

On 2026-11-26 UTC, GitHub reported `merged: true` for #32, #33, and #46–#49.
The merge receipts are:

| PR | Merged at (UTC) | Merge commit |
| --- | --- | --- |
| #47 | `2026-11-26T02:16:37Z` | `8e42f7b066894801440781c6ad6e05d894e81832` |
| #46 | `2026-11-26T02:18:48Z` | `1070d3ed917c77773019d2c880d1c911769a2d6f` |
| #32 | `2026-11-26T02:43:21Z` | `f58e917a7d75df94473cd1aae31531e338fa3ccb` |
| #33 | `2026-11-26T02:47:26Z` | `36567d0b706a160f64a939ffcffff3bf6c8bdd59` |
| #49 | `2026-11-26T03:03:28Z` | `a1a48a602b1b3b6520e9bdf404f77b1981891f34` |
| #48 | `2026-11-26T03:19:39Z` | `96632e91ad605970014d900686ae6f62e2762065` |

These merges were on the first-parent history of upstream `main` at the
verification snapshot. The final tree matched the disposable tree that passed
81 strict OpenSpec items, generated index validation, and traceability. The
readiness report, four proposed change packages, and published per-file test
runner spec were present at that snapshot. Later upstream commits may have
advanced `main`; the SHA above bounds these claims.

At that snapshot, `VERSION` was `1.3.52` and the annotated release tag targeted
`7d17d6f1baa4357110e57d3a6ffd55fbacdd77f7`. The release remained a separate
DG-22 owner-controlled action.

## Local archive validation — November 25, 2026 Central / November 26 UTC

After archiving this coordination-only change with OpenSpec CLI 1.14.3
(`--skip-specs`, because it adds no capability behavior), strict validation
passed: `validate --all --strict`, 82 items, 0 failures. Telemetry was disabled
and color output suppressed for the recorded run.
