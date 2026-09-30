# Tasks: spec-audit-rollout

## Sprint 1 — the scanner (MergeKingdom acceptance)

- [x] 1.1 Extract shared coverage discovery into `scripts/lib/spec_discovery.py`; `spec_traceability.py` imports it, numbers byte-identical before/after on this repo (SGA-05) — done 666a30d, 79/142 diff-clean, draft-exclusion included
- [x] 1.2 `scripts/spec_gap_scan.py` scan mode: inventory + coverage + gap report (JSON + human table, worst-tracked first, CLAIMED-BUT-ABSENT separated); exits 0/1/2 per SGA-01/03/04 — done 9df2e19; testbed scan reproduces GAPS.md §C2 dead-event set exactly (11 templates / 6 events)
- [x] 1.3 `tests/test_spec_gap_scan.py`: planted-gap fixture repo, planted CLAIMED-BUT-ABSENT, planted false-claim case the generator must not turn into a requirement, unreadable-root exit 2, looked-and-found-nothing wording — done 9df2e19 (16 tests; CBA cut to two provable classes after §E's production_ready lie was re-emitted)
- [ ] 1.4 `--scaffold` (evidence stubs, empty requirement slots, no prose) and `--draft` (born `<!-- draft: unreviewed -->`); exclusion of unreviewed drafts from every coverage count, tested (SGA-02)
- [ ] 1.5 MergeKingdom run: gap table vs GAPS.md backbone, scaffold set match, known false claims stay claims — acceptance 1–3 recorded in `docs/qa/` (SGA-07)
- [ ] 1.6 CI row in the standard gate template (`--fail-on-gaps` off at first, advisory)

## Sprint 2 — the intake gate

- [ ] 2.1 `spec-fleet.yml`: declaration reuse, per-repo clone+classify, state vocabulary SGA-10..12, capped report to `docs/qa/spec-sweeps/`, artifact
- [ ] 2.2 `spec-audit-tier.txt` + invalid-red gating for tiered repos only (SGA-11)
- [ ] 2.3 `hub_alert.py --key spec_fleet_sweep` wiring; T-style proofs: new unspaced repo noticed next night (SGA-10 scenario), unscannable named in body (SGA-12), dedupe one-issue (SGA-13)
- [ ] 2.4 Mutation proofs: empty declaration → exit 3 family red; classify-fault → unknown never spaced; a tiered invalid repo → red names it

## Sprint 3 — provenance

- [ ] 3.1 Inventory vendored openspec templates in tree; write `spec-templates.lock.json` with source URL + sha256 verified locally (SGA-20)
- [ ] 3.2 Refresh-check step in the walk: fetch, hash, compare, deduped drift issue (SGR-11 channel) (SGA-21)
- [ ] 3.3 Unreachable-upstream path → unknown + fault red, never in-sync (SGA-22)
- [ ] 3.4 One reviewed adoption round-trip documented (drift alert → lock+copy bump commit → issue closed) (SGA-21 scenario 3)

## Sprint 4 — closeout

- [ ] 4.1 MergeKingdom acceptance 4–5: reviewed IDs land, traceability exits config-refusal into real numbers, CI matrix rows honest, ratchet floor recorded
- [ ] 4.2 gameSessionStart advisory line ("worst-tracked gaps: N") consuming the scanner's JSON — one inventory source (design §gameSessionStart)
- [ ] 4.3 Exit evidence `docs/qa/<date>-spec-audit-live.md`: runs, census, mutation proofs, stated assumptions (hard rule #4 shape)
- [ ] 4.4 Adjacent-debt note: CI's unpinned `npx openspec` CLI (assumption 5) filed as its own item, not silently fixed here
