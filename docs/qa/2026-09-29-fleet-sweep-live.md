# Fleet sweep — first live runs (Sprint 1 exit evidence)

Date: 2026-09-30 (UTC). Package: `secret-gate-rollout`, Sprint 1
(SGR-07..12, SGR-16/17/18). Workflow:
`.github/workflows/secret-fleet.yml`, dispatched on `main` via
`workflow_dispatch` (PRs #23/#25/#26 were merge vehicles only — hard rule
#2: no PR review gate was bypassed; merge-commits, so branch SHAs stay
reachable).

## Runs in sequence

| Run | Head | Outcome | What it proved |
|---|---|---|---|
| [36646490542](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36646490542) | `dcadae43` | red at generator | exit 2 named itself correctly: `gh is not on PATH` — the stock `actions-runner` image carries git/python/sudo but not gh. A scanner that did not run is not a clean fleet. |
| [36648098397](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36648098397) | `50e9844` | red (fleet + 4 defects) | full fleet walked; drift/advisory/protection semantics and the alert body exposed four report defects, fixed in `9dab11e` (PR #26). |
| [36655872300](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36655872300) | `4753b5b2` | red — the fleet speaking | report semantics verified correct end-to-end; the red is 58 real findings-repos plus 69 real advisory gates. |

## Pins (verified by sha256 against the release asset, locally, before pinning)

- `actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09` # v5
- `actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349` # v2
- `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` # v4
- gitleaks `8.30.1` — tarball sha256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` + version assert step
- gh CLI `2.101.0` — tarball sha256 `9bca2d1c16825f109907a23307628a2f0698fbf99662b73a5cf0b020293072b8`

## Sweep census (run 36655872300)

- states line: `declared=133, scanned=129, clean=71, findings=58, unfetchable=4, unscannable=0`
- count parity (T-11): **passed** — independently recomputed expected count matched the generated declaration; the App token (`token_mode=app`) listed the owner scope.
- T-31 census: `T-31 census: clean` printed by the commit step before the report landed.
- first committed trend line: `docs/qa/fleet-sweeps/2026-09-30.json` (286KB trimmed copy; night one accidentally committed 80MB and is history — see Residual).
- full report: run artifact `secret-fleet-report` (90-day retention), 80.5MB.

## Sprint 0.1

Reused the existing **Mission Control CI/CD** GitHub App (ID 2550930,
installed All-repositories, contents r/w) rather than minting a dedicated
sweep App — architect's choice. Config lives as repo `vars.DEVGATE_SWEEP_APP_ID`
+ `secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY`; the key was streamed AI02→GitHub
and never touched local disk, chat, or logs. Accepted risk: a leaked sweep
key yields fleet-wide repo contents via the control-plane app.

## Semantics-fix verification table (9dab11e → run 36655872300)

| Defect (run 36648098397) | Fixed behavior | Measured |
|---|---|---|
| drift[] counted 128 ungated repos as divergence | `ungated[]` informational; drift[] = hash divergence only (SGR-06) | `drift=0, ungated=126` |
| advisory grep matched prose ("true" near the string) | key-form check: `continue-on-error:` mapping, value after colon, comments stripped | 69 entries, all real mappings; our own prose no longer matches |
| protection said `unknown` for everything (hardcoded `main`, all errors collapsed) | default-branch lookup + HTTP-status vocabulary; 404 = unprotected | `16 unprotected / 111 unknown` — and 111 is the **plan's truth**: the App token gets HTTP 403 "Upgrade to GitHub Pro or make this repository public" on private repos (free plan: branch protection is premium-only, per-repo). OQ3's degradation reads correctly: 16 repos (all public) answer 404→unprotected; the 111 unknowns are private repos spot-checked at 4 (castforge, AIREPO01, centrallogging, BiteClub → all HTTP 403 paywall). |
| alert body quoted 478k locations → GitHub 422 → dedupe marker dropped | body caps at 40 locations + artifact pointer | issue #24 has exactly 1 comment (this run's recurrence); no 422 in logs; body ≤8KB |

## Findings inventory (the fleet speaking — Sprint 2/3/4 input)

- **58 repos with uncovered findings**, 478,452 locations total.
  Dominant shapes: the guardrails-template doc-token spread
  (`docs/MCP_TOOLS_REFERENCE.md`, `TEAM_TOOLS.md`, `TROUBLESHOOTING.md`
  curl-auth-header lines — vendored into many game repos, retired template's
  warn-only era), `generic-api-key` in `cpofopencode`, ROADMAP/USAGE doc
  examples, and committed credential files (`homelabrepo01:
  ssh_keys/id_rsa` — private-key rule, top of the Sprint 2 rotation list).
- **4 unfetchable**: `rad-gateway`, `radcode`, `RADICAL-CODE`,
  `stitcher-codereview` — "Repository not found" (deleted since the org
  scan); they keep the run red until the declaration's include list is
  dispositioned.
- **69 advisory gates** (`continue-on-error: true` in shipped workflows),
  57 of them in `openclaw` — the SGR-16 triage backlog.
- **1 ungated exception**: `agent-guardrails-template` vendors the gate;
  its `gate_sha256` matches canonical exactly (`3fe86be5…`), so the one
  consumer repo already adopted proves the drift machinery on a real tree.

## T-13 (token-leak grep) — PASS

Grep over the full 80.5MB artifact for `gh[pousr]_`, `x-access-token:…@`,
`xox[baprs]-`, `AKIA`, `sk-`, `Bearer …` value shapes: **zero matches**.
Findings carry rule/path/line/commit only; values never crossed the gate's
redaction boundary into the fleet report.

## Stated assumptions (hard rule #5)

1. `REAL_INCLUDE_COUNT=7`: `fleet-sweep-include.txt` carries seven
   hand-picked URLs; all were live at declaration time. Count parity
   treats include-lines not already covered as +N; no silent drop fired.
2. gh-not-in-runner-image: provisioning gh in-workflow (pinned+hashed)
   rather than baking it into the runner image — the image is shared with
   other DevGate workflows; the runner-side bake is a later host-maintenance
   item, not a gate dependency.
3. The 60-minute `timeout-minutes` was measured sufficient: clones ~30min
   + drift/protection ~2min + rest <1min on both full walks. The heavier
   two-call-per-repo drift step did not push it near the ceiling.
4. Unfetchable ≠ gone forever: the 4 deleted repos stay declared-red until a
   human dispositions the include file — the sweep refuses to forget silently.

## Residual / owner-only

- Night one's 80MB report commit (`d56270f`) is permanent history unless
  scrubbed; sizes since are ~300KB. Recorded as a known self-inflicted
  incident — the trim rule that caused the redo is in the same commit as
  this evidence.
- The **111 unknown protection entries are a plan limitation** (GitHub free
  tier), not a scanner gap: SGR-17 coverage on private repos requires
  GitHub Pro per-repo (or public). Closeout must carry this as residual
  risk, not as a fixed finding.
- Rotation items from Sprint 0 stay owner-only (889/669/890/123, sweep App
  key hygiene).
