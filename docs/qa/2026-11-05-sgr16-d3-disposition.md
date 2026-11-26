# SGR-16 D3 — per-repo `continue-on-error` disposition (2026-11-05)

Closes disposition 3 of
[`2026-10-11-secret-fleet-sweep-triage.md`](./2026-10-11-secret-fleet-sweep-triage.md):
*"Per-repo SGR-16 triage for the … in-our-repos advisory entries — each is a
real `continue-on-error: true` to justify, convert, or baseline per repo."*

**No workflow was edited.** Dispositions below are records. Zero keys were
converted, so nothing that changes CI coverage is applied here — consistent with
the triage record's "owner sign-off required — none applied".

## Scope

Measured against `docs/qa/fleet-sweeps/2026-11-05.json` (the live sweep, not the
2026-10-10 figures the triage record was written from).

| | 2026-10-10 | 2026-11-05 |
|---|---|---|
| advisory total | 77 | 84 |
| openclaw (upstream fork) | 57 | 57 |
| **in-our-repos** | **20** | **27** |
| actionable after the RADICAL-CODE exclusion | — | **26** / 9 repos |

Out of D3 scope, named so they are not silently dropped:

- **openclaw, 57 keys** — the upstream-fork noise class. Disposition **1** (D1) in
  the triage record. Not triaged here.
- **RADICAL-CODE, 1 key** (`.github/workflows/ci.yml:385`) — out of scope by
  standing owner exclusion ("radical-code is out side of this scope"). Left
  named, not touched. Note `radcode` (local clone `RADOPENCODE`) is a
  **different repository** and is in scope.

## Method — the verdict-aggregator test

A `continue-on-error: true` key is not automatically an exemption. GitHub records
a step's conclusion as `success` even when the command exited non-zero, so
`gh run view` cannot distinguish "the gate passed" from "the gate failed and the
key swallowed it". Every key below was classified by reading the workflow and, where
the claim was consequential, running the gate command.

The decisive question per key: **is there a fail-closed aggregator that reads this
step's `outcome` and exits non-zero on `failure` / `cancelled` / `NOT RUN`?**

- **Yes** → the key is *aggregation*, not exemption. It exists so the matrix can
  report every row instead of aborting at the first red. Converting it to strict
  would destroy the matrix and add zero coverage. → **justify**.
- **No, and the key gates nothing** (report/upload, failure-path diagnostics, a
  documented non-gating smoke) → **justify**.
- **No, and the key silences a real gate** → evaluate **convert** (only if proven
  safe) or **baseline** (measured known debt + named promotion condition).

### The test is necessary, not sufficient (added 2026-11-05)

Three independent cross-checks of this record converged on the same gap. Every
claim they challenged has since been re-measured here, from the workflow text
and by running the commands. Two rows moved.

The verdict-aggregator test separates *aggregation* from *exemption* correctly —
that is why MergeKingdom, rad-gateway, OpenRawFlow and NemoClaw classified as
they did, and those classifications stand. What the test does **not** answer is
whether the thing being softened is a working check at all. Three questions were
skipped:

1. **Does the exempted job actually run?** A key on a job whose command cannot
   succeed is not exempting a *signal*. It is exempting a *failure*. An in-file
   comment describing intent is not evidence the check works — the comment and
   the command have to be read together.
2. **Is the soft layer's outcome read by anything?** A soft step with no `id:`
   and no aggregator is not "layered detection"; its result is discarded. A
   strict fallback that is a *different, weaker* scanner does not restore it.
3. **A justified key is not a working gate.** The key can be shaped correctly —
   soft so a report step can run, then a fail-closed exit — while the gate it
   aggregates is permanently red and evaluates nothing. "Justify" describes the
   key. It is not a claim that the check is effective, and the two must not be
   read as one.

A standing caveat on top of all three: GitHub records a `continue-on-error`
**step or job** as `success` even when the command exited non-zero. Neither the
Actions UI nor `gh run view` can distinguish "passed" from "failed and
swallowed", at either level. Everything below was taken from the workflow text
and from running the gate command, never from a green tick.

## Disposition table — 26 keys / 9 repos

