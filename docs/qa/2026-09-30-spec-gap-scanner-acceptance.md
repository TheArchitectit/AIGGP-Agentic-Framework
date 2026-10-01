# Spec gap scanner — MergeKingdom testbed acceptance (SGA-07, task 1.5)

The work-order acceptance list (`MergeKingdom/docs/SPEC-GAP-SCANNER-WORK-ORDER.md`
§Testbed acceptance, five criteria) run against the live testbed. Criteria 1–3
are recorded here; criteria 4–5 are the post-review lane (see "Deferred").
Scanner commit: 25d18b3 (`--scaffold`/`--draft` complete). Testbed HEAD:
`a2fa6b2`.

## Criterion 1 — scanner runs green, gap backbone = GAPS.md

`spec_gap_scan.py --root . --json` on MergeKingdom @ a2fa6b2 exits **0** and
prints 70 capabilities, **70 unspaced**, 0 partially-tracked, 0 uncovered IDs,
2 CLAIMED-BUT-ABSENT. Exit 0 with the table (not exit 2) because the tree HAS
anchors — the §A config-refusal wedge is correctly attributed: 0 requirement
IDs but 70 real anchors, so "unknown scope" would be a lie.

Worst-tracked-first ordering holds: `iap-manager` (449 lines) and `save-manager`
(444) lead, `hero-manager` (216) mid-pack — the biggest un-specced surfaces
first, matching the §B table's own emphasis.

## Criterion 2 — scaffold set names GAPS.md's capabilities with evidence

`--scaffold --draft` wrote 70 stubs under `openspec/specs/<cap>/spec.md` (run on
a working copy so the user's tree stays untouched), each carrying its evidence
anchor (`src/autoload/economy_manager.gd:20-107` style) and a
`<!-- draft: unreviewed -->` requirement slot. Every GAPS.md §B concept maps to
a scaffold stem:

| GAPS.md §B | scaffold stem(s) |
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
or `HERO_MERGE_COST_MULT` (§E retired claims + §C1). Two independent reasons:
rail 3 (CLAIMED-BUT-ABSENT never scaffolds — `test_scaffold_ignores_claimed_but_absent`)
and the mechanical classes only emit on *current* source absence. `HERO_MERGE_COST_MULT`
is gone because the testbed retired it in commit `f4fe20d` ("fix: retire
HERO_MERGE_COST_MULT"), and the 6 dead quest events were wired in `004f0cb`, so
the event-claimed class correctly reports **0** dead templates now vs GAPS.md §C2's
11 — the scanner tracks the code, not the stale doc. The 2 surviving const-dead
claims (`INVASION_POPUP_SCENE`, `MAX_HEROES`) are genuine current-tree findings
the handoff predates.

The review-admits transition is locked in tests (`test_review_admits_the_draft`):
deleting the `<!-- draft: unreviewed -->` marker is the ONLY edit that moves a
draft from excluded (0 counted) to a real uncovered ID.

## Deferred — criteria 4 and 5 (post-review, need human spec authoring)

Criterion 4 ("after review + IDs land, traceability exits config-refusal into
real numbers") was **demonstrated** on the working copy: reviewing one
`merge-engine` draft (delete marker + land `# spec: merge-engine-gap-01` in
`merge_engine.gd`) moved `spec_traceability.py` from exit 2 to **`1/1
requirements covered`, exit 0**, and the gap re-scan showed `unspaced=0,
uncovered_ids=0/1`. So the *mechanism* is proven; what criterion 4 actually asks
is the human act of authoring 70 real spec bodies, which is the testbed's
Sprint-3 work (SGA-07's "next CI matrix" clause), not the scanner's. Criterion 5
(the lane's CI matrix + ratchet floor) is that same lane's next run. Recorded
here as stated assumptions per hard rule #5 — criteria 1–3 are the scanner's
acceptance; 4–5 are the fleet lane's, and the scanner does its part of 4 (the
refusal-to-coverage path) provably.

## Not written to the testbed

All `--scaffold`/`--draft` runs were on a throwaway copy (`/tmp/mk-scaffold-test`
seeded from MergeKingdom's `src`/`data`/`game-specs`). MergeKingdom's real tree
has no generated `openspec/` dir — the handoff owns whether to adopt the scaffold
set; the scanner's job is proven it produces a correct one.
