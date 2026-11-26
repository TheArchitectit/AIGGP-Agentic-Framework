# Spec gap scanner — MergeKingdom testbed acceptance (SGA-07, task 1.5)

The work-order acceptance list (`MergeKingdom/docs/SPEC-GAP-SCANNER-WORK-ORDER.md`
Sec.Testbed acceptance, five criteria) run against the live testbed. Criteria 1–3
were recorded at scanner adoption (testbed HEAD `a2fa6b2`); criteria 4–5 landed
with the reviewed spec set (testbed HEAD `99dac4e`, 2026-10-24) and are recorded
below. Scanner commit: 25d18b3 (`--scaffold`/`--draft` complete); the testbed's
`.devgate` pin was moved to 518dc80 for the 4–5 run (see criterion 5).

## Criterion 1 — scanner runs green, gap backbone = GAPS.md

`spec_gap_scan.py --root . --json` on MergeKingdom @ a2fa6b2 exits **0** and
prints 70 capabilities, **70 unspaced**, 0 partially-tracked, 0 uncovered IDs,
2 CLAIMED-BUT-ABSENT. Exit 0 with the table (not exit 2) because the tree HAS
anchors — the Sec.A config-refusal wedge is correctly attributed: 0 requirement
IDs but 70 real anchors, so "unknown scope" would be a lie.

Worst-tracked-first ordering holds: `iap-manager` (449 lines) and `save-manager`
(444) lead, `hero-manager` (216) mid-pack — the biggest un-specced surfaces
first, matching the Sec.B table's own emphasis.

## Criterion 2 — scaffold set names GAPS.md's capabilities with evidence

