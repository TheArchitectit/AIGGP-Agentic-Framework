# spec-audit-rollout — exit evidence (2026-10-23)

Hard rule #4 shape. Package: `spec-audit-rollout` (tracker repo
`repo-brainstorming`, `devgate-open-changes`). Implementation lives here in
AIGGP main: `5afe0f2` (gate, classifier, walk, tier file, lock, 17 tests),
`350bbe4` (gate-fault reason names what was actually tried), `d1b0015`
(tests hermetic against a runner with no validator; sweep installs one and
passes the lock).

What this document is: the measured state of the package at exit. What it is
not: an adoption. Every number below came from a run on this machine or from
CI, and the sections marked **not done** are the parts that still need a live
nightly or an operator decision — they are not claimed as complete.

## Gate runs (this tree, 2026-10-23)

| Gate | Result |
|---|---|
| `npx openspec validate --all --strict` | `Totals: 33 passed, 0 failed (33 items)` |
| `scripts/specs-validate-negative-control.sh` | passed — strict validation refused the malformed fixture naming its designed defect (missing `## Purpose`), exit 1 |
| `python3 tests/gen_floors.py --check` | `test-floor: OK — 124 suites, 1725 tests` |
| `node scripts/guardrails-scan.mjs` | `pattern scan clean`, 32 non-blocking warnings |
| `python3 scripts/regression_check.py --base origin/main --fail-if-empty --pre-commit` | `0 over hard limit`, 37 soft-limit warnings, 3 scope-gap warnings (all pre-existing) |
| full pytest | `1725 passed, 182 subtests passed` (2 min 10 s) |
| fleet tests on a PATH with no `openspec` | `17 passed` — see the hermeticity proof below |

## Census — proof walk (2026-10-23)

Declaration: AIGGP, missioncontrol, repo-brainstorming (local paths, so the
run is the same code path the workflow uses minus `git clone`).

```
declared=3  scanned=3  states={spaced: 2, unspaced: 1}
AIGGP-Agentic-Framework   spaced     tiered=True   red=False  strict_state=ok
missioncontrol            spaced     tiered=False  red=False  strict_state=ok
repo-brainstorming        unspaced   tiered=False  red=False  strict_state=None
lock_provenance: fault=False  unknown=[]  drift=[openspec-proposal,
                openspec-spec, openspec-design, openspec-tasks]
```

The four drift entries are real: upstream `main` has moved past the pinned
v1.13.0 copies (the pins themselves verify — `pin_source` hashes match, so
`fault=False`). Drift is printed as a finding, not red, which is the SGA-21
semantics; see "not done" for the deduped issue half.

## Mutation proofs

Each proof mutates the input or the environment and shows the gate reds (or
stays honestly quiet) for the right reason.

1. **Empty declaration → walk refuses.** `spec-fleet-walk.sh` with an empty
   declaration file exits **3** and writes an error report: "empty
   declaration — refusing to write a vacuous report". A 0-repo sweep cannot
   read green on the trend line.
2. **Validator absent → unscannable, never spaced, never red.**
   `SPEC_AUDIT_OPENSPEC_BIN` pointed at a non-file, `PATH` emptied:
   `state=unscannable`, `red=False`, reason
   `openspec CLI not found (SPEC_AUDIT_OPENSPEC_BIN set but not a file; …)`.
   The first run of this proof caught the reason **lying** ("unset" when the
   variable was set), fixed in `350bbe4` and pinned by an assertion.
3. **Tiered invalid → red, naming the repo.** A fixture with a malformed
   `spec.md` and a tier entry, scored by the workflow's own red snippet
   extracted from `spec-fleet.yml`: exit **1** naming `['invalidrepo']`; the
   same snippet against the green tree exits **0**. The same fixture
   *without* a tier entry reads `invalid/red=False` — an unenforced repo is
   never called a failure.
4. **Hermeticity of the tests.** On a `PATH` containing only `python3`, the
   tiered-invalid fixture classifies `unscannable/red=False` without the
   stub and `invalid/red=True` with it — i.e. before `d1b0015` those two
   tests asserted the classifier's behavior while actually measuring the
   runner's missing binary. They now supply their own stub CLI.
5. **Provenance unreachable upstream → unknown + fault.** A lock entry whose
   `source` points at a closed port yields `unknown` for that template and
   `fault=True`; the walked tree itself is **not** blamed
   (`test_provenance_unreachable_upstream_is_unknown_not_in_sync`).
6. **Pin lying about itself → fault.** A `pinned_sha256` that does not match
   its own `pin_source` sets `fault=True` and reports the real hash.

## Stated assumptions (hard rule #5)

1. **The sweep's validator is the pinned npm CLI.** `spec-fleet.yml` now
   installs `@fission-ai/openspec@1.13.0` — the version the lock's
   `upstream_version` and `templates/github-workflows/specs.yml` name — and
   hands it to the classifier via `SPEC_AUDIT_OPENSPEC_BIN`. A nightly run on
   a runner that cannot reach the npm registry reads every openspec repo
   `unscannable` and reds; that is deliberate (census honesty) but it is a
   dependency on network + registry availability.
2. **Tier membership is a reviewed decision, not a scan result.**
   `spec-audit-tier.txt` carries a reason per entry; a reason-less entry is a
   gate fault (exit 2). Today it lists AIGGP only.
3. **`unscannable` reds, `unspaced` never does.** A repo with no openspec
   material is informational; a repo with material that cannot be validated
   is a hole in the census, so it reds.
4. **Drift is a finding, not a gate.** Upstream moves whenever Fission-AI
   edits a template; reding that every night is the muted-gate failure
   (SGR-10) the package exists to avoid. Only `fault`/`unknown` red.
5. **No automated process writes into a consumer tree.** Lock and vendored
   copies change in one reviewed commit.

## Not done at exit (carried as open boxes, not silently closed)

- **Live T-proofs** (tracker 2.3): the three nightly scenarios — a new
  unspaced repo noticed the next night, an unscannable repo named in the
  alert body, one deduped issue — need a real scheduled run. The wiring is
  in `spec-fleet.yml`; the runs have not happened.
- **Deduped drift issue** (3.2) and the **first reviewed adoption
  round-trip** (3.4): findings are printed and the lock/adoption procedure is
  documented in `2026-10-22-template-provenance.md`, but no consumer has yet
  taken a drift alert through lock+copy bump to issue close.
- **MergeKingdom acceptance 4–5** (4.1), the **`gameSessionStart` advisory
  line** (4.2 — its adapters live outside AIGGP), and **adjacent debt: CI's
  unpinned `npx` resolve** (4.4) — filed, not fixed here.

## Cleanup

No scratch repos, fixtures, or branches were left behind by these proofs:
every fixture is created under `tmp_path` or `/tmp` in the same command that
measures it.
