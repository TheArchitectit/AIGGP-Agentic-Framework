# Secret Fleet Sweep — triage of the chronically-red scheduled run (2026-10-11)

Owner directive: Roger, 2026-10-11 ("Address all issues"). This is a **triage
record + proposed dispositions**, not a gate change. No exclusion, no allowlist
entry, and no workflow edit is applied here — the sweep's coverage is not
weakened to make it green. Anything that narrows coverage is proposed below for
owner sign-off.

## What is red, and why

`secret-fleet.yml` (schedule, `main`) has failed on every run 2026-10-08/09/10
(e.g. `38045679232`). The terminal `Fail loudly and route` step fails on
`drift[]` **or** `advisory[]` being non-empty. From the 2026-10-10 report:

- `drift` = **0** — no vendored gate fork.
- `advisory` = **77** — SGR-16 (a `continue-on-error: true` key in a workflow).
- `states`: clean 78, **findings 54**, **unfetchable 4**, unscannable 0.
- `declared` 136, `scanned` 132.

So the red is driven by **advisory entries (77)** and is *also* reported via the
hub issue because the sweep's own `rc`/findings path is non-zero. Two distinct
root causes, both outside AIGGP's own tree:

### Root cause 1 — 57 of 77 advisory entries are an upstream fork's own workflows

`TheArchitectit/openclaw` is a **fork of `openclaw/openclaw`** (`fork=true`,
`parent=openclaw/openclaw`). Its `.github/workflows/*` are the upstream
project's own files (`auto-response.yml`, `clawsweeper-dispatch.yml`,
`dated-todo-sweep.yml`, `dependency-guard.yml`, `full-release-validation.yml`,
…). These are the *same noise class* the exclude file already names for
`llama.cpp` ("upstream fork; sweeping upstream history is noise"). The fork's
default-branch workflows are not our leak surface.

The remaining 20 advisory entries are in our own repos (radredeye,
radredeye-vision-review, LobsterWars, MergeKingdom, NemoClaw, OpenRawFlow,
pi-ithacus-agent-framework, rad-gateway, radcode, RADICAL-CODE) — these are
genuine SGR-16 items to triage per-repo, not fleet-monitor noise.

### Root cause 2 — the 4 "unfetchable" entries are a token-scope gap

`fleet-sweep-include.txt` deliberately lists the `drwhofan2k18-pixel/*`
counterparts (the "two-owner problem"). The sweep's App installation token is
scoped to `TheArchitectit`, so `git clone` of a `drwhofan2k18-pixel` URL fails
with `Repository not found` (HTTP 404 = no access). The URLs resolve fine under
an account that can see both owners (`gh api` confirms all four exist). This is
a **credential-scope gap**, not a repo defect: the include file asks for
coverage the token cannot deliver.

## Findings volume (for context, not a verdict)

54 repos report `findings`; the report caps shown locations at 50/repo, so
`findings` counts exceed listed locations (e.g. `openclaw` 502,514;
`openagentplatform` 78). Sampling the shown locations, the large majority are
documentation, vendored dependency trees (`.cargo/registry`, `vendor`,
`node_modules`), test fixtures, and lockfiles — the standard false-positive
classes. The largest single contributor is again the `openclaw` upstream fork.
This is **not** a claim the fleet is clean: 54 repos carry real triage work, and
each needs its own pass. It is a statement about where the monitor's signal is
currently dominated by known-noise classes.

## Proposed dispositions (owner sign-off required — none applied)

1. **Exclude the upstream fork by name** — add `openclaw` to
   `fleet-sweep-exclude.txt` with the reason "upstream fork; its workflows are
   upstream's own and are not our leak surface" (same class as `llama.cpp`).
   This removes 57 of 77 advisory entries and the single largest findings
   contributor. *Effect on coverage: deliberate and reasoned, mirroring an
   existing, accepted exclusion.*
2. **Fix the two-owner token scope** — either extend the App installation to
   `drwhofan2k18-pixel`, or move those 4 URLs out of `include` until the token
   can reach them, so the declaration stops asking for coverage it cannot get.
   Preferred: extend scope (keeps the two-owner sweep intact).
3. **Per-repo SGR-16 triage** for the 20 in-our-repos advisory entries — each is
   a real `continue-on-error: true` to justify, convert, or baseline per repo.
4. **Per-repo findings triage** across the 54 repos — separate workstream; the
   monitor is correctly naming a large backlog, not a single defect.

## Why this is not fixed here

Both root causes are **policy/scope decisions**, not code defects in AIGGP.
Applying (1) unilaterally would change what the fleet monitor covers; applying
(2) needs an App-installation scope change owned outside this repo. Both are
proposed above for Roger. The honest state is: the monitor is red because it is
**working** — it is reporting a large, real, mostly-known-noise backlog plus one
credential-scope gap.