`--scaffold --draft` wrote 70 stubs under `openspec/specs/<cap>/spec.md` (run on
a working copy so the user's tree stays untouched), each carrying its evidence
anchor (`src/autoload/economy_manager.gd:20-107` style) and a
`<!-- draft: unreviewed -->` requirement slot. Every GAPS.md Sec.B concept maps to
a scaffold stem:

| GAPS.md Sec.B | scaffold stem(s) |
|---|---|
| merge-engine | merge-engine ✓ |
| grid-state | grid-state ✓ |
| economy | economy-manager |
| item-database | item-database ✓ |
| production | production-system |
| building-models | building-base, building-data |
| zones-progression | zone-manager, zones |
| quests | quest-manager, quest-data |
| achievements | achievement-manager, achievements |
| daily-rewards | daily-rewards-manager, daily-bonuses |
| building-upgrades | building-upgrade-manager |
| converters | converter-manager |
| defense | defense-manager |
| leaderboard | leaderboard-manager |
| heroes | hero-manager |
| weather | weather-manager |
| prestige | prestige-manager |
| stats-analytics | stats-manager, analytics-manager |
| persistence | save-manager, save-migrations |
| settings | settings-manager |
| monetization-iap | iap-manager, iap-validator |
| monetization-ads | ad-manager, admob-provider, unity-ads-provider |
| ui-surfaces | ~20 individual `src/ui/*` stems (hud, prestige-screen, …) |
| lifecycle | **absent by design** — `main.gd` is the scene entry point, excluded |

Two documented divergences from the curated names, both correct-for-a-mechanical
scanner: (a) stems, not concepts (`economy-manager` where GAPS writes `economy`)
— aliasing to human concept-names is a scaffold/review concern, not a scan one;
(b) `ui-surfaces` and `lifecycle` are aggregate labels the file-based inventory
cannot mint — a scanner that names "ui-surfaces" would be inventing a capability,
violating rail 1 (SGA-01: capability candidates named from files that exist,
never invented). `main.gd` exclusion is the scanner's stated scene-entry rule.

## Criterion 3 — reviewed drafts, false claims stay claims

`--draft` output on the copy passed the "no known false claim reappears as fact"
check: the report JSON contains **none** of `production_ready`, `merge_sparkle`,
or `HERO_MERGE_COST_MULT` (Sec.E retired claims + Sec.C1). Two independent reasons:
rail 3 (CLAIMED-BUT-ABSENT never scaffolds — `test_scaffold_ignores_claimed_but_absent`)
and the mechanical classes only emit on *current* source absence. `HERO_MERGE_COST_MULT`
is gone because the testbed retired it in commit `f4fe20d` ("fix: retire
HERO_MERGE_COST_MULT"), and the 6 dead quest events were wired in `004f0cb`, so
the event-claimed class correctly reports **0** dead templates now vs GAPS.md Sec.C2's
11 — the scanner tracks the code, not the stale doc. The 2 surviving const-dead
claims (`INVASION_POPUP_SCENE`, `MAX_HEROES`) are genuine current-tree findings
the handoff predates.

The review-admits transition is locked in tests (`test_review_admits_the_draft`):
deleting the `<!-- draft: unreviewed -->` marker is the ONLY edit that moves a
draft from excluded (0 counted) to a real uncovered ID.

## Criterion 4 — reviewed IDs land; traceability leaves config refusal

All 70 scaffold specs were reviewed one by one against their source in the
testbed and landed at HEAD `99dac4e` (`openspec/gate-config.json` sets
`default_mode: blocking`). Every `<!-- draft: unreviewed -->` marker was
deleted — the review flip — and every newly exposed requirement got a source
marker in the file it describes. The review was not a rubber stamp: spec text
the scaffold had inherited as fact was corrected where the code disagreed, and
defects found while reading were written into the specs as divergences rather
than smoothed over (for example daily-bonus's re-open/claimable state and its
double-then-claim triple payout, prestige's literal `%%` and hard-coded loss
text, the IAP catalogue missing three paid shop ids, a receipt validator that
validates without a server, two idle popups nothing instances, and an invasion
popup that opens after the invasion it reports has already resolved).

Measured on the staged tree with the gates as `devgate-gates.yml` runs them:

| check | result |
|---|---|
| `spec_traceability.py --report` | **249/249 covered**, exit 0 |
| `spec_traceability.py --ratchet` | exit 0 (floor 249, see criterion 5) |
| `spec_gap_scan.py --fail-on-gaps` | exit 0 — `capabilities=70 unspaced=0 partially_tracked=0 uncovered_ids=0/249 claimed_but_absent=2` |

The two CLAIMED-BUT-ABSENT leads are reported only as leads, never requirements:
`MAX_HEROES` (`src/autoload/hero_manager.gd:9`) and `INVASION_POPUP_SCENE`
(`src/ui/invasion_popup.gd:6`), both defined and never referenced elsewhere.

The refusal-to-coverage path was re-proved on the landed tree rather than
inherited from the earlier one-spec demonstration — each mutation below was
applied, measured, and restored, and the tree re-measured 249/249 afterwards:

| mutation | traceability | ratchet | gap scan |
|---|---|---|---|
| `openspec/specs/` absent | **exit 2** — "no spec files found" | — | — |
| malformed `gate-config.json` | **exit 2** — parse error | — | — |
| a source marker deleted (blocking) | **exit 1**, 5 UNCOVERED, 244/249 | exit 1 | exit 1 |
| same, with `default_mode: advisory` | exit 0 (advisory 5 uncovered) | **exit 1** — 244 < floor 249 | exit 1 |

Exit 2 is reported as a config error and never as a pass; in blocking mode an
uncovered ID is exit 1; and the ratchet catches a marker drop even when the
coverage mode would wave it through. That is criterion 4's "exits
config-refusal into real numbers."

## Criterion 5 — honest CI matrix and a recorded ratchet floor

The floor is `.guardrails/traceability-ratchet.json` = `{"min_covered": 249}`,
written by `--update-ratchet` only after the count was final, and enforced in
CI by a `--ratchet` step beside the `--report` step.

The testbed's `.devgate` pin was moved `4e79f76` → `518dc80` for this run. On
the old pin the workflow could not have produced the row it declares:
`spec_gap_scan.py` does not exist at `4e79f76`, and its `spec_traceability.py`
predates the `openspec/specs` layout and reports `0/249 covered`. Both new rows
were therefore red-before-green by construction, not by choice.

CI run [`40129274169`](https://github.com/TheArchitectit/MergeKingdom/actions/runs/40129274169)
on `99dac4e` reports the matrix as it is:

| Gate | Verdict |
|---|---|
| spec_traceability | **PASS** |
| spec_gap_scan | **PASS** |
| pattern (guardrails) | FAIL — PREVENT-007 `scripts/merge-kingdom-cron.py:31` |
| game_regression | FAIL — 60 issues |
| scene_inventory | FAIL — 10 scenes, 17 orphaned buttons |
| drift (regression_check) | FAIL — `scripts/regression_check.py` 1047 lines vs 500 |
| semantic | **PASS** |
| silent_success | **PASS** |
| schema_health | SKIPPED (no DB — not a pass) |

Job verdict: **RED**, stated in the step as "at least one gate failed or did not
run. Every row above is honest; nothing here is softened." The four red rows
are outside criterion 5's scope and were verified unchanged, not assumed: the
same four gate scripts run on the old pin `4e79f76` produce the identical
counts (1 PREVENT-007 violation, 60 game-regression issues, 10 scene failures /
17 orphans, 1 over the hard limit). The two spec gates are the delta this lane
owns, and both are green.

## The scaffold set now lives in the testbed

Criteria 1–3 ran on a throwaway copy (`/tmp/mk-scaffold-test`) because the
testbed had no `openspec/` dir at `a2fa6b2`. The reviewed set was adopted at
`99dac4e`: 70 capability specs under `openspec/specs/`, `openspec/gate-config.json`,
and the ratchet floor. The remaining untracked `docs/DIGEST-FOLLOWUPS.md` and
Godot-generated `.gd.uid` sidecars were deliberately not committed.