| # | Repo | Key | Shape | Disposition |
|---|---|---|---|---|
| 1–10 | MergeKingdom | `devgate-gates.yml` 43, 54, 65, 96, 101, 106, 111, 137, 148, 153 | 10 gate steps under `Gate verdict` → `exit $verdict` | **justify** (aggregation) |
| 11–15 | rad-gateway | `devgate-gates.yml` 50, 146, 159, 196, 246 | 5 gate steps under `Gate verdict` → `exit $verdict`; `skipped` also reddens | **justify** (aggregation, stricter) |
| 16 | rad-gateway | `security-scan.yml:206` | `Upload Trivy scan results` (SARIF upload, `if: always()`); the Trivy **scan** is strict | **justify** (report upload) |
| 17 | radcode | `ci.yml:339` | `Record CI health artifact` — re-runs gates to write a report artifact; enforced gates run earlier in the job | **justify** (reporting) |
| 18 | radredeye | `guardrails.yml:61` | job `webxr-wasm32` "WebXR wasm32 build (non-gating)" — its command cannot resolve the crate; Clippy (`-D warnings`) is the strict gate | **owner** (exempts a job that has never compiled) |
| 19 | radredeye | `secret-validation.yml:94` | job `gitleaks-scan` "informational"; enforcing `.env` job beside it | **justify** + promotion debt |
| 20 | radredeye-vision-review | `guardrails.yml:63` | job `cargo-audit`, `TODO(promote-to-blocking)`; Clippy strict | **justify** + promotion debt |
| 21 | radredeye-vision-review | `secret-validation.yml:87` | job `gitleaks-scan` "informational" | **justify** + promotion debt |
| 22 | pi-ithacus-agent-framework | `regression-guard.yml:35` | gate step soft so the PR comment runs; `Fail job if regression failed` → `exit 1` | **justify** (key only — the gate it reports on is dead, see D3-a) |
| 23 | pi-ithacus-agent-framework | `secret-validation.yml:27` | Trufflehog soft, **no `id:`**, outcome never read; the "fallback" is a different scanner | **owner** (exemption, not aggregation) |
| 24 | OpenRawFlow | `devgate-gates.yml:80` | `rustcheck` soft so compile debt cannot hide the 4 scan gates; `RESULTS[rust]` seeded, `exit $FAILED` | **justify** (aggregation) |
| 25 | NemoClaw | `e2e-branch-validation.yaml:251` | `Collect Brev debug bundle on failure`, `if: failure()` | **justify** (failure-path diagnostics) |
| 26 | LobsterWars | `devgate-gates.yml:20` | real gate kept advisory; 13 measured violations | **baseline** |

**Totals (corrected 2026-11-05): 23 justify, 1 baseline, 2 owner, 0 convert.**
Was 25/1/0. Rows 18 and 23 moved from justify to owner; see the method note and
D3-a/D3-b below. Row 22's disposition of the *key* is unchanged and its gate
defect is recorded separately.

## Per-repo evidence

### MergeKingdom — 10 keys, justify (aggregation)

All 10 sit in one job under `Gate verdict (honest matrix — this step decides the
job)` (`devgate-gates.yml:165`), which `exit $verdict`s. `report()` marks
`failure` / `cancelled` / `NOT RUN` as RED and sets `verdict=1`. The file's own
header states the contract: *"continue-on-error alone never greens a job — the
verdict step is the only place the job conclusion is decided."*

Every one of the 10 gate commands was run against the real `.devgate` pin
(`5f20fc73b26e9c98dcc1ad07f097bef3c0565c5b`) rather than trusted from a green
run: **10/10 PASS, 0 failing**. There is no red gate hiding behind the key.

Converting these would abort at the first red and destroy the matrix.

### rad-gateway — 5 keys, justify (aggregation, stricter)

Same design at `devgate-gates.yml:271` (`exit $verdict` at 302). **Stricter than
MergeKingdom**: line 285 sets `verdict=1` on `skipped` as well.

### rad-gateway `security-scan.yml:206` — justify (report upload)

`Upload Trivy scan results` (`github/codeql-action/upload-sarif`), `if: always()` +
`continue-on-error: true`. The Trivy **scan** step itself has no
`continue-on-error` and is enforced. Only the SARIF upload is soft, so an upload
failure cannot mask a scan result. Same class the `sbom` job documents for
artifact quota.

### radcode `ci.yml:339` — justify (reporting)

The key is in the standalone **`health-report:`** job, not in a gate job. Its
step `Record CI health artifact (re-run all gates, keep going on failure)` runs
`scripts/ci_health.py run --all --continue-on-error` and uploads `.ci-health/`;
the key exists so the upload is never skipped. The file states the contract
itself: *"non-blocking observability — the gate/editor/dashboard jobs above
remain the authoritative blocking gates"* and *"Runs after the blocking jobs and
ALWAYS runs (`if: always()`)"*.

Those blocking jobs (`Build + Test + Lint + Guardrails`, `Editor (npm) compile +
lint`, `Dashboard WASM`, `Port regression`) carry the real enforcement —
`Pre-work guardrails check (fast, blocking)` and two `exit 1` paths among them —
and none of them has a key.

> Line numbers only match the GitHub revision. The local clone `RADOPENCODE` was
> last fetched 2026-08-13 and puts the key at line 181/186; the 2026-11-05 sweep
> scanned a 346-line `ci.yml` where it is line 339. Classified against the
> fetched revision, not the stale tree.

### radredeye — 2 keys, one of them not justified

- `guardrails.yml:61` — **owner. Corrected 2026-11-05; was "justify (documented
  signal job)".** The job is named *"WebXR wasm32 build (non-gating)"* and its
  comment describes intent: the webxr crate is excluded from the default
  workspace build because it targets wasm32, so this job is meant to compile it
  on its own target and report only. **The command cannot do that.**

  `Cargo.toml:3` reads `exclude = ["crates/radredeye-webxr"]`. The crate is on
  disk at `crates/radredeye-webxr/Cargo.toml` but is workspace-excluded, so
  from the repo root — as CI runs it —

  ```
  cargo build -p radredeye-webxr --target wasm32-unknown-unknown
  error: package ID specification 'radredeye-webxr' did not match any packages
  ```

  The job has **never compiled anything**. `guardrails.yml` is five independent
  jobs and contains **no aggregator** — no `verdict`, no `steps.*.outcome`, no
  `exit $` anywhere in the file. This key is a plain exemption.

  So it is not exempting a documented signal; it is exempting a failure, and
  `continue-on-error: true` is the only reason the job reads green. The fix is
  `--manifest-path crates/radredeye-webxr/Cargo.toml` or re-including the crate
  in the workspace — either would surface the crate's real compile state and
  could redden the job, so it is an owner call. Re-disposition the key once the
  command works; only then does "documented non-gating smoke" apply.

- `secret-validation.yml:94` — **justify + promotion debt. Unchanged.** Job
  `gitleaks-scan`, named *"Gitleaks scan (informational)"*, job-level
  `continue-on-error: true`, no aggregator. Re-read 2026-11-05 and it still
  holds: the file header gives two reasons and a promotion path (tune
  `.gitleaks.toml`; bake the gitleaks binary into the runner image), and an
  enforced path sits beside it — `check-env-files` exits 1 on a tracked `.env`.
  This is a working check deliberately held soft with the condition written
  down, which is the shape the corrected method still justifies.

### radredeye-vision-review — 2 keys, justify + promotion debt

- `secret-validation.yml:87` — same informational gitleaks shape as radredeye.
- `guardrails.yml:63` — job `cargo-audit` carries
  `# TODO(promote-to-blocking): remove continue-on-error once the dependency tree
  has been triaged against rustsec advisories. Until then this job reports but
  does not block — the gate is wired and running, not yet hard.` This is a real
  gate, deliberately not yet blocking, with the promotion condition written down.

### pi-ithacus-agent-framework — 2 keys, one of them not layered

- `regression-guard.yml:35` — **justify, for the key only. The gate it
  aggregates is dead — see D3-a.** The key's shape is correct and unchanged: the
  gate step (`id: reg`) is soft so `Comment on PR on failure` can run, and the
  job then ends with `Fail job if regression failed` → `run: exit 1` (line 66)
  plus `core.setFailed(...)` in the comment script. Report-then-fail, not an
  exemption. (The job header claims the PR "is blocked" — true only because of
  that later step, not the key.)

  **Do not read "justify" as "the gate works."** The step invokes
  `python3 scripts/regression_check.py --all --pre-commit --soft-as-hard
  --soft-as-hard-base origin/${{ github.base_ref }}`, and `regression_check.py`
  defines neither flag: its argparse accepts only `--registry`, `--rules`,
  `--staged`/`--unstaged`/`--all`, `--pre-commit`, `--json`, `--verbose`,
  `--quiet`, `--validate-agent-bundles`. A direct run exits 2 with
  `error: unrecognized arguments: --soft-as-hard --soft-as-hard-base origin/main`.
  The job is therefore **unconditionally red and evaluates nothing** — the
  aggregator faithfully reports a failure that is a usage error, not a
  regression.

- `secret-validation.yml:27` — **owner. Corrected 2026-11-05; was "justify
  (layered, enforced fallback)".** It is not layered in the sense the method
  requires. The Trufflehog step has `continue-on-error: true`, `uses:
  trufflesecurity/trufflehog@main` (**unpinned**), and **no `id:`** — and a
  grep for `steps.*.outcome` or `id:` across the file returns **nothing**. No
  step reads any other step's outcome.

  So a **verified** secret found by trufflehog does not fail the job unless the
  `Grep fallback (high-signal patterns)` step *also* matches it — and that
  fallback is a different, weaker scanner, not an enforcement of the first.
  The strict `No .env files tracked` step is real but is a third thing. This is
  exemption of a security check, not aggregation.

  Owner call: give the step an `id:` and fail closed on its outcome, or state
  plainly that trufflehog is pure signal and name what the enforced layer
  actually is. Pin the action to a commit either way.

### OpenRawFlow — 1 key, justify (cleanest aggregation in the fleet)

`devgate-gates.yml:80`, step `Rust check (server crate)` (`id: rustcheck`). The
comment states the design outright: *"`continue-on-error` so the compile debt
cannot skip the four scan gates below. The gate suite records this step's outcome
and is what actually fails the job, so a red cargo check is still red — it just
no longer hides the other four results."*

The aggregator seeds `RESULTS[rust]` from `steps.rustcheck.outcome`, runs
`regression` / `guardrails` / `semantic` / `silent-success` via `run_gate`, and
`exit $FAILED` (line 181) with
`[ "${RESULTS[$gate]:-FAIL}" = "PASS" ] || FAILED=1` — unset entries count as
FAIL, so a gate that never ran cannot pass vacuously. Regression is scoped with
`--fail-if-empty` for the same reason.

> Fetched from GitHub: the local `OpenRawFlow` clone (2026-06-17) holds only
> `ci.yml` and predates `devgate-gates.yml` entirely.

### NemoClaw — 1 key, justify (failure-path diagnostics)

`e2e-branch-validation.yaml:251`, step `Collect Brev debug bundle on failure`,
`if: failure()` + `continue-on-error: true`. It runs **only after the job has
already failed** and collects the onboard log, sandbox list, docker state and
gateway status before the Brev VM is torn down. It cannot weaken a gate: its
failure path only exists once something else has reddened. Soft here is correct —
a debug-collection failure must not replace or mask the real failure.

### LobsterWars — 1 key, baseline

`devgate-gates.yml:20`, job `guardrails-scan` / *"Pattern Scan"*:
*"Advisory until pre-existing violations are cleaned up (13 as of 2026-09-17)"*.

The other three jobs in that file (`semantic-scan`, `regression-check`,
`silent-success`) have no key and are strict.

**Baseline re-measured 2026-11-05, not copied from the comment:**
`node .devgate/scripts/guardrails-scan.mjs` → `GUARDRAILS: 13 violation(s) found.`
`rc=1`. The 2026-09-17 count is still exactly accurate.

Converting to strict would redden the job immediately against 13 known
violations, so conversion is **not proven safe**. Disposition is baseline: keep
advisory at a measured 13, and the promotion condition is the one the file
already names — clean the pre-existing violations.

One labelling nuance, recorded so it is not lost. A cross-check would call this
**owner** rather than **baseline**, because the key is job-level on a file with
no aggregator at all and the job is red on main. The action is identical either
way — keep advisory, do not convert, clean the 13 then promote — so the label
does not change what anyone does next. Kept as baseline because the count is
accurate, the scan works, and the promotion condition is written in the file.

## Defects named by the correction (owner call, not applied)

Two of these are the rows that moved. Each would change CI behaviour if fixed,
so neither is applied here.

**D3-a. `pi-ithacus` `regression-guard.yml` aggregates a gate that evaluates
nothing.** The step passes `--soft-as-hard` and `--soft-as-hard-base` to
`scripts/regression_check.py`, which defines neither. The step exits 2 at
argument parsing and the fail-closed step then faithfully exits 1, so the job is
unconditionally red and **no regression rule has been evaluated by this
workflow** for as long those flags have been absent. Fix is either to implement
the flags (they are a real design: treat soft rules as hard against a base ref)
or to drop them from the invocation. Either changes CI behaviour. Until then the
job's red is a usage error, not a regression signal — and its green-when-fixed
would be the first time the gate has actually run.

**D3-b. `radredeye` `guardrails.yml` webxr job cannot compile its crate.**
Row 18 above. `cargo build -p radredeye-webxr` cannot resolve a
workspace-excluded crate, so the job has never produced a build result. Fix
with `--manifest-path crates/radredeye-webxr/Cargo.toml` or by re-including the
crate in the workspace, then re-disposition the key against a job that runs.

**D3-c. `pi-ithacus` `secret-validation.yml` discards trufflehog's result.**
Row 23 above. No `id:`, nothing reads the outcome, action unpinned at `@main`.
Decide deliberately whether trufflehog is enforced or is pure signal, and pin it
either way.

## Secondary findings (named, not applied)

These are gaps in the aggregation designs themselves. Each would change CI
behaviour if fixed, so each is recorded for owner call rather than applied.

1. **MergeKingdom's matrix is green on a skipped gate.** `schema_health`
   (`devgate-gates.yml:151`) handles a missing DB honestly at the step level —
   it writes `outcome=skipped` to `$GITHUB_OUTPUT` and prints
   `SKIPPED (no DB configured — not a pass)`. The verdict step reads it correctly
   (line 195: `steps.schema_health.outputs.outcome || steps.schema_health.outcome`)
   and renders the row as `SKIPPED (not a pass)`. **But `report()` only sets
   `verdict=1` for `failure` / `cancelled` / `NOT RUN`** — `skipped` is labelled
   "not a pass" while `verdict` stays `0`, so the job exits **GREEN**. The
   closing banner even says *"SKIPPED rows are not passes"* and then exits 0.
   **rad-gateway already resolves this the strict way** (line 285:
   `skipped) …; verdict=1 ;;`). The text and the exit disagree here.

   Tightening MergeKingdom to match rad-gateway is in-scope gate work (this repo
   is a gate testbed), but it would leave the testbed permanently red on any
   runner without a DB configured — which is its current state — so it is an
   owner call about desired strictness, not a silent fix.

2. **LobsterWars' `gate-summary` never fails.** It has `needs: [guardrails-scan,
   semantic-scan, regression-check, silent-success]` and `if: always()` and writes
   a results table to `$GITHUB_STEP_SUMMARY` — and contains no `exit`, no
   `verdict`, no `FAILED` anywhere in the file. It is the summary half of the
   honest-matrix pattern without the verdict half. Only the Pattern Scan key is
   affected today (the other three jobs are strict), but the aggregator is not
   fail-closed.

3. **Four named promotion debts, none taken.** radredeye × 2 and
   radredeye-vision-review × 2 each carry a written promotion path
   (tune `.gitleaks.toml` / bake gitleaks into the runner image /
   `TODO(promote-to-blocking)` after rustsec triage). They are honest about being
   not-yet-hard, and they stay open.

## What this does not do

- **D1** (exclude `openclaw`) and **D2** (two-owner token scope) are unchanged —
  both are owner decisions, and D1 narrows coverage.
- **D4** (per-repo findings triage, 55 repos in the live sweep) is untouched.
- The 2026-11-05 correction amended **this record only**. D3-a/b/c are named,
  not fixed; no workflow, gate script, or allowlist was touched.
- No allowlist entry, exclusion, or workflow edit.
- Nothing in `RADICAL-CODE`.

## Bottom line

Of 26 actionable SGR-16 keys across 9 repos, **23 are legitimate design, not
exemption**: fail-closed aggregation, documented non-gating signal jobs whose
commands actually run, report/upload steps, and failure-path diagnostics.
**1 is a real advisory gate** (LobsterWars Pattern Scan) held at a baseline that
is still exactly 13 violations.

**2 are not justified and are corrected here.** `radredeye` `guardrails.yml:61`
exempts a job that has never compiled anything — its command cannot resolve a
workspace-excluded crate. `pi-ithacus` `secret-validation.yml:27` discards a
security scanner's result entirely; the "strict fallback" beside it is a
different, weaker scanner, not an enforcement of the first. Both are owner
calls.

**Zero keys convert.** But the claim is now narrower than the first draft made
it. The verdict-aggregator test separates aggregation from exemption and does
that job well; it does not establish that the check being softened works. Two
rows passed on the strength of an in-file comment describing intent rather than
behaviour, and a third row's key is sound while the gate it reports on has never
evaluated a rule. "Justify" here means the key's shape is right **and** the
thing it softens is a working check — nothing more.

One finding stands outside the key counts: GitHub reports a `continue-on-error`
step **or job** as `success` on non-zero exit, so a green Actions UI is not
evidence that a check passed.
